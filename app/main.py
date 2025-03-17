from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.logger import log_with_context
from app.utils.redis import close_redis, get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_with_context("Application starting", {"version": settings.VERSION})

    # Initialize Redis on startup
    await get_redis()
    log_with_context(
        "Redis connection established", {"host": settings.REDIS_HOST, "port": settings.REDIS_PORT}
    )

    yield

    # log the application shutdown
    log_with_context("Application shutting down")

    # Close Redis on shutdown
    await close_redis()
    log_with_context("Redis connection closed")


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
    log_with_context("Health check")
    return {"status": "healthy"}
