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
