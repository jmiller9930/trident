from fastapi import APIRouter

from app.health.routes import router as health_router
from app.version.routes import router as version_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)
