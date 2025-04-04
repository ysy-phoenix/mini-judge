import json
import threading
from enum import Enum
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings
from app.utils.logger import logger

# Use thread local storage
_local = threading.local()


class RedisQueue(Enum):
    SUBMISSIONS = "submissions"
    RESULTS = "results"
    WORKERS = "workers"
    TASKS = "tasks"
    PROCESSED = "processed"
    SUBMITTED = "submitted"
    FETCHED = "fetched"


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


class RedisManager:
    r"""Redis key name manager, for managing key name formats."""

    @staticmethod
    def queue(name: str, key: str = None) -> str:
        r"""Get the queue key name."""
        return f"{settings.REDIS_PREFIX}:{name}:{key}" if key else f"{settings.REDIS_PREFIX}:{name}"

    @staticmethod
    def pattern(name: str) -> str:
        r"""Get the pattern for all task keys."""
        return f"{settings.REDIS_PREFIX}:{name}:*"

    @staticmethod
    async def get_hash_fields(key: str, fields: list[str] = None) -> dict[str, Any]:
        r"""Get the values of one or more fields from a hash table."""
        redis = await get_redis()
        result = {}
        try:
            if not fields:
                fields = await redis.hkeys(key)
            values = await redis.hmget(key, fields)
            for field, value in zip(fields, values, strict=False):
                if value is not None:
                    try:
                        result[field] = value.decode("utf-8") if isinstance(value, bytes) else value
                    except (UnicodeDecodeError, AttributeError):
                        result[field] = value
            return result
        except Exception as e:
            logger.error(f"Failed to get fields from hash table {key}: {str(e)}")
            return {}

    @staticmethod
    async def push(queue: RedisQueue | str, data: str | dict | bytes) -> int | None:
        r"""Push data to a queue, automatically handle serialization."""
        if isinstance(queue, RedisQueue):
            queue = queue.value

        redis = await get_redis()
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            elif not isinstance(data, str | bytes):
                data = str(data)

            return await redis.rpush(queue, data)
        except Exception as e:
            logger.error(f"Failed to push data to queue {queue}: {str(e)}")
            return None

    @staticmethod
    async def get(queue: RedisQueue) -> str | None:
        r"""Get data from a queue."""
        redis = await get_redis()
        return await redis.get(queue.value)

    @staticmethod
    async def length(queue: RedisQueue) -> int:
        r"""Get the length of a queue."""
        redis = await get_redis()
        return await redis.llen(queue.value)

    @staticmethod
    async def keys(queue: RedisQueue) -> list[str]:
        r"""Get all keys that match a pattern."""
        redis = await get_redis()
        return await redis.keys(RedisManager.pattern(queue.value))

    @staticmethod
    async def scan(cursor: int, match: str, count: int = 1000) -> tuple[int, list[str]]:
        r"""Scan the database for keys that match a pattern."""
        redis = await get_redis()
        return await redis.scan(cursor, match=match, count=count)

    @staticmethod
    async def exists(key: str) -> bool:
        r"""Check if a key exists."""
        redis = await get_redis()
        return await redis.exists(key)

    @staticmethod
    async def delete(keys: list[str]) -> int:
        r"""Delete a list of keys."""
        redis = await get_redis()
        pipe = redis.pipeline()
        for key in keys:
            pipe.delete(key)
        return await pipe.execute()

    @staticmethod
    async def expire(key: str, seconds: int = settings.RESULT_EXPIRY_TIME) -> int:
        r"""Set the expiration time for a key."""
        redis = await get_redis()
        return await redis.expire(key, seconds)

    @staticmethod
    async def hset(key: str, mapping: dict[str, Any]) -> int:
        r"""Set the values of one or more fields in a hash table."""
        redis = await get_redis()
        return await redis.hset(key, mapping=mapping)

    @staticmethod
    async def incr(queue: RedisQueue) -> int:
        r"""Increment the value of a key."""
        redis = await get_redis()
        return await redis.incr(queue.value)

    @staticmethod
    async def pop(queue: RedisQueue | str, timeout: int = settings.MAX_LATENCY) -> tuple[str, str]:
        r"""Pop an item from a list, or block until one is available."""
        redis = await get_redis()
        return await redis.blpop(
            queue.value if isinstance(queue, RedisQueue) else queue, timeout=timeout
        )
