from fastapi import APIRouter

from app.api.v1.directives import router as directives_v1_router
from app.api.v1.locks import router as locks_v1_router
from app.api.v1.memory import router as memory_v1_router
from app.mcp.mcp_router import router as mcp_v1_router
from app.api.v1.nike import router as nike_v1_router
from app.api.v1.system import router as system_v1_router
from app.health.routes import router as health_router
from app.version.routes import router as version_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(system_v1_router, prefix="/system", tags=["system"])
v1_router.include_router(directives_v1_router, prefix="/directives", tags=["directives"])
v1_router.include_router(nike_v1_router, prefix="/nike", tags=["nike"])
v1_router.include_router(memory_v1_router, prefix="/memory", tags=["memory"])
v1_router.include_router(locks_v1_router, prefix="/locks", tags=["locks"])
v1_router.include_router(mcp_v1_router, prefix="/mcp", tags=["mcp"])
api_router.include_router(v1_router)
