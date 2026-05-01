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
  workspaceId: string;
  userId: string;
  agentRole: string;
} | null {
  const conf = vscode.workspace.getConfiguration("trident");
  const projectId = (conf.get<string>("projectId") ?? "").trim();
  const workspaceId = (conf.get<string>("workspaceId") ?? "").trim();
  const userId = (conf.get<string>("userId") ?? "").trim();
  const agentRole = (conf.get<string>("agentRole") ?? "USER").trim();
  if (!isUuid(projectId) || !isUuid(userId)) {
    return null;
  }
  return { projectId, workspaceId, userId, agentRole };
}

export function isEditGovernanceEnabled(): boolean {
  return vscode.workspace.getConfiguration("trident").get<boolean>("editGovernanceEnabled") ?? true;
}

export function getPatchWorkflowRequired(): boolean {
  return vscode.workspace.getConfiguration("trident").get<boolean>("patchWorkflowRequired") ?? false;
}

export function getLockHeartbeatIntervalSec(): number {
  const v = vscode.workspace.getConfiguration("trident").get<number>("lockHeartbeatIntervalSec");
  if (typeof v !== "number" || Number.isNaN(v)) {
    return 60;
  }
  return Math.max(0, Math.floor(v));
}

export function isDebugMode(): boolean {
  return vscode.workspace.getConfiguration("trident").get<boolean>("debugMode") ?? false;
}

/** Human-readable label for a directive status enum value. */
export function humanStatus(status: string): string {
  switch (status) {
    case "DRAFT":       return "Draft";
    case "ACTIVE":      return "Active";
    case "IN_PROGRESS": return "Running";
    case "REVIEW":      return "Waiting";
    case "COMPLETE":    return "Complete";
    case "CLOSED":      return "Closed";
    case "FAILED":      return "Failed";
    case "REJECTED":    return "Rejected";
    case "CANCELLED":   return "Cancelled";
    default:            return status;
  }
}

/** Human-readable label for a ledger state enum value. */
export function humanLedgerState(state: string): string {
  switch (state) {
    case "DRAFT":       return "Draft";
    case "IN_PROGRESS": return "Running";
    case "REVIEW":      return "In Review";
    case "CLOSED":      return "Closed";
    case "FAILED":      return "Failed";
    default:            return state;
  }
}
