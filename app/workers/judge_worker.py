import asyncio
import os
import signal
from multiprocessing import Process

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.services.judge import process_judge_task
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.utils.redis_helpers import RedisKeyManager


class JudgeWorker(Process):
    r"""Worker process for processing judge tasks from queue."""

    def __init__(self, worker_id: int):
        super().__init__(name=f"judge-worker-{worker_id}")
        self.worker_id = worker_id

    async def _process_task(self, submission: Submission):
        redis = await get_redis()
        task_key = RedisKeyManager.task_key(submission.task_id)

        try:
            await redis.hset(task_key, "status", JudgeStatus.RUNNING)
            await redis.expire(task_key, settings.RESULT_EXPIRY_TIME)
            result = await process_judge_task(submission)
            await redis.rpush(
                RedisKeyManager.result_queue_key(submission.task_id),
                result.model_dump_json(),
            )
            await redis.incr(settings.REDIS_PROCESSED_COUNT)
        except Exception as e:
            logger.error(
                f"Worker {self.worker_id} process task error: [red]{submission.task_id}[/red] | "
                f"[red]{str(e)}[/red]"
            )
            error_result = JudgeResult(
                status=JudgeStatus.SYSTEM_ERROR, error_message=str(e), task_id=submission.task_id
            )
            await redis.rpush(
                RedisKeyManager.result_queue_key(submission.task_id),
                error_result.model_dump_json(),
            )

    async def _run_async_loop(self):
        r"""Simplified async event loop for task processing."""
        redis = await get_redis()

        try:
            while True:
                try:
                    timeout = 1
                    result = await redis.blpop(settings.REDIS_SUBMISSION_QUEUE, timeout=timeout)
                    if result is None:
                        continue
                    _, data = result
                    await redis.incr(settings.REDIS_FETCHED_COUNT)
                    submission = Submission.model_validate_json(data)
                    await asyncio.create_task(self._process_task(submission))
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error: {str(e)}")
                    await asyncio.sleep(1)
        finally:
            pass

    def run(self):
        r"""Main process entry point with simplified signal handling."""

        def handle_signal(signum, frame):
            os._exit(0)

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async_loop())
        except Exception as e:
            logger.error(f"Worker {self.worker_id} error: {str(e)}")
        finally:
            os._exit(0)
