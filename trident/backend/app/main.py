import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.config.settings import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("trident")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("event=service_start service=trident-api")
    logger.info("event=service_ready service=trident-api")
    yield
    logger.info("event=service_shutdown service=trident-api")


app = FastAPI(title="Trident API", version="0.1.0-skeleton", lifespan=lifespan)
app.include_router(api_router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "trident-api", "docs": "/docs"}
