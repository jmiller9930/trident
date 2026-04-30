"""Minimal placeholder for trident-vector (100A); replace with Chroma or real vector stack in later directives."""

import logging
import sys

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
logger = logging.getLogger("trident-vector-placeholder")

app = FastAPI(title="Trident Vector Placeholder")


@app.on_event("startup")
async def startup() -> None:
    logger.info("event=service_start service=trident-vector")
    logger.info("event=service_ready service=trident-vector")


@app.get("/health")
def health() -> dict[str, str]:
    logger.info("event=service_health_check service=trident-vector endpoint=/health")
    return {"status": "ok", "service": "trident-vector-placeholder"}


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("event=service_shutdown service=trident-vector")
