import asyncio
import threading
import time

import psutil

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.workers.judge_worker import JudgeWorker


async def recover_lost_tasks():
    r"""Recover lost tasks."""
    redis = await get_redis()

    try:
        task_keys = await redis.keys(f"{settings.REDIS_PREFIX}task:*")
        recovered = 0
        queue_length = await redis.llen(settings.REDIS_SUBMISSION_QUEUE)
        for key in task_keys:
            try:
                pipe = redis.pipeline()
                pipe.hget(key, "status")
                pipe.hget(key, "submitted_at")
                status, submitted_at = await pipe.execute()

                status = status.decode("utf-8") if status else None
                submitted_at = float(submitted_at) if submitted_at else None

                task_id = key.decode("utf-8").split(":")[-1]
                if status == JudgeStatus.PENDING and queue_length == 0:
                    # FIXME: This is a temporary fix for the lost task recovery
                    logger.warning(f"Found lost pending task: {task_id}!")
                    recovered += 1

                    task_data = await redis.hget(key, "data")
                    if task_data:
                        await redis.rpush(settings.REDIS_SUBMISSION_QUEUE, task_data)
                        logger.info(f"Requeued task {task_id}")
                    else:
                        error_result = JudgeResult(
                            status=JudgeStatus.SYSTEM_ERROR,
                            error_message="Task lost and could not be recovered",
                            task_id=task_id,
                        )
                        await redis.rpush(
                            f"{settings.REDIS_RESULT_QUEUE}:{task_id}",
                            error_result.model_dump_json(),
                        )
                        logger.warning(f"Could not recover task {task_id}, marked as error")
            except Exception as e:
                logger.error(f"Error processing task key {key}: {str(e)}")

        if recovered > 0:
            logger.info(f"Recovered {recovered} lost or stalled tasks")

    finally:
        # Ensure the connection is closed
        await redis.close()


async def cleanup_expired_keys():
    r"""Clean up expired keys in Redis that weren't automatically cleaned up."""
    redis = await get_redis()
    current_time = time.time()
    deleted_count = 0

    try:
        # 1. clean expired task status
        cursor = 0
        while True:
            cursor, keys = await redis.scan(
                cursor, match=f"{settings.REDIS_PREFIX}task:*", count=1000
            )
            if keys:
                pipe = redis.pipeline()
                keys_to_delete = []

                # Check each key's submission time
                for key in keys:
                    submitted_at = await redis.hget(key, "submitted_at")
                    if submitted_at:
                        submitted_at = float(submitted_at)
                        # If the task has expired
                        if current_time - submitted_at > settings.RESULT_EXPIRY_TIME:
                            keys_to_delete.append(key)
                            task_id = key.decode("utf-8").split(":")[-1]
                            # Delete the corresponding result queue
                            pipe.delete(f"{settings.REDIS_RESULT_QUEUE}:{task_id}")

                # Delete expired keys in batch
                if keys_to_delete:
                    for key in keys_to_delete:
                        pipe.delete(key)
                    await pipe.execute()
                    deleted_count += len(keys_to_delete)

            if cursor == 0:
                break

        # 2. clean possible orphaned result queues
        cursor = 0
        orphaned_results = 0
        while True:
            cursor, result_keys = await redis.scan(
                cursor, match=f"{settings.REDIS_RESULT_QUEUE}:*", count=1000
            )
            if result_keys:
                pipe = redis.pipeline()
                for key in result_keys:
                    task_id = key.decode("utf-8").split(":")[-1]
                    task_key = f"{settings.REDIS_PREFIX}task:{task_id}"
                    # Check if the corresponding task still exists
                    if not await redis.exists(task_key):
                        pipe.delete(key)
                        orphaned_results += 1

                if orphaned_results > 0:
                    await pipe.execute()

            if cursor == 0:
                break

        if deleted_count > 0 or orphaned_results > 0:
            logger.info(
                f"Cleanup completed: removed {deleted_count} expired tasks "
                f"and {orphaned_results} orphaned results"
            )

    except Exception as e:
        logger.error(f"Error during Redis cleanup: {str(e)}")
    finally:
        # Ensure the connection is closed
        await redis.close()


class WorkerManager:
    r"""Manages a pool of worker processes."""

    def __init__(self):
        self.workers: list[JudgeWorker] = []
        self.running = True

        # Start workers
        max_workers = settings.MAX_WORKERS

        for i in range(max_workers):
            worker = JudgeWorker(i)
            worker.start()
            self.workers.append(worker)

        logger.info(f"All {max_workers} workers started")

        # Start monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_workers, name="worker-monitor", daemon=True
        )
        self._monitor_thread.start()

        # Start recovery thread
        self._recovery_thread = threading.Thread(
            target=self._run_recovery, name="worker-recovery", daemon=True
        )
        self._recovery_thread.start()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._run_cleanup, name="redis-cleanup", daemon=True
        )
        self._cleanup_thread.start()
        logger.info("Started Redis cleanup thread")

    def _monitor_workers(self):
        r"""Monitor worker processes and restart if needed."""
        while self.running:
            failed_workers = 0
            busy_workers = 0
            hanging_workers = 0

            for i, worker in enumerate(self.workers):
                if not worker.is_alive():
                    logger.error(f"Worker {worker.worker_id} died. Restarting...")

                    # Start a new worker with the same ID
                    new_worker = JudgeWorker(worker.worker_id)
                    new_worker.start()
                    self.workers[i] = new_worker
                    failed_workers += 1
                else:
                    # Check if worker is busy or hanging
                    try:
                        worker_process = psutil.Process(worker.pid)
                        is_busy = 0
                        is_hanging = 0

                        # Check all child processes
                        for child in worker_process.children(recursive=True):
                            is_busy = 1
                            # Check if process is hanging (running too long)
                            if (
                                child.is_running()
                                and time.time() - child.create_time()
                                > settings.MAX_TASK_EXECUTION_TIME
                            ):
                                is_hanging = 1
                                logger.warning(
                                    f"Worker {worker.worker_id} has a hanging child process."
                                )
                                child.kill()

                        busy_workers += is_busy
                        hanging_workers += is_hanging

                    except Exception as e:
                        logger.error(f"Failed to check worker {worker.worker_id}: {str(e)}")

            # Log worker status
            logger.info(
                f"Workers status - Total: {len(self.workers)}, "
                f"Free: {len(self.workers) - busy_workers}, "
                f"Failed: {failed_workers}, "
                f"Busy: {busy_workers}, "
                f"Hanging: {hanging_workers}"
            )

            # Sleep before next check
            time.sleep(settings.MONITOR_INTERVAL)

    def _run_recovery(self):
        r"""Run task recovery thread."""
        logger.info("Starting task recovery thread")

        while self.running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(recover_lost_tasks())
                loop.close()

            except Exception as e:
                logger.error(f"Recovery thread error: {str(e)}")

            time.sleep(settings.RECOVER_INTERVAL)

    def _run_cleanup(self):
        r"""Run Redis cleanup thread to periodically remove expired keys."""
        logger.info("Starting Redis cleanup thread")

        while self.running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(cleanup_expired_keys())
                loop.close()

            except Exception as e:
                logger.error(f"Cleanup thread error: {str(e)}")

            time.sleep(settings.CLEANUP_INTERVAL)

    def shutdown(self):
        r"""Shutdown all workers."""
        self.running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()
        logger.info("All workers terminated")
