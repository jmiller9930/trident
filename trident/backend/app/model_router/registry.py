"""Model profile registry + cadre mapping (100R / IDE_002).

Cadre alignment:
  ENGINEER:      local=qwen3_coder_next  external=sonnet_46_external
  ARCHITECT:     local=qwen_reasoning_local  external=opus_latest_external  (manual escalation only)
  REVIEWER/DOCS: local=qwen_reasoning_local  external=sonnet_46_external
  SYSTEM/USER:   shared profile
"""

from __future__ import annotations

from app.config.settings import Settings
from app.models.enums import AgentRole

# ── Named profile IDs (used in MODEL_ROUTING_DECISION audit payloads) ──────────
LOCAL_PROFILE_ENGINEER   = "qwen3_coder_next"
LOCAL_PROFILE_ARCHITECT  = "qwen_reasoning_local"
LOCAL_PROFILE_REVIEWER   = "qwen_reasoning_local"
LOCAL_PROFILE_DOCS       = "qwen_instruct_small"
LOCAL_PROFILE_SHARED     = "trident_local_shared_v1"

EXTERNAL_MODEL_ENGINEER  = "sonnet_46_external"
EXTERNAL_MODEL_ARCHITECT = "opus_latest_external"   # manual escalation only
EXTERNAL_MODEL_REVIEWER  = "sonnet_46_external"
EXTERNAL_MODEL_DOCS      = "sonnet_46_external"

# ── Cadre local profile lookup ──────────────────────────────────────────────────
_CADRE_LOCAL_BY_ROLE: dict[AgentRole, str] = {
    AgentRole.ENGINEER:      LOCAL_PROFILE_ENGINEER,
    AgentRole.ARCHITECT:     LOCAL_PROFILE_ARCHITECT,
    AgentRole.REVIEWER:      LOCAL_PROFILE_REVIEWER,
    AgentRole.DOCUMENTATION: LOCAL_PROFILE_DOCS,
    AgentRole.DEBUGGER:      LOCAL_PROFILE_ENGINEER,
    AgentRole.SYSTEM:        LOCAL_PROFILE_SHARED,
    AgentRole.USER:          LOCAL_PROFILE_SHARED,
}

# ── Cadre external fallback lookup ─────────────────────────────────────────────
_CADRE_EXTERNAL_BY_ROLE: dict[AgentRole, str] = {
    AgentRole.ENGINEER:      EXTERNAL_MODEL_ENGINEER,
    AgentRole.ARCHITECT:     EXTERNAL_MODEL_ARCHITECT,
    AgentRole.REVIEWER:      EXTERNAL_MODEL_REVIEWER,
    AgentRole.DOCUMENTATION: EXTERNAL_MODEL_DOCS,
    AgentRole.DEBUGGER:      EXTERNAL_MODEL_ENGINEER,
    AgentRole.SYSTEM:        EXTERNAL_MODEL_ENGINEER,
    AgentRole.USER:          EXTERNAL_MODEL_ENGINEER,
}


def resolve_profile_id(*, agent_role: AgentRole, settings: Settings) -> str:
    """Return the local profile ID for the given role + settings mode."""
    mode = (settings.model_router_mode or "SINGLE_MODEL_MODE").strip().upper().replace("-", "_")
    if mode == "CADRE_MODE":
        return _CADRE_LOCAL_BY_ROLE.get(agent_role, settings.model_router_shared_profile_id)
    return settings.model_router_shared_profile_id


def resolve_external_model_id(*, agent_role: AgentRole, settings: Settings) -> str:
    """Return the external model label for the given role.

    Falls back to ``settings.model_router_external_stub_model_id`` if SINGLE_MODEL_MODE
    or if role not in cadre map.
    """
    mode = (settings.model_router_mode or "SINGLE_MODEL_MODE").strip().upper().replace("-", "_")
    if mode == "CADRE_MODE":
        return _CADRE_EXTERNAL_BY_ROLE.get(agent_role, settings.model_router_external_stub_model_id)
    return settings.model_router_external_stub_model_id
