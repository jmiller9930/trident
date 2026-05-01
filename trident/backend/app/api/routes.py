from fastapi import APIRouter

from app.api.v1.auth import router as auth_v1_router
from app.api.v1.directives import router as directives_v1_router
from app.api.v1.git import router as git_v1_router
from app.api.v1.agent_runtime import router as agent_runtime_v1_router
from app.api.v1.decision_engine import router as decision_engine_v1_router
from app.api.v1.reviewer_runtime import router as reviewer_runtime_v1_router
from app.api.v1.directive_state import router as directive_state_v1_router
from app.api.v1.patch_proposals import router as patch_proposals_v1_router
from app.api.v1.validations import router as validations_v1_router
from app.api.v1.members import router as members_v1_router
from app.api.v1.onboarding import router as onboarding_v1_router
from app.api.v1.projects import router as projects_v1_router
from app.api.v1.ide import router as ide_v1_router
from app.api.v1.locks import router as locks_v1_router
from app.api.v1.patches import router as patches_v1_router
from app.api.v1.memory import router as memory_v1_router
from app.mcp.mcp_router import router as mcp_v1_router
from app.api.v1.nike import router as nike_v1_router
from app.api.v1.router_route import router as router_subsystem_v1_router
from app.api.v1.system import router as system_v1_router
from app.health.routes import router as health_router
from app.version.routes import router as version_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_v1_router, prefix="/auth", tags=["auth"])
v1_router.include_router(projects_v1_router, prefix="/projects", tags=["projects"])
v1_router.include_router(members_v1_router, prefix="/members", tags=["members"])
v1_router.include_router(
    onboarding_v1_router,
    prefix="/projects/{project_id}/onboarding",
    tags=["onboarding"],
)
v1_router.include_router(
    git_v1_router,
    prefix="/projects/{project_id}/git",
    tags=["git"],
)
v1_router.include_router(
    directive_state_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}",
    tags=["directive-state"],
)
v1_router.include_router(
    agent_runtime_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}/agents",
    tags=["agents"],
)
v1_router.include_router(
    decision_engine_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}",
    tags=["decision-engine"],
)
v1_router.include_router(
    reviewer_runtime_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}/patches/{patch_id}",
    tags=["reviewer"],
)
v1_router.include_router(
    patch_proposals_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}/patches",
    tags=["patches-governed"],
)
v1_router.include_router(
    validations_v1_router,
    prefix="/projects/{project_id}/directives/{directive_id}/validations",
    tags=["validations"],
)
v1_router.include_router(system_v1_router, prefix="/system", tags=["system"])
v1_router.include_router(ide_v1_router, prefix="/ide", tags=["ide"])
v1_router.include_router(directives_v1_router, prefix="/directives", tags=["directives"])
v1_router.include_router(nike_v1_router, prefix="/nike", tags=["nike"])
v1_router.include_router(memory_v1_router, prefix="/memory", tags=["memory"])
v1_router.include_router(locks_v1_router, prefix="/locks", tags=["locks"])
v1_router.include_router(patches_v1_router, prefix="/patches", tags=["patches"])
v1_router.include_router(mcp_v1_router, prefix="/mcp", tags=["mcp"])
v1_router.include_router(router_subsystem_v1_router, prefix="/router", tags=["router"])
api_router.include_router(v1_router)
