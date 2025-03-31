import asyncio
from multiprocessing import Process

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
        """Check and handle resource throttling based on system load."""
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

    async def _run_async_loop(self):
        r"""Async event loop for the worker."""
        redis = await get_redis()

        while True:
            try:
                # Check resource utilization before processing
                if await self._check_and_handle_resource_throttling(redis):
                    continue  # Skip to next iteration if we're throttling

                # Block until we get a task, with a timeout so we can check resources periodically
                result = await redis.blpop(
                    settings.REDIS_SUBMISSION_QUEUE, timeout=settings.RESOURCE_CHECK_INTERVAL
                )

                if result is None:
                    # No task available or timeout, loop and check resources again
                    continue

                _, data = result
                await redis.incr(settings.REDIS_FETCHED_COUNT)
                submission = Submission.model_validate_json(data)
                await self._process_task(submission)
            except Exception as e:
                logger.error(f"Worker {self.worker_id} loop error: [red]{str(e)}[/red]")
                # Sleep to avoid tight error loops
                await asyncio.sleep(1)

    def run(self):
        r"""Main process entry point."""
        # Create a new event loop for this process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the async loop
        try:
            loop.run_until_complete(self._run_async_loop())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()


# curl http://localhost:8000/api/v1/health/queue
