from fastapi import APIRouter

from app.core.config import settings
from app.utils.redis import get_redis
from app.utils.resource_monitor import ResourceMonitor

router = APIRouter()


@router.get("")
async def health_check():
    r"""Health check endpoint."""
    return {"status": "healthy"}


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
        redis = await get_redis()

        queue_length = await redis.llen(settings.REDIS_SUBMISSION_QUEUE)
        processed = int(await redis.get(settings.REDIS_PROCESSED_COUNT) or 0)
        submitted = int(await redis.get(settings.REDIS_SUBMITTED_COUNT) or 0)
        cpu_usage = ResourceMonitor.get_cpu_usage()
        memory_usage = ResourceMonitor.get_memory_usage()

        return {
            "status": "ok",
            "queue_length": queue_length,
            "processed_tasks": processed,
            "submitted_tasks": submitted,
            "backlog": submitted - processed,
            "system": {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
