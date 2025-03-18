import asyncio
import json
from multiprocessing import Process

from app.core.config import settings
from app.models.schemas import JudgeRequest
from app.services.judge import process_judge_task_direct
from app.utils.logger import log_with_context
from app.utils.redis import get_redis


class JudgeWorker(Process):
    """Worker process for processing judge tasks from queue"""

    def __init__(self, worker_id: int):
        super().__init__(name=f"judge-worker-{worker_id}")
        self.worker_id = worker_id
        self.daemon = True

    async def _process_task(self, task_id: str, task_data: dict):
        try:
            # Convert to JudgeRequest
            request = JudgeRequest(**task_data)

            # Process directly
            result = await process_judge_task_direct(request, task_id)

            # Store result in Redis
            redis = await get_redis()
            result_key = f"{settings.REDIS_PREFIX}result:{task_id}"
            await redis.set(
                result_key, json.dumps(result.model_dump()), ex=settings.RESULT_EXPIRY_TIME
            )

            log_with_context(
                f"Worker {self.worker_id} completed task",
                {"task_id": task_id, "status": result.status.value},
            )

        except Exception as e:
            log_with_context(
                f"Worker {self.worker_id} failed to process task",
                {"task_id": task_id, "error": str(e)},
                level="error",
            )

    async def _run_async_loop(self):
        """Async event loop for the worker"""
        redis = await get_redis()
        log_with_context(f"Worker {self.worker_id} started", {})

        while True:
            try:
                # Block until we get a task
                queue_key = f"{settings.REDIS_PREFIX}queue:judge_tasks"
                task = await redis.blpop(queue_key, timeout=1)

                if task:
                    _, task_id = task
                    task_id = task_id.decode("utf-8")

                    # Get task data
                    task_key = f"{settings.REDIS_PREFIX}task:{task_id}"
                    task_data = await redis.get(task_key)

                    if task_data:
                        task_data = json.loads(task_data)
                        # Process the task
                        await self._process_task(task_id, task_data)
                    else:
                        log_with_context(
                            f"Worker {self.worker_id} found missing task data",
                            {"task_id": task_id},
                            level="error",
                        )

            except Exception as e:
                log_with_context(
                    f"Worker {self.worker_id} loop error", {"error": str(e)}, level="error"
                )
                # Sleep to avoid tight error loops
                await asyncio.sleep(1)

    def run(self):
        """Main process entry point"""
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
