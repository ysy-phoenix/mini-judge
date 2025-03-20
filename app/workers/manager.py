import asyncio
import threading
import time

import psutil

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.workers.judge_worker import JudgeWorker

INTERVAL = 120


async def recover_lost_tasks():
    r"""Recover lost tasks."""
    redis = await get_redis()

    try:
        task_keys = await redis.keys(f"{settings.REDIS_PREFIX}task:*")
        now = time.time()
        recovered = 0
        logger.info(f"Recovering {len(task_keys)} tasks")
        for key in task_keys:
            try:
                pipe = redis.pipeline()
                pipe.hget(key, "status")
                pipe.hget(key, "submitted_at")
                status, submitted_at = await pipe.execute()

                status = status.decode("utf-8") if status else None
                submitted_at = float(submitted_at) if submitted_at else None

                task_id = key.decode("utf-8").split(":")[-1]
                if status == JudgeStatus.PENDING and submitted_at and now - submitted_at > 10:
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
        logger.info("Redis connection closed")


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
            time.sleep(INTERVAL)

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

            time.sleep(5)

    def shutdown(self):
        r"""Shutdown all workers."""
        self.running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()

        # Wait for all workers to terminate
        for worker in self.workers:
            worker.join(timeout=5)
