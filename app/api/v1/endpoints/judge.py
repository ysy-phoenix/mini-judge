import time
import traceback

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import JudgeResult, JudgeStatus, Submission
from app.utils.logger import logger
from app.utils.redis import RedisManager, RedisQueue

router = APIRouter()


def handle_failed_result(failed: JudgeResult, error: Exception) -> JudgeResult:
    failed.error_message = str(error)
    logger.error(failed.error_message)
    return failed


@router.post("", response_model=JudgeResult)
async def create_judge_task(submission: Submission) -> JudgeResult:
    r"""Submit code for judging and wait for the result."""
    failed = JudgeResult(
        status=JudgeStatus.SYSTEM_ERROR,
        task_id=submission.task_id,
        metadata={
            "passed": 0,
            "total": len(submission.test_cases),
        },
    )
    key = RedisManager.queue(RedisQueue.TASKS, submission.task_id)

    # submit task to redis
    try:
        await RedisManager.hset(
            key,
            mapping={
                "status": JudgeStatus.PENDING,
                "submitted_at": time.time(),
                "data": submission.model_dump_json(),
            },
        )
        await RedisManager.expire(key, settings.RESULT_EXPIRY_TIME)
        await RedisManager.push(RedisQueue.SUBMISSIONS, submission.model_dump_json())
        await RedisManager.incr(RedisQueue.SUBMITTED)
    except Exception as e:
        logger.error(traceback.format_exc())
        return handle_failed_result(failed, e)

    # wait for result
    try:
        result = await RedisManager.pop(
            RedisManager.queue(RedisQueue.RESULTS, submission.task_id),
        )

        if result is None:
            task_status = await RedisManager.get_hash_fields(key, ["status"])
            if task_status == JudgeStatus.PENDING:
                failed.error_message = "Judge timeout. Task still pending."
            elif task_status is None:
                failed.error_message = f"Task information not found. Task ID: {submission.task_id}"
            else:
                failed.error_message = (
                    f"Task was in status {task_status} but no result was available."
                )
            logger.warning(failed.error_message)
            return failed

        # Normal case, unpack result
        _, result_data = result

    except Exception as e:
        logger.error(traceback.format_exc())
        return handle_failed_result(failed, e)

    try:
        # Clean up result and task status
        await RedisManager.delete([key])
        return JudgeResult.model_validate_json(result_data)
    except Exception as e:
        logger.error(traceback.format_exc())
        return handle_failed_result(failed, e)
