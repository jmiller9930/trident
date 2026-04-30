#!/bin/sh
set -e
BP="${TRIDENT_BASE_PATH:-}"
BP_TRIM=$(echo "$BP" | sed 's|^/*||;s|/*$||')
if [ -n "$BP_TRIM" ]; then
  export TRIDENT_NGINX_LOCATION_API="/${BP_TRIM}/api/"
else
  export TRIDENT_NGINX_LOCATION_API="/api/"
fi
export TRIDENT_BASE_PATH="${TRIDENT_BASE_PATH:-}"
export TRIDENT_PUBLIC_BASE_URL="${TRIDENT_PUBLIC_BASE_URL:-}"
envsubst '${TRIDENT_BASE_PATH}${TRIDENT_PUBLIC_BASE_URL}' < /templates/config.js.template > /usr/share/nginx/html/config.js
envsubst '${TRIDENT_NGINX_LOCATION_API}' < /templates/nginx.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g "daemon off;"
