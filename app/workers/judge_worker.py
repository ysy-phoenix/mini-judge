import asyncio
import signal
from multiprocessing import Process

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.services.judge import process_judge_task
from app.utils.logger import logger
from app.utils.redis import RedisManager, RedisQueue


class JudgeWorker(Process):
    r"""Worker process for processing judge tasks from queue."""

    def __init__(self, worker_id: int):
        super().__init__(name=f"judge-worker-{worker_id}", daemon=True)
        self.worker_id = worker_id
        self.running = True

    async def process_task(self, submission: Submission):
        task_key = RedisManager.queue(RedisQueue.TASKS, submission.task_id)

        try:
            await RedisManager.hset(task_key, {"status": JudgeStatus.RUNNING})
            await RedisManager.expire(task_key, settings.RESULT_EXPIRY_TIME)
            result = await process_judge_task(submission)
            await RedisManager.push(
                RedisManager.queue(RedisQueue.RESULTS, submission.task_id),
                result.model_dump_json(),
            )
            await RedisManager.incr(RedisQueue.PROCESSED)
        except Exception as e:
            error_result = JudgeResult(
                status=JudgeStatus.SYSTEM_ERROR,
                error_message=str(e),
                task_id=submission.task_id,
                metadata={
                    "passed": 0,
                    "total": len(submission.test_cases),
                },
            )
            try:
                await RedisManager.push(
                    RedisManager.queue(RedisQueue.RESULTS, submission.task_id),
                    error_result.model_dump_json(),
                )
            except Exception as e:
                logger.error(f"Error storing error result: {str(e)}")

    async def work(self):
        r"""Simplified async event loop for task processing."""
        try:
            while self.running:
                try:
                    result = await RedisManager.pop(RedisQueue.SUBMISSIONS, timeout=1)
                    if not result:
                        continue
                    _, data = result
                    await RedisManager.incr(RedisQueue.FETCHED)
                    submission = Submission.model_validate_json(data)
                    await self.process_task(submission)
                except Exception as e:
                    logger.error(f"Error processing task: {str(e)}")
                    await asyncio.sleep(1)
        finally:
            pass

    def run(self):
        r"""Main process entry point with minimal shutdown handling."""
        self.loop = None

        def handle_signal(signum, frame):
            self.running = False

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.work())
        except Exception as e:
            if not self.running or "Event loop stopped" in str(e):
                pass
            else:
                logger.error(f"Error in worker {self.worker_id}: {str(e)}")
        finally:
            if self.loop and self.loop.is_running():
                self.loop.stop()
            self.running = False

    async def shutdown_gracefully(self):
        r"""Perform graceful shutdown of async operations."""
        logger.debug(f"Worker {self.worker_id} shutting down gracefully")

        await asyncio.sleep(0.5)

        if self.loop:
            self.loop.stop()
