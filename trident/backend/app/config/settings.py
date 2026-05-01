from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_base_path(raw: str | None) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    return "/" + s.strip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIDENT_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    db_host: str = "trident-db"
    db_port: int = 5432
    db_name: str = "trident"
    db_user: str = "trident"
    db_password: str = "changeme_local_only"
    """ChromaDB server host (empty = local ephemeral client for dev/tests)."""
    chroma_host: str = ""
    chroma_port: int = 8000
    """When chroma_host is empty and this is set, use persistent on-disk Chroma (tests / single-node)."""
    chroma_local_path: str = ""
    """Public URL for OpenAPI/docs references (e.g. https://clawbot.a51.corp/trident)."""
    public_base_url: str = ""
    """HTTP path prefix when served behind a reverse proxy (e.g. /trident). Empty for local dev."""
    base_path: str = ""
    """Nike worker poll interval when no pending events (seconds)."""
    nike_poll_sec: float = 2.0
    """Max processing attempts per event before dead-letter (global default, 100O)."""
    nike_max_attempts: int = 5
    """Base delay before returning an event to PENDING after a retriable failure (seconds)."""
    nike_retry_backoff_sec: float = 1.0
    """When > 0, new lock rows set expires_at = now + TTL (100P); 0 disables TTL."""
    lock_ttl_sec: int = 0
    """FIX 003: when > 0, ACTIVE lock becomes STALE if last heartbeat older than this many seconds; 0 disables."""
    lock_heartbeat_miss_sec: int = 300
    """Comma-separated UUIDs allowed to call POST /locks/force-release (FIX 003)."""
    lock_force_release_admin_user_ids: str = ""
    """100R: SINGLE_MODEL_MODE | CADRE_MODE"""
    model_router_mode: str = "SINGLE_MODEL_MODE"
    """100R: when False, external escalation path is never taken (local-first only; deterministic CI)."""
    model_router_escalation_enabled: bool = False
    """100R: escalate to external stub when local confidence < this (only if escalation_enabled)."""
    model_router_escalation_confidence_threshold: float = 0.5
    """100R: max chars for token optimizer before external path."""
    model_router_token_budget_chars: int = 4096
    """100R: shared profile id when SINGLE_MODEL_MODE."""
    model_router_shared_profile_id: str = "trident_local_shared_v1"
    """100R: external stub model label for ENGINEER role (no live API in default build). IDE_002: sonnet_46_external."""
    model_router_external_stub_model_id: str = "sonnet_46_external"
    """FIX 005: max cumulative external optimized-prompt chars per directive; 0 = unlimited."""
    model_router_external_budget_max_chars: int = 0
    """FIX 005: emit budget warning audit when usage crosses this fraction of max (ignored if max 0)."""
    model_router_external_budget_warn_ratio: float = 0.85
    """FIX 005: prompt length above this suggests CONTEXT_WINDOW_LIMIT escalation candidate."""
    model_router_context_soft_limit_chars: int = 96_000
    """MODEL_PLANE_WIRING — Ollama (or compatible) base URL for primary inference plane; required for production routing."""
    model_router_base_url: str = "http://127.0.0.1:11434"
    """Optional secondary model plane (e.g. 172.20.1.66); empty disables."""
    model_router_secondary_base_url: str = ""
    """Gate: secondary plane allowed only when True (manual / ops toggle)."""
    model_plane_secondary_enabled: bool = False
    model_plane_connect_timeout_sec: float = 2.0
    model_plane_read_timeout_sec: float = 5.0
    """Inference POST timeouts (generate/chat/embeddings)."""
    model_plane_request_timeout_sec: float = 120.0
    """Probe retries after first attempt (directive default 2 → 3 total tries)."""
    model_plane_probe_retries: int = 2
    model_plane_circuit_breaker_threshold: int = 3
    model_plane_circuit_breaker_ttl_sec: float = 60.0
    """Optional full URL for secondary readiness (accept_inference JSON); empty skips extra gate."""
    model_plane_secondary_ready_url: str = ""
    """When False, skip TCP connect before HTTP probe (mocked httpx tests / environments without reachable ports)."""
    model_plane_tcp_probe_enabled: bool = True
    """MODEL_ROUTER_002: when True, EXTERNAL engineer path uses ModelPlaneRouterService (Ollama /api/chat)."""
    engineer_use_model_plane: bool = False
    """MODEL_ROUTER_002: passed as prefer_secondary when engineer_use_model_plane is True."""
    engineer_model_plane_prefer_secondary: bool = False
    # ── GitHub provider (GITHUB_001) ─────────────────────────────────────
    """Opt-in gate — ALL git endpoints return 503 when False."""
    github_enabled: bool = False
    """Fine-grained PAT (read from env; use github_token_file for secret-mount pattern)."""
    github_token: str = ""
    """Path to a file containing the token (Docker/K8s secret mount). Takes precedence over github_token."""
    github_token_file: str = ""
    """GitHub REST API base URL (override for GHES)."""
    github_api_base_url: str = "https://api.github.com"
    """Default org slug for repo creation; empty = personal account."""
    github_default_org: str = ""
    github_api_timeout: float = 30.0
    # ── JWT ──────────────────────────────────────────────────────────────
    """HS256 signing secret for JWT access/refresh (set in production)."""
    jwt_secret: str = "trident_local_dev_jwt_secret_min_32_chars_x"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    @field_validator("base_path", mode="before")
    @classmethod
    def coerce_base_path(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v)

    @property
    def normalized_base_path(self) -> str:
        return normalize_base_path(self.base_path)

    @property
    def api_router_prefix(self) -> str:
        """Mount point for API routes (e.g. /api or /trident/api)."""
        base = self.normalized_base_path
        return f"{base}/api" if base else "/api"


settings = Settings()
