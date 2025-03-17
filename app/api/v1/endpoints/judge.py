from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.schemas import JudgeRequest, JudgeResponse, JudgeStatus
from app.services.judge import judge_submission, process_judge_task
from app.utils.logger import log_with_context
from app.utils.redis import get_task

router = APIRouter()


@router.post("", response_model=JudgeResponse)
async def create_judge_task(request: JudgeRequest) -> JudgeResponse:
    r"""Submit code for judging and wait for results."""
    try:
        # Queue the judge task and get task ID
        pending_response = await judge_submission(request)
        task_id = pending_response.task_id

        log_with_context("Processing task synchronously", {"task_id": task_id})

        # Process the task immediately (not in background)
        result = await process_judge_task(task_id)

        # Check for completion - in case something went wrong and status is still pending
        if result.status == JudgeStatus.PENDING:
            raise HTTPException(
                status_code=500, detail="Judging process did not complete within expected time"
            )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/async", response_model=JudgeResponse)
async def create_async_judge_task(
    request: JudgeRequest, background_tasks: BackgroundTasks
) -> JudgeResponse:
    r"""Submit code for judging asynchronously (original behavior)."""
    try:
        # Queue the judge task and return task ID
        response = await judge_submission(request)

        # Process the task in the background
        background_tasks.add_task(process_judge_task, response.task_id)

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{task_id}", response_model=JudgeResponse)
async def get_judge_result(task_id: str) -> JudgeResponse:
    """
    Get the result of a judge task
    """
    try:
        # Try to get the task result from Redis
        task_data = await get_task(task_id)

        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

        # If task has results, return them
        if "status" in task_data and task_data["status"] != JudgeStatus.PENDING:
            return JudgeResponse(**task_data)

        # Task is still being processed
        return JudgeResponse(status=JudgeStatus.PENDING, task_id=task_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
