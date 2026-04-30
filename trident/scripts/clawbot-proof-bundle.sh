#!/usr/bin/env bash
# Run on clawbot from the trident runtime directory (…/trident/) after deploy:
#   cp .env.example .env   # configure TRIDENT_* for clawbot
#   docker compose up -d
#   export vars or: set -a && . ./.env && set +a
#   bash scripts/clawbot-proof-bundle.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${TRIDENT_PUBLIC_BASE_URL:?Set TRIDENT_PUBLIC_BASE_URL in .env (e.g. https://clawbot.a51.corp/trident)}"

PUB="${TRIDENT_PUBLIC_BASE_URL%/}"

echo "=== PROOF BUNDLE === date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=== git HEAD (if repo) ==="
( cd "$ROOT/../.." && git rev-parse HEAD 2>/dev/null ) || ( git rev-parse HEAD 2>/dev/null ) || echo "(unknown)"

echo "=== docker compose ps ==="
docker compose ps

echo "=== curl ${PUB}/api/health ==="
curl -fsS "${PUB}/api/health" && echo

echo "=== curl ${PUB}/api/ready ==="
curl -fsS "${PUB}/api/ready" && echo

echo "=== curl ${PUB}/api/version ==="
curl -fsS "${PUB}/api/version" && echo

echo "=== docker compose logs --tail=80 trident-api trident-web ==="
docker compose logs --tail=80 trident-api trident-web

echo "=== restart persistence: docker compose restart trident-api ==="
docker compose restart trident-api
sleep 5

echo "=== curl ${PUB}/api/health (after restart) ==="
curl -fsS "${PUB}/api/health" && echo

echo "=== docker compose ps (after restart) ==="
docker compose ps

echo "=== secrets: .env must not be committed ==="
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  TOP="$(git rev-parse --show-toplevel)"
  if git -C "$TOP" ls-files --error-unmatch trident/.env >/dev/null 2>&1; then
    echo "FAIL: trident/.env is tracked by git"
    exit 1
  fi
  echo "OK: trident/.env is not tracked (adjust path if repo layout differs)"
else
  echo "(skip git secrets check — not a git checkout)"
fi

echo "=== PROOF BUNDLE END ==="
