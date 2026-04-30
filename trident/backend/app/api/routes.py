from fastapi import APIRouter

from app.api.v1.directives import router as directives_v1_router
from app.api.v1.system import router as system_v1_router
from app.health.routes import router as health_router
from app.version.routes import router as version_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(system_v1_router, prefix="/system", tags=["system"])
v1_router.include_router(directives_v1_router, prefix="/directives", tags=["directives"])
api_router.include_router(v1_router)
