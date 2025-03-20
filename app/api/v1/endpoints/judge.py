from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.utils.logger import logger
from app.utils.redis import get_redis

router = APIRouter()

MAX_WAIT_TIME = 60  # seconds


@router.post("", response_model=JudgeResult)
async def create_judge_task(submission: Submission) -> JudgeResult:
    r"""Submit code for judging and wait for the result."""
    try:
        redis = await get_redis()
        await redis.rpush(f"{settings.REDIS_SUBMISSION_QUEUE}", submission.model_dump_json())
    except Exception as e:
        logger.error(f"Error pushing submission to Redis: {str(e)}")
        return JudgeResult(status=JudgeStatus.SYSTEM_ERROR, error_message=str(e))

    try:
        _, result = await redis.blpop(
            f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}", timeout=MAX_WAIT_TIME
        )
    except Exception as e:
        logger.error(f"Error popping result from Redis: {str(e)}")
        return JudgeResult(status=JudgeStatus.SYSTEM_ERROR, error_message=str(e))

    try:
        await redis.delete(f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}")
        return JudgeResult.model_validate_json(result)
    except Exception as e:
        logger.error(f"Error deleting result from Redis: {str(e)}")
        return JudgeResult(status=JudgeStatus.SYSTEM_ERROR, error_message=str(e))
