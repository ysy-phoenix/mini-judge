import time

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.utils.logger import logger
from app.utils.redis import get_redis

router = APIRouter()


@router.post("", response_model=JudgeResult)
async def create_judge_task(submission: Submission) -> JudgeResult:
    r"""Submit code for judging and wait for the result."""
    try:
        redis = await get_redis()

        # Record task submission time and status
        task_key = f"{settings.REDIS_PREFIX}task:{submission.task_id}"
        await redis.hset(
            task_key,
            mapping={
                "status": JudgeStatus.PENDING,
                "submitted_at": time.time(),
                "code_hash": hash(submission.code),
                "data": submission.model_dump_json(),
            },
        )
        await redis.expire(task_key, settings.RESULT_EXPIRY_TIME)

        # Submit task to queue
        await redis.rpush(f"{settings.REDIS_SUBMISSION_QUEUE}", submission.model_dump_json())
        await redis.incr(settings.REDIS_SUBMITTED_COUNT)
    except Exception as e:
        logger.error(f"Error pushing submission to Redis: {str(e)}")
        return JudgeResult(
            status=JudgeStatus.SYSTEM_ERROR, error_message=str(e), task_id=submission.task_id
        )

    try:
        # Wait for result, add a little extra timeout
        timeout = settings.MAX_LATENCY
        result = await redis.blpop(
            f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}", timeout=timeout
        )

        if result is None:
            # Result timeout, check task status
            task_status = await redis.hget(task_key, "status")
            task_status = task_status.decode("utf-8") if task_status else None

            if task_status == JudgeStatus.PENDING:
                # Task still pending
                return JudgeResult(
                    status=JudgeStatus.SYSTEM_ERROR,
                    error_message=f"Judge timeout after {timeout} seconds. Task still pending.",
                    task_id=submission.task_id,
                )
            elif task_status is None:
                # Task information expired or not found
                return JudgeResult(
                    status=JudgeStatus.SYSTEM_ERROR,
                    error_message="Task information not found.",
                    task_id=submission.task_id,
                )
            else:
                # Task has status but result is lost
                return JudgeResult(
                    status=JudgeStatus.SYSTEM_ERROR,
                    error_message=f"Task was in status {task_status} but no result was available.",
                    task_id=submission.task_id,
                )

        # Normal case, unpack result
        _, result_data = result

    except Exception as e:
        logger.error(f"Error popping result from Redis: {str(e)}")
        return JudgeResult(
            status=JudgeStatus.SYSTEM_ERROR, error_message=str(e), task_id=submission.task_id
        )

    try:
        # Clean up result and task status
        pipe = redis.pipeline(transaction=True)
        pipe.delete(f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}")
        pipe.delete(task_key)
        await pipe.execute()
        return JudgeResult.model_validate_json(result_data)
    except Exception as e:
        logger.error(f"Error after processing result: {str(e)}")
        return JudgeResult(
            status=JudgeStatus.SYSTEM_ERROR, error_message=str(e), task_id=submission.task_id
        )
