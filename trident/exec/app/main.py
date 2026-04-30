import logging
import sys

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
logger = logging.getLogger("trident-exec")

app = FastAPI(title="Trident Exec Placeholder")


@app.on_event("startup")
async def startup() -> None:
    logger.info("event=service_start service=trident-exec")
    logger.info("event=service_ready service=trident-exec")


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("event=service_health_check service=trident-exec endpoint=/health")
    return {"status": "ok", "service": "trident-exec"}


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("event=service_shutdown service=trident-exec")
