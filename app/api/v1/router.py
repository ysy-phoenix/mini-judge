from fastapi import APIRouter

from app.api.v1.endpoints import health, judge

api_router = APIRouter()
api_router.include_router(judge.router, prefix="/judge", tags=["judge"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
