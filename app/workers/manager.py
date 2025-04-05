from app.core.config import settings
from app.utils.logger import logger
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
        self.worker_monitor = WorkerMonitor(self.workers)
        self.task_recovery = TaskRecovery()
        self.redis_cleanup = RedisCleanup()

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
