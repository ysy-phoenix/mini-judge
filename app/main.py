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
    await get_redis()
    logger.info(
        "Redis connection established", {"host": settings.REDIS_HOST, "port": settings.REDIS_PORT}
    )

    worker_manager = WorkerManager()
    yield

    logger.info("Application shutting down")

    worker_manager.shutdown()

    await close_redis()
    logger.info("Redis connection closed")


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
