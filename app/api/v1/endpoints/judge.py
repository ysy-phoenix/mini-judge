import uuid

from fastapi import APIRouter, HTTPException

from app.models.schemas import JudgeRequest, JudgeResponse, JudgeStatus
from app.services.judge import process_judge_task_direct
from app.utils.logger import log_with_context
from app.utils.redis import add_to_queue, get_result, get_task, set_task

router = APIRouter()


@router.post("", response_model=JudgeResponse)
async def create_judge_task(request: JudgeRequest) -> JudgeResponse:
    """Submit code for judging and wait for the result"""
    try:
        result = await process_judge_task_direct(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/async", response_model=JudgeResponse)
async def create_async_judge_task(request: JudgeRequest) -> JudgeResponse:
    """Submit code for judging asynchronously"""
    try:
        task_id = str(uuid.uuid4())
        await set_task(task_id, request.model_dump())
        await add_to_queue("judge_tasks", task_id)
        log_with_context("Task queued for async processing", {"task_id": task_id})
        return JudgeResponse(status=JudgeStatus.PENDING, task_id=task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{task_id}", response_model=JudgeResponse)
async def get_judge_result(task_id: str) -> JudgeResponse:
    """Get the result of the judging task"""
    try:
        result_data = await get_result(task_id)
        if result_data:
            return JudgeResponse(**result_data)
        task_data = await get_task(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
        return JudgeResponse(status=JudgeStatus.PENDING, task_id=task_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
