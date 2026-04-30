import * as vscode from "vscode";

/** API origin e.g. http://127.0.0.1:8000 — no trailing slash. */
export function getApiBaseUrl(): string {
  const v = vscode.workspace.getConfiguration("trident").get<string>("apiBaseUrl");
  return (v ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
}
