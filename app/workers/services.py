import asyncio
import threading
import time
from abc import ABC, abstractmethod

import psutil

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus
from app.utils.error_handling import with_error_handling
from app.utils.logger import logger
from app.utils.redis import close_redis, get_redis
from app.utils.redis_helpers import (
    RedisKeyManager,
    get_hash_fields,
    push_to_queue,
)
from app.workers.judge_worker import JudgeWorker


class ThreadWorker(ABC):
    r"""Base class for all background thread workers."""

    def __init__(self, thread_name):
        self.running = True
        self._thread = None
        self.thread_name = thread_name

    def start(self):
        r"""Start the worker thread."""
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._thread_loop, name=self.thread_name, daemon=True
            )
            self._thread.start()
            logger.info(f"{self.thread_name} started")

    def stop(self):
        r"""Stop the worker thread."""
        self.running = False

    def _thread_loop(self):
        r"""Main thread loop that handles exceptions and calls the worker's task."""
        while self.running:
            try:
                # Execute the worker's task
                self._execute_task()
            except Exception as e:
                logger.error(f"{self.thread_name} error: {str(e)}")
            finally:
                # Sleep interval between executions
                time.sleep(self._get_interval())

    @abstractmethod
    def _execute_task(self):
        r"""Task to be executed by the thread. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _get_interval(self):
        r"""Get the interval between task executions. Must be implemented by subclasses."""
        pass


class AsyncThreadWorker(ThreadWorker):
    r"""Base class for thread workers that run async tasks."""

    def _execute_task(self):
        r"""Create a new event loop and run the async task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_task())
        finally:
            loop.close()

    @abstractmethod
    async def _async_task(self):
        r"""Async task to be executed. Must be implemented by subclasses."""
        pass


class WorkerMonitor(ThreadWorker):
    r"""Monitor worker process status and restart when needed."""

    def __init__(self, workers):
        super().__init__("worker-monitor")
        self.workers = workers

    def _execute_task(self):
        r"""Check worker status and restart failed workers."""
        status = self._check_workers_status()
        self._log_status_summary(status)

    def _get_interval(self):
        return settings.MONITOR_INTERVAL

    def _check_workers_status(self):
        r"""Check worker process status and restart failed processes."""
        status = {
            "total": len(self.workers),
            "failed": 0,
            "busy": 0,
            "hanging": 0,
        }

        for i, worker in enumerate(self.workers):
            if not worker.is_alive():
                logger.error(f"Worker process {worker.worker_id} stopped, restarting...")
                # Start a new worker to replace the failed one
                new_worker = JudgeWorker(worker.worker_id)
                new_worker.start()
                self.workers[i] = new_worker
                status["failed"] += 1
            else:
                self._check_worker_activity(worker, status)

        return status

    def _check_worker_activity(self, worker, status):
        r"""Check if a worker is busy or hanging."""
        try:
            worker_process = psutil.Process(worker.pid)
            is_busy = 0
            is_hanging = 0

            # Check all child processes
            for child in worker_process.children(recursive=True):
                is_busy = 1
                # Check if process is hanging (running time too long)
                if (
                    child.is_running()
                    and time.time() - child.create_time() > settings.MAX_TASK_EXECUTION_TIME
                ):
                    is_hanging = 1
                    logger.warning(f"Worker process {worker.worker_id} has a hanging child process")
                    child.kill()

            status["busy"] += is_busy
            status["hanging"] += is_hanging
        except Exception as e:
            logger.error(f"Failed to check worker process {worker.worker_id}: {str(e)}")

    def _log_status_summary(self, status):
        r"""Log the status summary of worker processes."""
        logger.info(
            f"Worker process status - Total: {status['total']}, "
            f"Idle: {status['total'] - status['busy']}, "
            f"Failed: {status['failed']}, "
            f"Busy: {status['busy']}, "
            f"Hanging: {status['hanging']}"
        )


class TaskRecovery(AsyncThreadWorker):
    r"""Recover lost tasks."""

    def __init__(self):
        super().__init__("task-recovery")

    def _get_interval(self):
        return settings.RECOVER_INTERVAL

    @with_error_handling(error_message="Error recovering lost tasks")
    async def _async_task(self):
        r"""Recover lost tasks from Redis."""
        redis = await get_redis()
        try:
            await self._recover_lost_tasks(redis)
        finally:
            await close_redis()

    async def _recover_lost_tasks(self, redis):
        r"""Find and recover lost tasks."""
        task_keys = await redis.keys(RedisKeyManager.all_task_keys_pattern())
        recovered = 0
        queue_length = await redis.llen(settings.REDIS_SUBMISSION_QUEUE)

        for key in task_keys:
            task_info = await get_hash_fields(key, ["status", "submitted_at", "data"])
            status = task_info.get("status")
            task_id = (
                key.decode("utf-8").split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
            )

            if status == JudgeStatus.PENDING and queue_length == 0:
                logger.warning(f"Detected lost pending task: {task_id}!")
                recovered += 1
                await self._recover_task(redis, task_id, task_info.get("data"))

        if recovered > 0:
            logger.info(f"Recovered {recovered} lost or hanging tasks")

    async def _recover_task(self, redis, task_id, task_data):
        r"""Recover a single task."""
        if task_data:
            await push_to_queue(settings.REDIS_SUBMISSION_QUEUE, task_data)
            logger.info(f"Task {task_id} has been re-queued")
        else:
            error_result = JudgeResult(
                status=JudgeStatus.SYSTEM_ERROR,
                error_message="Task lost and cannot be recovered",
                task_id=task_id,
            )
            await push_to_queue(
                RedisKeyManager.result_queue_key(task_id),
                error_result.model_dump_json(),
            )
            logger.warning(f"Failed to recover task {task_id}, marked as error")


class RedisCleanup(AsyncThreadWorker):
    r"""Clean up expired keys in Redis."""

    def __init__(self):
        super().__init__("redis-cleanup")

    def _get_interval(self):
        return settings.CLEANUP_INTERVAL

    @with_error_handling(error_message="Error cleaning up expired keys")
    async def _async_task(self):
        r"""Clean up expired keys in Redis."""
        redis = await get_redis()
        try:
            await self._cleanup_expired_keys(redis)
        finally:
            await close_redis()

    async def _cleanup_expired_keys(self, redis):
        r"""Clean up expired keys in Redis."""
        current_time = time.time()
        deleted_count = await self._cleanup_expired_tasks(redis, current_time)
        orphaned_count = await self._cleanup_orphaned_results(redis)

        if deleted_count > 0 or orphaned_count > 0:
            logger.info(
                f"Cleanup completed: removed {deleted_count} expired tasks "
                f"and {orphaned_count} orphaned result queues"
            )

    async def _cleanup_expired_tasks(self, redis, current_time):
        r"""Clean up expired task keys."""
        deleted_count = 0
        cursor = 0

        while True:
            cursor, keys = await redis.scan(
                cursor, match=RedisKeyManager.all_task_keys_pattern(), count=1000
            )
            if not keys:
                if cursor == 0:
                    break
                continue

            # Process keys in batches
            keys_to_delete, result_queues_to_delete = await self._get_expired_keys(
                redis, keys, current_time
            )

            # Delete expired keys in batch
            if keys_to_delete:
                pipe = redis.pipeline()
                for key in keys_to_delete:
                    pipe.delete(key)
                for result_queue in result_queues_to_delete:
                    pipe.delete(result_queue)
                await pipe.execute()
                deleted_count += len(keys_to_delete)

            if cursor == 0:
                break

        return deleted_count

    async def _get_expired_keys(self, redis, keys, current_time):
        r"""Identify expired task keys and their associated result queues."""
        keys_to_delete = []
        result_queues_to_delete = []

        for key in keys:
            task_info = await get_hash_fields(key, ["submitted_at"])
            submitted_at = float(task_info.get("submitted_at", 0))

            # If the task has expired
            if current_time - submitted_at > settings.RESULT_EXPIRY_TIME:
                keys_to_delete.append(key)
                task_id = (
                    key.decode("utf-8").split(":")[-1]
                    if isinstance(key, bytes)
                    else key.split(":")[-1]
                )
                result_queue = RedisKeyManager.result_queue_key(task_id)
                result_queues_to_delete.append(result_queue)

        return keys_to_delete, result_queues_to_delete

    @with_error_handling(error_message="Error cleaning up orphaned result queues", default_return=0)
    async def _cleanup_orphaned_results(self, redis):
        r"""Clean up orphaned result queues (result queues without corresponding tasks)."""
        orphaned_count = 0
        cursor = 0

        while True:
            cursor, result_keys = await redis.scan(
                cursor, match=RedisKeyManager.all_result_queue_keys_pattern(), count=1000
            )
            if not result_keys:
                if cursor == 0:
                    break
                continue

            # Find and delete orphaned keys
            orphaned_keys = await self._find_orphaned_keys(redis, result_keys)
            if orphaned_keys:
                pipe = redis.pipeline()
                for key in orphaned_keys:
                    pipe.delete(key)
                await pipe.execute()
                orphaned_count += len(orphaned_keys)

            if cursor == 0:
                break

        return orphaned_count

    async def _find_orphaned_keys(self, redis, result_keys):
        r"""Find result queue keys without corresponding task keys."""
        orphaned_keys = []

        for key in result_keys:
            task_id = (
                key.decode("utf-8").split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
            )
            task_key = RedisKeyManager.task_key(task_id)

            # Check if the corresponding task exists
            if not await redis.exists(task_key):
                orphaned_keys.append(key)

        return orphaned_keys
