"""trident-worker entrypoint — Nike dispatcher loop (100O §4, §9)."""

from __future__ import annotations

import logging
import sys
import time

from app.config.settings import Settings
from app.db.session import session_factory_for_settings
from app.nike.dispatcher import drain_pending_batch

logger = logging.getLogger("trident.nike.worker")


def main() -> None:
    cfg = Settings()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        stream=sys.stdout,
        format="%(message)s",
    )
    factory = session_factory_for_settings(cfg)
    logger.info(
        "event=nike_worker_start service=trident-worker poll_sec=%s max_attempts=%s",
        cfg.nike_poll_sec,
        cfg.nike_max_attempts,
    )
    while True:
        batch = 0
        session = factory()
        try:
            batch = drain_pending_batch(session, cfg, max_events=32)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("event=nike_worker_batch_error")
        finally:
            session.close()
        if batch == 0:
            time.sleep(cfg.nike_poll_sec)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("event=nike_worker_shutdown service=trident-worker")
        sys.exit(0)
