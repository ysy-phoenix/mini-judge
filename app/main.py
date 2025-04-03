import os
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.workers.manager import WorkerManager

# Global worker manager reference
_worker_manager = None


# Simple force exit handler
def force_exit(signum, frame):
    # Force immediate exit without any cleanup
    os._exit(0)


# Register force exit handlers
signal.signal(signal.SIGINT, force_exit)
signal.signal(signal.SIGTERM, force_exit)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_manager
    logger.info("Application starting")

    # Initialize Redis
    _ = await get_redis()

    # Initialize worker manager
    _worker_manager = WorkerManager()

    try:
        yield
    finally:
        os._exit(0)


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
    return {"status": "healthy"}
