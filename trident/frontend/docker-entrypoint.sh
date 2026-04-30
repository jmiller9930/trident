#!/bin/sh
set -e
export TRIDENT_BASE_PATH="${TRIDENT_BASE_PATH:-}"
export TRIDENT_PUBLIC_BASE_URL="${TRIDENT_PUBLIC_BASE_URL:-}"
envsubst '${TRIDENT_BASE_PATH}${TRIDENT_PUBLIC_BASE_URL}' < /templates/config.js.template > /usr/share/nginx/html/config.js
exec nginx -g "daemon off;"
