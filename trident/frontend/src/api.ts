/** Runtime API base — matches OPERATIONS_RUNBOOK / TRIDENT_BASE_PATH semantics. */

export function normalizeBasePath(raw: string | undefined): string {
  const s = (raw ?? "").trim();
  if (!s) return "";
  return "/" + s.replace(/^\/+|\/+$/g, "");
}

/**
 * JSON API prefix (no trailing slash).
 * - Preferred (compose + nginx on :3000): `TRIDENT_PUBLIC_BASE_URL` **empty**, `TRIDENT_BASE_PATH=/trident`
 *   → `origin + /trident/api` (same-origin proxy).
 * - If `PUBLIC_BASE_URL` is set but its **origin** differs from the page (e.g. `https://host/trident` while the UI is
 *   `http://host:3000`), fetch hits cross-origin / mixed content and fails with **NetworkError** — we ignore `pub`
 *   and use same-origin `origin + BASE_PATH + /api` instead.
 * - Same-origin `PUBLIC_BASE_URL` (rare) still uses `pub + /api` without duplicating `BASE_PATH`.
 */
export function getApiBase(): string {
  const pubRaw = (window.__TRIDENT_PUBLIC_BASE_URL__ ?? "").trim();
  const bp = normalizeBasePath(window.__TRIDENT_BASE_PATH__);
  const sameOriginDefault = `${window.location.origin}${bp}/api`;

  if (!pubRaw) {
    return sameOriginDefault;
  }

  let pubOrigin: string;
  try {
    pubOrigin = new URL(pubRaw).origin;
  } catch {
    return sameOriginDefault;
  }

  if (pubOrigin !== window.location.origin) {
    return sameOriginDefault;
  }

  return `${pubRaw.replace(/\/+$/, "")}/api`;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getApiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers as Record<string, string>),
    },
  });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = { raw: text };
    }
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status: number; body: unknown };
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body as T;
}
