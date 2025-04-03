from app.core.config import settings
from app.utils.logger import logger
from app.workers.judge_worker import JudgeWorker
from app.workers.services import RedisCleanup, TaskRecovery, WorkerMonitor


class WorkerManager:
    r"""Manages a pool of worker processes and related services."""

    def __init__(self):
        self.workers = []
        self.running = True

        # Create worker processes
        max_workers = settings.MAX_WORKERS
        for i in range(max_workers):
            worker = JudgeWorker(i)
            worker.start()
            self.workers.append(worker)

        logger.info(f"All {max_workers} workers started")

        # Initialize service components
        self.worker_monitor = WorkerMonitor(self.workers)
        self.task_recovery = TaskRecovery()
        self.redis_cleanup = RedisCleanup()

        # Start all services
        self.worker_monitor.start()
        self.task_recovery.start()
        self.redis_cleanup.start()
