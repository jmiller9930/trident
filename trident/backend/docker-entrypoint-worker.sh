#!/bin/sh
set -e
cd /app
python -m alembic upgrade head
exec python -m app.nike.worker_main
