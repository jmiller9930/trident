/** Runtime API base — matches OPERATIONS_RUNBOOK / TRIDENT_BASE_PATH semantics. */

export function normalizeBasePath(raw: string | undefined): string {
  const s = (raw ?? "").trim();
  if (!s) return "";
  return "/" + s.replace(/^\/+|\/+$/g, "");
}

/**
 * JSON API prefix (no trailing slash).
 * - Same-origin: `origin + BASE_PATH + /api` (nginx proxy), when `PUBLIC_BASE_URL` is empty.
 * - Cross-origin: `PUBLIC_BASE_URL + /api` — URL must already be the API mount (e.g. `https://host/trident`),
 *   do not append `BASE_PATH` again (avoids `/trident/trident/api` when both are set).
 */
export function getApiBase(): string {
  const pub = (window.__TRIDENT_PUBLIC_BASE_URL__ ?? "").trim();
  const bp = normalizeBasePath(window.__TRIDENT_BASE_PATH__);
  if (pub) {
    return `${pub.replace(/\/+$/, "")}/api`;
  }
  return `${window.location.origin}${bp}/api`;
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
