import time

from app.core.config import settings
from app.utils.logger import logger
from app.utils.redis import RedisManager, RedisQueue
from app.workers.judge_worker import JudgeWorker
from app.workers.services import RedisCleanup, TaskRecovery, WorkerMonitor


class WorkerManager:
    r"""Manages a pool of worker processes and related services."""

    def __init__(self):
        self.workers: list[JudgeWorker] = []
        self.max_workers = settings.MAX_WORKERS
        self.running = False

    def start(self):
        self.running = True
        for i in range(self.max_workers):
            worker = JudgeWorker(i)
            worker.start()
            self.workers.append(worker)

        logger.info(f"All {self.max_workers} workers started")

        # Initialize service components
        self.worker_monitor = WorkerMonitor(self.workers, interval=settings.MONITOR_INTERVAL)
        self.worker_monitor.set_system_manager(self)  # Pass self reference
        self.task_recovery = TaskRecovery(interval=settings.RECOVER_INTERVAL)
        self.redis_cleanup = RedisCleanup(interval=settings.CLEANUP_INTERVAL)

        # Start all services
        self.worker_monitor.start()
        self.task_recovery.start()
        self.redis_cleanup.start()

    def shutdown(self):
        r"""Shut down all worker processes and services."""
        self.running = False
        logger.info("Shutting down worker manager...")

        # Stop all services
        self.worker_monitor.stop()
        self.task_recovery.stop()
        self.redis_cleanup.stop()

        # Simply kill all workers without any notification or cleanup
        for worker in self.workers:
            if worker.is_alive():
                try:
                    worker.kill()
                except Exception as e:
                    logger.error(f"Error killing worker {worker.worker_id}: {str(e)}")

        logger.info("Worker manager shutdown complete")

    async def restart_workers(self):
        await RedisManager.set(RedisQueue.RESTART, str(True))
        total_workers = len(self.workers)
        half_size = total_workers // 2
        if half_size == 0:
            half_size = 1

        logger.info(
            f"Starting worker restart: {total_workers} total workers, restarting in two phases"
        )

        self._restart_worker_section(0, half_size)
        time.sleep(0.2)
        self._restart_worker_section(half_size, total_workers)

        logger.info("All workers successfully restarted in two phases")
        await RedisManager.set(RedisQueue.RESTART, str(False))

    def _restart_worker_section(self, start_idx: int, end_idx: int):
        r"""Restart a section of workers in small batches."""
        batch = self.workers[start_idx:end_idx]
        logger.info(f"Restarting worker batch {start_idx} to {end_idx - 1}")

        for worker in batch:
            if worker.is_alive():
                try:
                    worker.terminate()
                except Exception as e:
                    logger.error(f"Error terminating worker {worker.worker_id}: {str(e)}")

        for worker in batch:
            if worker.is_alive():
                try:
                    worker.kill()
                except Exception:
                    logger.error(f"Error killing worker {worker.worker_id}")
                    pass

        for i, worker in enumerate(batch, start=start_idx):
            new_worker = JudgeWorker(worker.worker_id)
            new_worker.start()
            self.workers[i] = new_worker
