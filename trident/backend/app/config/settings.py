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
