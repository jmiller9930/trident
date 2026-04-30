import logging
import sys
import time

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
logger = logging.getLogger("trident-worker")


def main() -> None:
    logger.info("event=service_start service=trident-worker")
    logger.info("event=service_ready service=trident-worker")
    interval = float(__import__("os").environ.get("TRIDENT_WORKER_HEARTBEAT_SEC", "10"))
    while True:
        logger.info("event=service_health_check service=trident-worker heartbeat=true")
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("event=service_shutdown service=trident-worker")
        sys.exit(0)
