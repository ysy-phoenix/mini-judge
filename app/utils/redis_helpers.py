import json
from typing import Any, TypeVar

from app.core.config import settings
from app.utils.logger import logger
from app.utils.redis import get_redis

T = TypeVar("T")


async def batch_delete_keys(pattern: str) -> int:
    r"""Batch delete keys matching a specific pattern."""
    redis = await get_redis()
    cursor = 0
    deleted = 0

    try:
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=1000)
            if keys:
                pipe = redis.pipeline()
                for key in keys:
                    pipe.delete(key)
                await pipe.execute()
                deleted += len(keys)
            if cursor == 0:
                break

        if deleted > 0:
            logger.info(f"Deleted {deleted} keys, matching pattern: {pattern}")

        return deleted
    except Exception as e:
        logger.error(f"Error deleting keys, pattern: {pattern}: {str(e)}")
        return 0


async def execute_lua_or_fallback(lua_script: str, keys: int, *args):
    r"""Try to execute the Lua script, fallback to scanning method if failed."""
    redis = await get_redis()
    try:
        return await redis.eval(lua_script, keys, *args)
    except Exception as e:
        logger.warning(f"Lua script execution failed: {str(e)}, using scanning method instead")
        return None


async def redis_pipeline_operation(operations: list[tuple], error_message: str = "管道操作失败"):
    r"""Execute a group of Redis pipeline operations, handling errors."""

    """Example usage:
    operations = [
        ('set', 'key1', 'value1'),
        ('hset', 'hash1', 'field1', 'value1'),
    ]
    await redis_pipeline_operation(operations)
    """
    redis = await get_redis()
    pipe = redis.pipeline()

    try:
        # Add operations to the pipeline
        for op in operations:
            command, *args = op
            getattr(pipe, command)(*args)

        # Execute the pipeline operations
        return await pipe.execute()
    except Exception as e:
        logger.error(f"{error_message}: {str(e)}")
        return None


async def push_to_queue(queue_name: str, data: str | dict | bytes):
    r"""Push data to a queue, automatically handle serialization."""
    redis = await get_redis()

    try:
        if isinstance(data, dict):
            data = json.dumps(data)
        elif not isinstance(data, str | bytes):
            data = str(data)

        return await redis.rpush(queue_name, data)
    except Exception as e:
        logger.error(f"Failed to push data to queue {queue_name}: {str(e)}")
        return None


async def get_hash_fields(key: str, fields: list[str] = None) -> dict[str, Any]:
    r"""Get the values of one or more fields from a hash table."""
    redis = await get_redis()
    result = {}

    try:
        if fields:
            # Get specified fields
            values = await redis.hmget(key, fields)
            for field, value in zip(fields, values, strict=False):
                if value is not None:
                    try:
                        # Try decoding
                        result[field] = value.decode("utf-8") if isinstance(value, bytes) else value
                    except (UnicodeDecodeError, AttributeError):
                        result[field] = value
        else:
            # Get all fields
            all_values = await redis.hgetall(key)
            for field, value in all_values.items():
                field_name = field.decode("utf-8") if isinstance(field, bytes) else field
                try:
                    # Try decoding
                    result[field_name] = (
                        value.decode("utf-8") if isinstance(value, bytes) else value
                    )
                except (UnicodeDecodeError, AttributeError):
                    result[field_name] = value

        return result
    except Exception as e:
        logger.error(f"Failed to get fields from hash table {key}: {str(e)}")
        return {}


class RedisKeyManager:
    r"""Redis key name manager, for managing key name formats."""

    @staticmethod
    def task_key(task_id: str) -> str:
        r"""Get the task key name."""
        return f"{settings.REDIS_PREFIX}task:{task_id}"

    @staticmethod
    def result_queue_key(task_id: str) -> str:
        r"""Get the result queue key name."""
        return f"{settings.REDIS_RESULT_QUEUE}:{task_id}"

    @staticmethod
    def worker_key(worker_id: str) -> str:
        r"""Get the worker key name."""
        return f"{settings.REDIS_PREFIX}worker:{worker_id}"

    @staticmethod
    def counter_key(counter_name: str) -> str:
        r"""Get the counter key name."""
        return f"{settings.REDIS_PREFIX}counter:{counter_name}"

    @staticmethod
    def all_task_keys_pattern() -> str:
        r"""Get the pattern for all task keys."""
        return f"{settings.REDIS_PREFIX}task:*"

    @staticmethod
    def all_result_queue_keys_pattern() -> str:
        r"""Get the pattern for all result queue keys."""
        return f"{settings.REDIS_RESULT_QUEUE}:*"

    @staticmethod
    def all_worker_keys_pattern() -> str:
        r"""Get the pattern for all worker keys."""
        return f"{settings.REDIS_PREFIX}worker:*"
