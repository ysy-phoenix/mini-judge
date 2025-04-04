import os
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import logger
from app.utils.redis import get_redis
from app.workers.manager import WorkerManager

# Global worker manager reference
manager = None


def handle_signal(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signal.Signals(signum).name}. Initiating shutdown...")
    if manager.running:
        manager.shutdown()
    sys.exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with fast startup and shutdown."""
    global manager
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Initialize worker manager
    manager = WorkerManager()
    manager.start()
    redis = await get_redis()
    await redis.flushall()

    try:
        yield
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        logger.info("Finishing application...")
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
