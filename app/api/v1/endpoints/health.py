from fastapi import APIRouter

from app.utils.redis import RedisManager, RedisQueue, get_redis

router = APIRouter()


@router.get("")
async def health_check():
    r"""Health check endpoint."""
    return {"status": "healthy"}


@router.post("/restart")
async def restart():
    r"""Restart the worker manager."""
    await RedisManager.set(RedisQueue.RESTART, str(True))
    return {"status": "restarting"}


@router.get("/restart")
async def restart_status():
    r"""Get the restart status."""
    restart_status = await RedisManager.get(RedisQueue.RESTART)
    restart_status = (
        False if restart_status is None or restart_status.decode("utf-8") != "True" else True
    )
    return {"restart": restart_status}


@router.get("/redis")
async def redis_health_check():
    r"""Check Redis connection health."""
    try:
        redis = await get_redis()
        ping_result = await redis.ping()
        if ping_result:
            return {"status": "healthy", "redis": "connected"}
        return {"status": "unhealthy", "redis": "not responding"}
    except Exception as e:
        return {"status": "unhealthy", "redis": str(e)}


@router.get("/detail")
async def detail():
    r"""Get submission queue status."""
    try:
        submissions_length = await RedisManager.length(RedisQueue.SUBMISSIONS)
        tasks_length = await RedisManager.count(RedisQueue.TASKS)
        results_length = await RedisManager.count(RedisQueue.RESULTS)
        submitted = int(await RedisManager.get(RedisQueue.SUBMITTED) or 0)
        fetched = int(await RedisManager.get(RedisQueue.FETCHED) or 0)
        processed = int(await RedisManager.get(RedisQueue.PROCESSED) or 0)

        return {
            "status": "ok",
            "submissions_length": submissions_length,
            "tasks_length": tasks_length,
            "results_length": results_length,
            "submitted_tasks": submitted,
            "fetched_tasks": fetched,
            "processed_tasks": processed,
            "backlog": submitted - processed,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
