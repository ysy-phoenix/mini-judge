import json
from typing import Any

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


async def set_task(task_id: str, data: dict[str, Any], ttl: int = 3600) -> None:
    r"""Store task data in Redis with expiration time."""
    redis_conn = await get_redis()
    key = f"{settings.REDIS_PREFIX}task:{task_id}"
    await redis_conn.set(key, json.dumps(data), ex=ttl)


async def get_task(task_id: str) -> dict[str, Any] | None:
    r"""Retrieve task data from Redis."""
    redis_conn = await get_redis()
    key = f"{settings.REDIS_PREFIX}task:{task_id}"
    data = await redis_conn.get(key)
    if data:
        return json.loads(data)
    return None


async def add_to_queue(queue_name: str, task_id: str) -> None:
    r"""Add task to a Redis queue."""
    redis_conn = await get_redis()
    key = f"{settings.REDIS_PREFIX}queue:{queue_name}"
    await redis_conn.lpush(key, task_id)


async def get_from_queue(queue_name: str) -> str | None:
    r"""Get a task from a Redis queue."""
    redis_conn = await get_redis()
    key = f"{settings.REDIS_PREFIX}queue:{queue_name}"
    task = await redis_conn.rpop(key)
    if task:
        return task.decode("utf-8")
    return None
