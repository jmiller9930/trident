#!/bin/sh
set -e
BP="${TRIDENT_BASE_PATH:-}"
if [ -z "$BP" ]; then
  curl -fsS "http://127.0.0.1:8000/api/health"
else
  BP_NORM="/$(echo "$BP" | sed 's|^/*||;s|/*$||')"
  curl -fsS "http://127.0.0.1:8000${BP_NORM}/api/health"
fi
