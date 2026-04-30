# Trident IDE extension (100K)

VS Code / Code - OSS extension that connects to **trident-api** only (no local LLM, no direct external APIs).

## Setup

```bash
cd trident-ide-extension
npm install
npm run compile
```

Open this folder in VS Code and run **Run Extension** (F5). Ensure API is up, e.g. `http://127.0.0.1:8000` (default **`trident.apiBaseUrl`**).

## Features

- **Sidebar** — connection hint, read-only directive list, shortcuts for chat / agent JSON / health.
- **Chat** — **`POST /api/v1/ide/chat`** (deterministic stub + audits + **`CHAT_LOG`** proof on the server).
- **Agent state** — opens JSON combining directive detail + **`/api/v1/memory/directive/{id}`**.

## API paths

With default settings, requests use `{apiBaseUrl}/api/health` and `{apiBaseUrl}/api/v1/...`. If the API is served under a path prefix (e.g. **`TRIDENT_BASE_PATH=/trident`**), set **`trident.apiBaseUrl`** to the **origin only** and ensure your reverse proxy maps **`/trident/api`** to the API (same as web UI), or point **`apiBaseUrl`** at the full public API root per **`OPERATIONS_RUNBOOK`**.

## Layout

```
src/
  extension.ts
  api/tridentClient.ts
  utils/config.ts
  sidebar/tridentSidebar.ts
  panels/chatPanel.ts
```

## Packaging

```bash
npm run compile
npx --yes @vscode/vsce package --no-dependencies
```
