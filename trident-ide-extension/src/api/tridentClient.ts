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
}
