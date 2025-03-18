import uuid

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import JudgeResult, Submission
from app.utils.logger import logger
from app.utils.redis import get_redis

router = APIRouter()

MAX_WAIT_TIME = 60  # seconds


@router.post("", response_model=JudgeResult)
async def create_judge_task(submission: Submission) -> JudgeResult:
    """Submit code for judging and wait for the result (using worker pool)"""
    try:
        if submission.task_id is None:
            submission.task_id = str(uuid.uuid4())
        redis = await get_redis()
        await redis.rpush(f"{settings.REDIS_SUBMISSION_QUEUE}", submission.model_dump_json())
        _, result = await redis.blpop(
            f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}", timeout=MAX_WAIT_TIME
        )
        await redis.delete(f"{settings.REDIS_RESULT_QUEUE}:{submission.task_id}")
        return JudgeResult.model_validate_json(result)

    except Exception as e:
        logger.error(f"Error processing judge task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
