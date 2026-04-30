import * as vscode from "vscode";

/** API origin e.g. http://127.0.0.1:8000 — no trailing slash. */
export function getApiBaseUrl(): string {
  const v = vscode.workspace.getConfiguration("trident").get<string>("apiBaseUrl");
  return (v ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(s: string): boolean {
  return UUID_RE.test(s.trim());
}

/** Identity for lock APIs; null if governance IDs not configured. */
export function getGovernanceIdentity(): {
  projectId: string;
  userId: string;
  agentRole: string;
} | null {
  const conf = vscode.workspace.getConfiguration("trident");
  const projectId = (conf.get<string>("projectId") ?? "").trim();
  const userId = (conf.get<string>("userId") ?? "").trim();
  const agentRole = (conf.get<string>("agentRole") ?? "USER").trim();
  if (!isUuid(projectId) || !isUuid(userId)) {
    return null;
  }
  return { projectId, userId, agentRole };
}

export function isEditGovernanceEnabled(): boolean {
  return vscode.workspace.getConfiguration("trident").get<boolean>("editGovernanceEnabled") ?? true;
}
