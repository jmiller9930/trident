import logging

from fastapi import APIRouter

logger = logging.getLogger("trident")

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    logger.info("event=service_health_check service=trident-api endpoint=/api/health")
    return {"status": "ok", "service": "trident-api"}


@router.get("/ready")
def ready() -> dict[str, str]:
    logger.info("event=service_health_check service=trident-api endpoint=/api/ready")
    return {"status": "ready", "service": "trident-api"}
