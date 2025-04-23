import asyncio
import threading
import time
from abc import ABC, abstractmethod

import psutil

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus
from app.utils.logger import logger
from app.utils.redis import RedisManager, RedisQueue
from app.workers.judge_worker import JudgeWorker


class ThreadWorker(ABC):
    r"""Base class for background sync thread workers."""

    def __init__(self, name: str, interval: float):
        self.name = name
        self.interval = interval
        self.thread = None
        self.running = False
        self.exit_event = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.exit_event.clear()
        self.thread = threading.Thread(name=self.name, target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.exit_event.set()

    def run(self):
        try:
            while self.running:
                try:
                    self.execute()
                except Exception as e:
                    logger.error(f"Error in worker {self.name}: {str(e)}")

                if not self.exit_event.wait(self.interval):
                    continue
                break
        except Exception as e:
            logger.error(f"Error in worker {self.name}: {str(e)}")

    @abstractmethod
    def execute(self):
        pass


class AsyncThreadWorker(ThreadWorker):
    r"""Thread worker that executes async functions."""

    def __init__(self, name: str, interval: float):
        super().__init__(name=name, interval=interval)

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            while self.running:
                try:
                    loop.run_until_complete(self.async_execute())
                except Exception as e:
                    logger.error(f"Error in worker {self.name}: {str(e)}")

                if not self.exit_event.wait(self.interval):
                    continue
                break
        except Exception as e:
            logger.error(f"Error in worker {self.name}: {str(e)}")

    def execute(self):
        pass

    @abstractmethod
    async def async_execute(self):
        pass


class WorkerMonitor(ThreadWorker):
    r"""Monitors the status of worker processes."""

    def __init__(self, workers: list, interval: float = 10.0):
        super().__init__(interval=interval, name="worker-monitor")
        self.workers = workers

    def execute(self):
        status = self.check_workers_status()
        self.log_status_summary(status)

    def check_workers_status(self):
        status = {"total": len(self.workers), "failed": 0, "busy": 0, "hanging": 0}
        for i, worker in enumerate(self.workers):
            if not worker.is_alive():
                logger.error(f"Worker process {worker.worker_id} stopped, restarting...")
                new_worker = JudgeWorker(worker.worker_id)
                new_worker.start()
                self.workers[i] = new_worker
                status["failed"] += 1
            else:
                self.check_worker_activity(worker, status)

        return status

    @staticmethod
    def check_running(proc: psutil.Process):
        try:
            return (
                proc.status()
                not in (
                    psutil.STATUS_ZOMBIE,
                    psutil.STATUS_DEAD,
                    psutil.STATUS_STOPPED,
                )
                and proc.is_running()
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @staticmethod
    def terminate_process(proc):
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                proc.kill()
                proc.wait(timeout=1)
            except Exception as e:
                logger.error(f"Kill failed for {proc.pid}: {str(e)}")
                return False
        return True

    def check_worker_activity(self, worker: JudgeWorker, status: dict):
        try:
            worker_process = psutil.Process(worker.pid)
            is_busy = is_hanging = 0
            for child in worker_process.children(recursive=True):
                is_busy = 1
                if (
                    self.check_running(child)
                    and time.time() - child.create_time() > settings.MAX_TASK_EXECUTION_TIME
                ):
                    is_hanging = 1
                    logger.warning(f"Worker process {worker.worker_id} has a hanging child process")
                    self.terminate_process(child)

            status["busy"] += is_busy
            status["hanging"] += is_hanging
        except Exception as e:
            logger.error(f"Failed to check worker process {worker.worker_id}: {str(e)}")

    def log_status_summary(self, status: dict):
        logger.info(
            f"Worker process status - Total: {status['total']}, "
            f"Idle: {status['total'] - status['busy']}, "
            f"Failed: {status['failed']}, "
            f"Busy: {status['busy']}, "
            f"Hanging: {status['hanging']}"
        )


class TaskRecovery(AsyncThreadWorker):
    r"""Recovers and requeues stuck tasks."""

    def __init__(self, interval: float = 0.2):
        super().__init__(interval=interval, name="task-recovery")

    async def async_execute(self):
        length = await RedisManager.length(RedisQueue.SUBMISSIONS)
        if length != 0:
            return

        recovered = 0
        task_keys = await RedisManager.keys(RedisQueue.TASKS)
        for key in task_keys:
            task_info = await RedisManager.get_hash_fields(key, ["status", "submitted_at", "data"])
            status = task_info.get("status")
            current_time = float(time.time())
            if (
                status == JudgeStatus.PENDING
                and length == 0
                and current_time - float(task_info.get("submitted_at", float("inf"))) > 5.0
            ) or (
                status == JudgeStatus.RUNNING
                and current_time - float(task_info.get("running_at", float("inf")))
                > settings.MAX_TASK_EXECUTION_TIME
            ):
                key = key.decode("utf-8").split(":")[-1].split("-")[0]
                logger.warning(f"Detected lost pending task: {key}!")
                recovered += 1
                await self.recover_task(key, task_info.get("data"))

        if recovered > 0:
            logger.info(f"Recovered {recovered} lost or hanging tasks")

    async def recover_task(self, task_id: str, task_data: dict):
        if task_data:
            await RedisManager.push(RedisQueue.SUBMISSIONS, task_data)
            logger.info(f"Task {task_id.split(':')[-1]} has been re-queued")
        else:
            error_result = JudgeResult(
                status=JudgeStatus.SYSTEM_ERROR,
                error_message="Task lost and cannot be recovered",
                task_id=task_id,
            )
            await RedisManager.push(
                RedisManager.queue(RedisQueue.RESULTS, task_id), error_result.model_dump_json()
            )
            logger.warning(f"Failed to recover task {task_id}, marked as error")


class RedisCleanup(AsyncThreadWorker):
    r"""Cleans up expired keys in Redis."""

    def __init__(self, interval: float = 300.0):
        super().__init__(interval=interval, name="redis-cleanup")
        self.batch_size = 1000

    async def async_execute(self):
        deleted_count = await self.cleanup_keys(
            RedisManager.pattern(RedisQueue.TASKS), self.is_expired_task
        )
        orphaned_count = await self.cleanup_keys(
            RedisManager.pattern(RedisQueue.RESULTS), self.is_orphaned_result
        )

        if deleted_count > 0 or orphaned_count > 0:
            logger.info(
                f"Cleanup completed: removed {deleted_count} expired tasks "
                f"and {orphaned_count} orphaned result queues"
            )

    async def cleanup_keys(self, pattern: str, filter_func: callable) -> int:
        deleted_count = cursor = 0

        while True:
            cursor, keys = await RedisManager.scan(cursor, match=pattern, count=self.batch_size)
            if not keys:
                if cursor == 0:
                    break
                continue

            keys_to_delete = [key for key in keys if await filter_func(key)]

            if keys_to_delete:
                await RedisManager.delete(keys_to_delete)
                deleted_count += len(keys_to_delete)

            if cursor == 0:
                break

        return deleted_count

    async def is_expired_task(self, key: str) -> bool:
        task_info = await RedisManager.get_hash_fields(key, ["submitted_at"])
        submitted_at = float(task_info.get("submitted_at", 0))
        return time.time() - submitted_at > settings.RESULT_EXPIRY_TIME

    async def is_orphaned_result(self, key: str) -> bool:
        task_key = RedisManager.queue(RedisQueue.TASKS, key)
        return not await RedisManager.exists(task_key)
