import threading

from redis.asyncio import Redis

from app.core.config import settings

# Use thread local storage
_local = threading.local()


async def get_redis():
    r"""Get Redis connection, create a new connection for each thread/event loop."""
    # Try to get from current thread local storage
    if not hasattr(_local, "redis_client"):
        _local.redis_client = None

    if _local.redis_client is None:
        # Create a new connection
        _local.redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=False,  # Keep raw byte format
        )

    return _local.redis_client


async def close_redis():
    r"""Close the Redis connection for the current thread."""
    if hasattr(_local, "redis_client") and _local.redis_client is not None:
        await _local.redis_client.close()
        _local.redis_client = None
