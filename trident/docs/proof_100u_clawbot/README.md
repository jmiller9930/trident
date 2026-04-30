# 100U clawbot proof captures

Captured on **clawbot.a51.corp** after `git pull` → `docker compose build trident-web` → `docker compose up -d trident-web`.

**Important:** For same-origin nginx proxy to the API, run **`trident-web`** with **`TRIDENT_PUBLIC_BASE_URL` empty** (e.g. `TRIDENT_PUBLIC_BASE_URL= docker compose up -d trident-web`). Otherwise the UI may call a cross-origin API URL and hit browser CORS.

When **`TRIDENT_BASE_PATH=/trident`**, health via the web port is **`http://<host>:3000/trident/api/health`** (JSON). A bare **`/api/health`** on the web port falls through to the SPA unless nginx also proxies `/api/` (not required when base path is set).

**PNG files**

- **`100u-directives-and-panels.png`** — full-page UI (directives + workspace + MCP/router rail).
- **`100u-mcp-router-rail.png`** — crop of **`aside.control`** (router + MCP).

Headless capture used **`ghcr.io/puppeteer/puppeteer:22.15.0`** with **`NODE_PATH=/home/pptruser/node_modules`** and script **`capture_mcp_rail.cjs`**.
