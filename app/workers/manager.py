import threading
import time

import psutil

from app.core.config import settings
from app.utils.logger import logger
from app.workers.judge_worker import JudgeWorker

INTERVAL = 120


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

    def shutdown(self):
        """Shutdown all workers"""
        self.running = False
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()

        # Wait for all workers to terminate
        for worker in self.workers:
            worker.join(timeout=5)
