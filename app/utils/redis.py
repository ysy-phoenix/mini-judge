import redis.asyncio as redis

from app.core.config import settings

redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    r"""Get Redis client instance."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        )
    return redis_client


async def close_redis():
    r"""Close Redis connection."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
