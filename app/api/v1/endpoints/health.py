from fastapi import APIRouter

from app.core.config import settings
from app.utils.redis import get_redis

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


@router.get("/queue")
async def queue_status():
    r"""Get submission queue status."""
    try:
        redis = await get_redis()

        pending_count = await redis.llen(settings.REDIS_SUBMISSION_QUEUE)

        processed_count = await redis.get(settings.REDIS_PROCESSED_COUNT)
        processed_count = int(processed_count) if processed_count else 0
        submitted_count = await redis.get(settings.REDIS_SUBMITTED_COUNT)
        submitted_count = int(submitted_count) if submitted_count else 0
        fetched_count = await redis.get(settings.REDIS_FETCHED_COUNT)
        fetched_count = int(fetched_count) if fetched_count else 0
        return {
            "pending": pending_count,
            "fetched": fetched_count,
            "processed": processed_count,
            "submitted": submitted_count,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
