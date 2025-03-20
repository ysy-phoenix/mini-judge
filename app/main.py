from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import logger
from app.utils.redis import close_redis, get_redis
from app.workers.manager import WorkerManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting", {"version": settings.VERSION})

    # Initialize Redis on startup
    redis = await get_redis()
    logger.info(
        "Redis connection established", {"host": settings.REDIS_HOST, "port": settings.REDIS_PORT}
    )

    # Perform full cleanup
    await reset_redis_state(redis)

    worker_manager = WorkerManager()
    yield

    logger.info("Application shutting down")

    worker_manager.shutdown()

    await close_redis()
    logger.info("Redis connection closed")


async def reset_redis_state(redis):
    r"""Reset all Redis state, including counters, task status, and queues."""

    # 1. Reset counters
    counters = [
        settings.REDIS_PROCESSED_COUNT,
        settings.REDIS_SUBMITTED_COUNT,
        settings.REDIS_FETCHED_COUNT,
    ]

    pipe = redis.pipeline()
    for counter in counters:
        pipe.set(counter, 0)
    await pipe.execute()

    # 2. Clear the main queue
    await redis.delete(settings.REDIS_SUBMISSION_QUEUE)

    # 3. Delete all task states
    try:
        task_delete_script = """
        local keys = redis.call('keys', ARGV[1])
        local count = 0
        if #keys > 0 then
            count = redis.call('del', unpack(keys))
        end
        return count
        """

        task_count = await redis.eval(task_delete_script, 0, f"{settings.REDIS_PREFIX}task:*")
        logger.info(f"Deleted {task_count} task keys")
    except Exception as e:
        logger.warning(f"Task deletion script failed: {str(e)}, using scan")

        cursor = 0
        task_count = 0
        while True:
            cursor, keys = await redis.scan(
                cursor, match=f"{settings.REDIS_PREFIX}task:*", count=1000
            )
            if keys:
                pipe = redis.pipeline()
                for key in keys:
                    pipe.delete(key)
                await pipe.execute()
                task_count += len(keys)

            if cursor == 0:
                break

        logger.info(f"Deleted {task_count} task keys using scan")

    # 4. Delete all result queues
    try:
        result_delete_script = """
        local keys = redis.call('keys', ARGV[1])
        local count = 0
        if #keys > 0 then
            count = redis.call('del', unpack(keys))
        end
        return count
        """

        result_count = await redis.eval(result_delete_script, 0, f"{settings.REDIS_RESULT_QUEUE}:*")
        logger.info(f"Deleted {result_count} result queues")
    except Exception as e:
        logger.warning(f"Result deletion script failed: {str(e)}, using scan")

        cursor = 0
        result_count = 0
        while True:
            cursor, keys = await redis.scan(
                cursor, match=f"{settings.REDIS_RESULT_QUEUE}:*", count=1000
            )
            if keys:
                pipe = redis.pipeline()
                for key in keys:
                    pipe.delete(key)
                await pipe.execute()
                result_count += len(keys)

            if cursor == 0:
                break

        logger.info(f"Deleted {result_count} result queues using scan")

    # 5. Clean up other possible states
    worker_keys = await redis.keys(f"{settings.REDIS_PREFIX}worker:*")
    if worker_keys:
        pipe = redis.pipeline()
        for key in worker_keys:
            pipe.delete(key)
        await pipe.execute()
        logger.info(f"Deleted {len(worker_keys)} worker keys")

    logger.info("Redis state reset completed")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    logger.info("Health check")
    return {"status": "healthy"}
