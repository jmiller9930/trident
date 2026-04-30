from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, settings as app_settings


def database_url_from_settings(cfg: Settings) -> str:
    return (
        f"postgresql+psycopg2://{cfg.db_user}:{cfg.db_password}"
        f"@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}"
    )


def create_engine_for_settings(cfg: Settings):
    return create_engine(
        database_url_from_settings(cfg),
        pool_pre_ping=True,
    )


def session_factory_for_settings(cfg: Settings) -> sessionmaker[Session]:
    engine = create_engine_for_settings(cfg)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session_factory(cfg: Settings) -> sessionmaker[Session]:
    return session_factory_for_settings(cfg)


def get_settings_dep() -> Settings:
    return app_settings


def get_db(
    cfg: Annotated[Settings, Depends(get_settings_dep)],
) -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session (sync)."""
    factory = session_factory_for_settings(cfg)
    session = factory()
    try:
        yield session
        session.commit()
    except HTTPException:
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
