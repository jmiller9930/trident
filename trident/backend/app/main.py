import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.config.settings import Settings, settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("trident")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg: Settings = app.state.settings_ref  # type: ignore[attr-defined]
    logger.info(
        "event=service_start service=trident-api base_path=%s public_base_url=%s",
        cfg.normalized_base_path or "",
        cfg.public_base_url or "",
    )
    logger.info("event=service_ready service=trident-api")
    yield
    logger.info("event=service_shutdown service=trident-api")


def build_app(cfg: Settings | None = None) -> FastAPI:
    """Build FastAPI app. Use explicit cfg in tests; production uses module `settings`."""
    cfg = cfg if cfg is not None else settings
    base = cfg.normalized_base_path
    api_prefix = cfg.api_router_prefix

    app = FastAPI(
        title="Trident API",
        version="0.1.0-skeleton",
        lifespan=lifespan,
    )
    app.state.settings_ref = cfg

    app.include_router(api_router, prefix=api_prefix)

    root_path = f"{base}/" if base else "/"

    @app.get(root_path)
    def root() -> dict[str, str]:
        return {
            "service": "trident-api",
            "docs": f"{base}/docs" if base else "/docs",
            "base_path": base or "/",
        }

    return app


app = build_app()
