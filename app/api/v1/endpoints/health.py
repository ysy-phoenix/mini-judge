from fastapi import APIRouter

from app.utils.redis import get_redis

router = APIRouter()


@router.get("")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}


@router.get("/redis")
async def redis_health_check():
    """
    Check Redis connection health
    """
    try:
        redis = await get_redis()
        ping_result = await redis.ping()
        if ping_result:
            return {"status": "healthy", "redis": "connected"}
        return {"status": "unhealthy", "redis": "not responding"}
    except Exception as e:
        return {"status": "unhealthy", "redis": str(e)}
