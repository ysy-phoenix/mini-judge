import asyncio
from multiprocessing import Process

from app.core.config import settings
from app.models.schemas import Submission
from app.services.judge import process_judge_task
from app.utils.logger import logger
from app.utils.redis import get_redis


class JudgeWorker(Process):
    r"""Worker process for processing judge tasks from queue."""

    def __init__(self, worker_id: int):
        super().__init__(name=f"judge-worker-{worker_id}")
        self.worker_id = worker_id
        self.daemon = True

    async def _process_task(self, submission: Submission):
        try:
            result = await process_judge_task(submission)
            redis = await get_redis()
            await redis.rpush(
                f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}",
                result.model_dump_json(),
            )
        except Exception as e:
            logger.error(
                f"Worker {self.worker_id} process task error: [red]{submission.task_id}[/red] | "
                f"[red]{str(e)}[/red]"
            )

    async def _run_async_loop(self):
        r"""Async event loop for the worker."""
        redis = await get_redis()

        while True:
            try:
                # Block until we get a task
                _, data = await redis.blpop(settings.REDIS_SUBMISSION_QUEUE)
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
