import { getApiBaseUrl } from "../utils/config";

export interface DirectiveSummary {
  id: string;
  title: string;
  status: string;
}

export interface DirectiveListResponse {
  items: DirectiveSummary[];
}

export interface IdeChatResponse {
  reply: string;
  correlation_id: string;
  proof_object_id: string;
}

export interface IdeStatusResponse {
  directive_id: string;
  title: string;
  directive_status: string;
  ledger_state: string;
  current_agent_role: string;
  last_routing_decision?: {
    routing_outcome?: string;
    escalation_trigger_code?: string;
    calibrated_confidence?: number;
    local_model?: string;
    external_model?: string;
    blocked_external?: boolean;
    blocked_reason_code?: string;
  } | null;
  last_routing_model?: string | null;
  nodes_executed?: string[] | null;
}

export interface IdeProofSummaryResponse {
  directive_id: string;
  title: string;
  directive_status: string;
  ledger_state: string;
  current_agent_role: string;
  proof_count: number;
  last_routing_decision?: IdeStatusResponse["last_routing_decision"];
  last_routing_model?: string | null;
  last_mcp_events: Array<Record<string, unknown>>;
  last_patch_event?: Record<string, unknown> | null;
}

export interface CreateDirectiveBody {
  workspace_id: string;
  project_id: string;
  title: string;
  graph_id?: string;
  created_by_user_id: string;
}

export interface CreateDirectiveResponseBody {
  directive: DirectiveSummary & { workspace_id: string; project_id: string };
  task_ledger: { id: string; current_state: string; current_agent_role: string };
}

export interface ActiveLockInfo {
  lock_id: string;
  project_id: string;
  directive_id: string;
  file_path: string;
  locked_by_user_id: string;
  locked_by_agent_role: string;
  lock_status: string;
  expires_at: string | null;
}

export interface LockAcquireResponseBody {
  lock_id: string;
  project_id: string;
  directive_id: string;
  file_path: string;
  lock_status: string;
}

export interface PatchProposeResponseBody {
  unified_diff: string;
  summary: string;
  correlation_id: string;
  result_text: string;
}

export interface PatchRejectResponseBody {
  correlation_id: string;
}

export interface PatchApplyCompleteResponseBody {
  proof_object_id: string;
  lock_id: string;
  correlation_id: string;
}

export interface IdeRouterSnapshot {
  route: string | null;
  reason: string;
  next_action: string;
  validated: boolean;
}

export interface IdeMcpAuditSnippet {
  event_type: string;
  created_at?: string | null;
  payload_preview: string;
}

export interface IdeActionResponseBody {
  correlation_id: string;
  action: string;
  project_id: string;
  directive_id: string;
  directive_status: string;
  task_ledger_state: string;
  current_agent_role: string;
  reply: string | null;
  nodes_executed: string[] | null;
  proof_object_id: string | null;
  router: IdeRouterSnapshot | null;
  memory_preview: Record<string, unknown> | null;
  mcp_recent: IdeMcpAuditSnippet[] | null;
  patch_guidance: string | null;
}

// ── Decision engine types (DECISION_ENGINE_001 / VSCODE_DECISION_001) ────────

export interface DecisionEvidenceItem {
  source: string;
  detail: string;
  source_id?: string | null;
}

export interface DecisionResponse {
  recommendation: string;
  confidence: number;
  summary: string;
  evidence: DecisionEvidenceItem[];
  blocking_reasons: string[];
  recommended_next_api_action?: string | null;
  computed_at: string;
}

export interface DecisionRecordResponse extends DecisionResponse {
  decision_record_id: string;
  persisted: boolean;
}

// ── Execution state types (STATUS_001 / VSCODE_001) ─────────────────────────

export class ExecutionStateAuthError extends Error {
  constructor(msg: string) { super(msg); this.name = "ExecutionStateAuthError"; }
}

export interface ActionAllowed {
  allowed: boolean;
  reason_code?: string | null;
  reason_text?: string | null;
}

export interface ExecutionActionsAllowed {
  create_patch: ActionAllowed;
  accept_patch: ActionAllowed;
  reject_patch: ActionAllowed;
  execute_patch: ActionAllowed;
  create_validation: ActionAllowed;
  start_validation: ActionAllowed;
  complete_validation: ActionAllowed;
  waive_validation: ActionAllowed;
  signoff: ActionAllowed;
}

export interface BlockingReason {
  code: string;
  message: string;
  required_next_action?: string | null;
}

export interface ExecutionStateResponse {
  directive: {
    directive_id: string;
    project_id: string;
    title: string;
    status: string;
    created_by_user_id: string;
    created_at: string;
    closed_at?: string | null;
    closed_by_user_id?: string | null;
  };
  git: {
    repo_linked: boolean;
    provider?: string | null;
    owner?: string | null;
    repo_name?: string | null;
    branch_name?: string | null;
    latest_commit_sha?: string | null;
    branch_created: boolean;
    commit_pushed: boolean;
  };
  patch: {
    patch_count: number;
    latest_patch_id?: string | null;
    latest_patch_status?: string | null;
    accepted_patch_id?: string | null;
    accepted_patch_executed: boolean;
    execution_commit_sha?: string | null;
  };
  validation: {
    validation_count: number;
    passed_count: number;
    failed_count: number;
    waived_count: number;
    latest_validation_status?: string | null;
    signoff_eligible: boolean;
  };
  signoff: {
    closed: boolean;
    proof_object_id?: string | null;
  };
  actions_allowed: ExecutionActionsAllowed;
  blocking_reasons: BlockingReason[];
  computed_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────

export class TridentClient {
  constructor(private readonly apiOrigin: string = getApiBaseUrl()) {}

  private v1Url(path: string): string {
    const base = this.apiOrigin.replace(/\/+$/, "");
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${base}/api/v1${p}`;
  }

  private healthUrl(): string {
    return `${this.apiOrigin.replace(/\/+$/, "")}/api/health`;
  }

  async health(): Promise<{ ok: boolean; status: number; body: string }> {
    try {
      const res = await fetch(this.healthUrl(), { headers: { Accept: "application/json" } });
      const body = await res.text();
      return { ok: res.ok, status: res.status, body };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, status: 0, body: msg };
    }
  }

  async connectionLabel(): Promise<{ label: string; detail?: string }> {
    const h = await this.health();
    if (h.ok) {
      return { label: "Backend connected", detail: this.apiOrigin };
    }
    return {
      label: "Backend unreachable",
      detail: h.body.slice(0, 120),
    };
  }

  async listDirectives(): Promise<DirectiveListResponse> {
    const res = await fetch(this.v1Url("/directives/"), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`list directives: HTTP ${res.status}`);
    }
    return (await res.json()) as DirectiveListResponse;
  }

  async getDirective(directiveId: string): Promise<unknown> {
    const res = await fetch(this.v1Url(`/directives/${directiveId}`), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`directive: HTTP ${res.status}`);
    }
    return res.json();
  }

  async getMemoryDirective(directiveId: string): Promise<unknown> {
    const res = await fetch(this.v1Url(`/memory/directive/${directiveId}`), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`memory: HTTP ${res.status}`);
    }
    return res.json();
  }

  async getActiveLock(projectId: string, relativeFilePath: string): Promise<ActiveLockInfo | null> {
    const params = new URLSearchParams({
      project_id: projectId,
      file_path: relativeFilePath,
    });
    const res = await fetch(`${this.v1Url("/locks/active")}?${params.toString()}`, {
      headers: { Accept: "application/json" },
    });
    if (res.status === 404) {
      return null;
    }
    if (!res.ok) {
      throw new Error(`locks/active: HTTP ${res.status} ${await res.text()}`);
    }
    return (await res.json()) as ActiveLockInfo;
  }

  async acquireLock(body: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
  }): Promise<LockAcquireResponseBody> {
    const res = await fetch(this.v1Url("/locks/acquire"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`locks/acquire: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as LockAcquireResponseBody;
  }

  /** Same JSON envelope as release (FIX 003). */
  async postLockHeartbeat(body: {
    lock_id: string;
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
  }): Promise<{ lock_id: string; lock_status: string; last_heartbeat_at?: string | null }> {
    const res = await fetch(this.v1Url("/locks/heartbeat"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`locks/heartbeat: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as { lock_id: string; lock_status: string; last_heartbeat_at?: string | null };
  }

  async releaseLock(body: {
    lock_id: string;
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
  }): Promise<{ lock_id: string; lock_status: string }> {
    const res = await fetch(this.v1Url("/locks/release"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`locks/release: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as { lock_id: string; lock_status: string };
  }

  async proposePatch(body: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
    before_text: string;
    after_text: string;
    correlation_id?: string | null;
  }): Promise<PatchProposeResponseBody> {
    const res = await fetch(this.v1Url("/patches/propose"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`patches/propose: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as PatchProposeResponseBody;
  }

  async rejectPatch(body: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
    reason?: string | null;
    correlation_id?: string | null;
  }): Promise<PatchRejectResponseBody> {
    const res = await fetch(this.v1Url("/patches/reject"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`patches/reject: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as PatchRejectResponseBody;
  }

  async applyCompletePatch(body: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
    unified_diff: string;
    after_text: string;
    correlation_id?: string | null;
  }): Promise<PatchApplyCompleteResponseBody> {
    const res = await fetch(this.v1Url("/patches/apply-complete"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`patches/apply-complete: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as PatchApplyCompleteResponseBody;
  }

  /** 100N — governed orchestration (requires project_id + directive_id). */
  async postIdeAction(body: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    action: "ASK" | "RUN_WORKFLOW" | "PROPOSE_PATCH";
    prompt?: string | null;
    intent_for_router?: string | null;
    reviewer_rejections_remaining?: number;
    actor_id?: string | null;
  }): Promise<IdeActionResponseBody> {
    const res = await fetch(this.v1Url("/ide/action"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`ide/action: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as IdeActionResponseBody;
  }

  async postIdeChat(directiveId: string, prompt: string): Promise<IdeChatResponse> {
    const res = await fetch(this.v1Url("/ide/chat"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        directive_id: directiveId,
        prompt,
        actor_id: "vscode-trident-extension",
      }),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`ide/chat: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as IdeChatResponse;
  }

  async getIdeStatus(directiveId: string): Promise<IdeStatusResponse> {
    const res = await fetch(this.v1Url(`/ide/status/${directiveId}`), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`ide/status: HTTP ${res.status}`);
    }
    return (await res.json()) as IdeStatusResponse;
  }

  async getIdeProofSummary(directiveId: string): Promise<IdeProofSummaryResponse> {
    const res = await fetch(this.v1Url(`/ide/proof-summary/${directiveId}`), {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`ide/proof-summary: HTTP ${res.status}`);
    }
    return (await res.json()) as IdeProofSummaryResponse;
  }

  // ── Decision engine (DECISION_ENGINE_001 / VSCODE_DECISION_001) ─────────

  async getDecision(
    projectId: string,
    directiveId: string,
    patchId?: string | null,
    bearerToken?: string
  ): Promise<DecisionResponse> {
    let url = this.v1Url(`/projects/${projectId}/directives/${directiveId}/decision`);
    if (patchId) url += `?patch_id=${encodeURIComponent(patchId)}`;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (bearerToken) headers["Authorization"] = `Bearer ${bearerToken}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`decision: HTTP ${res.status}`);
    return (await res.json()) as DecisionResponse;
  }

  async recordDecision(
    projectId: string,
    directiveId: string,
    patchId?: string | null,
    bearerToken?: string
  ): Promise<DecisionRecordResponse> {
    let url = this.v1Url(`/projects/${projectId}/directives/${directiveId}/decision/record`);
    if (patchId) url += `?patch_id=${encodeURIComponent(patchId)}`;
    const headers: Record<string, string> = { Accept: "application/json", "Content-Type": "application/json" };
    if (bearerToken) headers["Authorization"] = `Bearer ${bearerToken}`;
    const res = await fetch(url, { method: "POST", headers, body: "" });
    if (!res.ok) throw new Error(`decision/record: HTTP ${res.status}`);
    return (await res.json()) as DecisionRecordResponse;
  }

  // ── Execution state (STATUS_001 / VSCODE_001) ────────────────────────────

  async getExecutionState(
    projectId: string,
    directiveId: string,
    bearerToken?: string
  ): Promise<ExecutionStateResponse> {
    const url = this.v1Url(`/projects/${projectId}/directives/${directiveId}/execution-state`);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (bearerToken) {
      headers["Authorization"] = `Bearer ${bearerToken}`;
    }
    const res = await fetch(url, { headers });
    if (res.status === 401 || res.status === 403) {
      throw new ExecutionStateAuthError(`execution-state: HTTP ${res.status}`);
    }
    if (!res.ok) {
      throw new Error(`execution-state: HTTP ${res.status}`);
    }
    return (await res.json()) as ExecutionStateResponse;
  }

  async createDirective(body: CreateDirectiveBody): Promise<CreateDirectiveResponseBody> {
    const res = await fetch(this.v1Url("/directives/"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`create directive: HTTP ${res.status} ${text}`);
    }
    return JSON.parse(text) as CreateDirectiveResponseBody;
  }
}
