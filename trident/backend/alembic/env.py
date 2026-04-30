from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure `app` package is importable when running alembic from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config.settings import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import database_url_from_settings  # noqa: E402

import app.models  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except (KeyError, ValueError):
        pass

target_metadata = Base.metadata


def get_url() -> str:
    return database_url_from_settings(Settings())


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = dict(config.get_section(config.config_ini_section) or {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
