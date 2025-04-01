import asyncio
import shutil
import signal
from contextlib import asynccontextmanager
from multiprocessing import Process
from pathlib import Path

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.services.judge import process_judge_task
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.utils.resource_monitor import ResourceMonitor


class JudgeWorker(Process):
    r"""Worker process for processing judge tasks from queue."""

    def __init__(self, worker_id: int):
        super().__init__(name=f"judge-worker-{worker_id}")
        self.worker_id = worker_id
        self.daemon = True
        self.throttled = False
        self.shutdown_event = asyncio.Event()
        self.current_task: asyncio.Task | None = None
        self.current_submission: Submission | None = None

    async def _process_task(self, submission: Submission):
        redis = await get_redis()
        task_key = f"{settings.REDIS_PREFIX}task:{submission.task_id}"

        try:
            # Update task status to running
            await redis.hset(task_key, "status", JudgeStatus.RUNNING)
            await redis.expire(task_key, settings.RESULT_EXPIRY_TIME)

            # Process task
            result = await process_judge_task(submission)

            # Save result and update status
            await redis.rpush(
                f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}",
                result.model_dump_json(),
            )

            # Increment processed count
            await redis.incr(settings.REDIS_PROCESSED_COUNT)
        except Exception as e:
            logger.error(
                f"Worker {self.worker_id} process task error: [red]{submission.task_id}[/red] | "
                f"[red]{str(e)}[/red]"
            )

            # Even if there is an error, provide a result to avoid client permanent waiting
            error_result = JudgeResult(
                status=JudgeStatus.SYSTEM_ERROR, error_message=str(e), task_id=submission.task_id
            )
            await redis.rpush(
                f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}",
                error_result.model_dump_json(),
            )

    async def _check_and_handle_resource_throttling(self, redis):
        r"""Check and handle resource throttling based on system load."""
        # If we're already throttled, check if we can resume
        if self.throttled:
            if ResourceMonitor.can_resume():
                logger.info(
                    f"Worker {self.worker_id} resuming task processing as system load is now normal"
                )
                self.throttled = False
            else:
                # Still in high load, sleep and check again later
                await asyncio.sleep(settings.RESOURCE_CHECK_INTERVAL)
                return True  # Keep throttling
        # Otherwise, check if we need to start throttling
        elif ResourceMonitor.should_throttle():
            logger.warning(
                f"Worker {self.worker_id} throttling task processing due to high system load"
            )
            self.throttled = True
            await asyncio.sleep(settings.RESOURCE_CHECK_INTERVAL)
            return True  # Start throttling

        return False  # No throttling needed

    async def _cleanup_resources(self):
        r"""Clean up any resources used by the worker"""
        try:
            # Clean up temporary files
            worker_tmp_dir = Path(f"{settings.CODE_EXECUTION_DIR}/worker_{self.worker_id}")
            if worker_tmp_dir.exists():
                shutil.rmtree(worker_tmp_dir, ignore_errors=True)

            # Clean up Redis keys
            redis = await get_redis()
            state_key = f"{settings.REDIS_PREFIX}:worker:{self.worker_id}:state"
            await redis.delete(state_key)

            # Clear any other worker-specific data
            if self.current_submission:
                task_key = f"{settings.REDIS_PREFIX}task:{self.current_submission.task_id}"
                # Only clear if it's still in RUNNING state (not completed)
                task_status = await redis.hget(task_key, "status")
                if task_status and task_status.decode() == JudgeStatus.RUNNING:
                    # Mark as system error instead of leaving in running state
                    await redis.hset(task_key, "status", JudgeStatus.SYSTEM_ERROR)

                    # Add error result to ensure client gets a response
                    error_result = JudgeResult(
                        status=JudgeStatus.SYSTEM_ERROR,
                        error_message="Task discarded during system shutdown",
                        task_id=self.current_submission.task_id,
                    )
                    await redis.rpush(
                        f"{settings.REDIS_RESULT_QUEUE}:{self.current_submission.task_id}",
                        error_result.model_dump_json(),
                    )

        except Exception as e:
            logger.error(f"Worker {self.worker_id} cleanup error: {str(e)}")

    @asynccontextmanager
    async def task_context(self, submission: Submission):
        r"""Context manager for task execution with proper cleanup"""
        self.current_submission = submission
        try:
            yield
        finally:
            self.current_submission = None

    async def shutdown(self):
        r"""Graceful shutdown handling"""
        # Set shutdown event
        self.shutdown_event.set()

        # Handle current task
        if self.current_task and not self.current_task.done():
            try:
                # Wait for current task to complete
                await asyncio.wait_for(self.current_task, timeout=settings.TASK_COMPLETION_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker {self.worker_id} timeout waiting for task completion - discarding task"
                )

                # Cancel the task without saving state
                self.current_task.cancel()
                try:
                    await self.current_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error during task completion: {str(e)}")

        # Cleanup phase
        try:
            await asyncio.wait_for(
                self._cleanup_resources(), timeout=settings.SHUTDOWN_CLEANUP_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Worker {self.worker_id} cleanup timeout")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} cleanup error: {str(e)}")

    async def _run_async_loop(self):
        r"""Enhanced async event loop with shutdown handling"""
        redis = await get_redis()

        while not self.shutdown_event.is_set():
            try:
                # Use shorter timeout during shutdown
                timeout = 1 if self.shutdown_event.is_set() else None

                # Get task with timeout
                result = await redis.blpop(settings.REDIS_SUBMISSION_QUEUE, timeout=timeout)

                if result is None:
                    continue

                _, data = result
                await redis.incr(settings.REDIS_FETCHED_COUNT)
                submission = Submission.model_validate_json(data)

                # Process task with context manager
                async with self.task_context(submission):
                    self.current_task = asyncio.create_task(self._process_task(submission))
                    await self.current_task

            except Exception as e:
                logger.error(f"Worker {self.worker_id} loop error: {str(e)}")
                await asyncio.sleep(1)

    def run(self):
        r"""Enhanced main process entry point with signal handling"""
        # Set up signal handlers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def handle_shutdown_signal(signum, frame):
            # Schedule shutdown in event loop
            loop.call_soon_threadsafe(lambda: asyncio.create_task(self.shutdown()))

        # Register signal handlers
        signal.signal(signal.SIGTERM, handle_shutdown_signal)
        signal.signal(signal.SIGINT, handle_shutdown_signal)

        try:
            loop.run_until_complete(self._run_async_loop())
        except KeyboardInterrupt:
            logger.info(f"Worker {self.worker_id} received keyboard interrupt")
        finally:
            # Ensure shutdown is called
            loop.run_until_complete(self.shutdown())
            loop.close()


# curl http://localhost:8000/api/v1/health/queue
