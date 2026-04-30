import { useCallback, useEffect, useMemo, useState } from "react";
import { apiJson, getApiBase } from "./api";

type NavKey = "directives" | "memory" | "agents" | "git" | "logs";

type DirectiveSummary = {
  id: string;
  workspace_id: string;
  project_id: string;
  title: string;
  status: string;
  graph_id?: string | null;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

type TaskLedgerSummary = {
  id: string;
  directive_id: string;
  current_state: string;
  current_agent_role: string;
  current_owner_user_id: string | null;
  last_transition_at: string;
  created_at: string;
  updated_at: string;
};

type DirectiveDetail = {
  directive: DirectiveSummary;
  task_ledger: TaskLedgerSummary;
};

type MemoryDirectivePayload = Record<string, unknown>;

export default function App() {
  const [nav, setNav] = useState<NavKey>("directives");
  const [directives, setDirectives] = useState<DirectiveSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DirectiveDetail | null>(null);
  const [memory, setMemory] = useState<MemoryDirectivePayload | null>(null);
  const [projectMemory, setProjectMemory] = useState<Record<string, unknown> | null>(null);
  const [schemaStatus, setSchemaStatus] = useState<Record<string, unknown> | null>(null);
  const [nikeEvents, setNikeEvents] = useState<unknown[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [createWs, setCreateWs] = useState("");
  const [createProj, setCreateProj] = useState("");
  const [createUser, setCreateUser] = useState("");
  const [createTitle, setCreateTitle] = useState("");

  const [mcpCmd, setMcpCmd] = useState("echo proof");
  const [mcpTarget, setMcpTarget] = useState("shell_sim");
  const [mcpRole, setMcpRole] = useState("engineer");
  const [mcpApprove, setMcpApprove] = useState(false);
  const [routerIntent, setRouterIntent] = useState("run workflow via LangGraph");

  const [lastApiPreview, setLastApiPreview] = useState<string>("");

  const refreshDirectives = useCallback(async () => {
    try {
      const data = await apiJson<{ items: DirectiveSummary[] }>("/v1/directives/");
      setDirectives(data.items);
      setLoadErr(null);
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refreshDirectives();
    apiJson<Record<string, unknown>>("/v1/system/schema-status")
      .then(setSchemaStatus)
      .catch(() => setSchemaStatus(null));
  }, [refreshDirectives]);

  useEffect(() => {
    if (nav !== "directives") return;
    const t = window.setInterval(() => void refreshDirectives(), 8000);
    return () => window.clearInterval(t);
  }, [nav, refreshDirectives]);

  const loadDetail = useCallback(async (id: string) => {
    setBusy(true);
    setLoadErr(null);
    try {
      const [d, m] = await Promise.all([
        apiJson<DirectiveDetail>(`/v1/directives/${id}`),
        apiJson<MemoryDirectivePayload>(`/v1/memory/directive/${id}`),
      ]);
      setDetail(d);
      setMemory(m);
      setLastApiPreview(JSON.stringify({ directive: d.directive.id, memory_keys: Object.keys(m) }, null, 2));
    } catch (e) {
      setDetail(null);
      setMemory(null);
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setMemory(null);
      return;
    }
    void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const loadProjectMemory = useCallback(async (projectId: string) => {
    setBusy(true);
    try {
      const pm = await apiJson<Record<string, unknown>>(`/v1/memory/project/${projectId}`);
      setProjectMemory(pm);
      setLoadErr(null);
    } catch (e) {
      setProjectMemory(null);
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (nav !== "memory") return;
    const pid =
      detail?.directive.project_id ??
      (directives[0]?.project_id as string | undefined);
    if (pid) void loadProjectMemory(pid);
  }, [nav, detail, directives, loadProjectMemory]);

  useEffect(() => {
    if (nav !== "logs") return;
    const q = selectedId ? `?directive_id=${selectedId}&limit=40` : "?limit=40";
    apiJson<{ items: unknown[] }>(`/v1/nike/events${q}`)
      .then((r) => setNikeEvents(r.items))
      .catch(() => setNikeEvents([]));
  }, [nav, selectedId]);

  const taskId = detail?.task_ledger.id;

  const gitProofHints = useMemo(() => {
    const proofs = (memory?.proof_objects as Array<{ proof_type?: string }> | undefined) ?? [];
    return proofs.filter((p) => String(p.proof_type ?? "").startsWith("GIT"));
  }, [memory]);

  async function createDirective(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setLoadErr(null);
    try {
      const body = {
        workspace_id: createWs.trim(),
        project_id: createProj.trim(),
        title: createTitle.trim() || "Untitled directive",
        created_by_user_id: createUser.trim(),
        status: "DRAFT",
      };
      const created = await apiJson<DirectiveDetail>("/v1/directives/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setLastApiPreview(JSON.stringify(created, null, 2));
      await refreshDirectives();
      setSelectedId(created.directive.id);
      setCreateTitle("");
    } catch (err) {
      const e = err as Error & { body?: unknown };
      setLoadErr(e.message + (e.body ? ` — ${JSON.stringify(e.body)}` : ""));
    } finally {
      setBusy(false);
    }
  }

  async function runWorkflow() {
    if (!selectedId) return;
    setBusy(true);
    setLoadErr(null);
    try {
      const out = await apiJson<Record<string, unknown>>(
        `/v1/directives/${selectedId}/workflow/run?reviewer_rejections_remaining=0`,
        { method: "POST" },
      );
      setLastApiPreview(JSON.stringify(out, null, 2));
      await loadDetail(selectedId);
      await refreshDirectives();
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function mcpClassify() {
    if (!selectedId || !taskId) return;
    setBusy(true);
    try {
      const body = {
        directive_id: selectedId,
        task_id: taskId,
        agent_role: mcpRole.trim(),
        command: mcpCmd,
        target: mcpTarget.trim(),
      };
      const out = await apiJson<unknown>("/v1/mcp/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setLastApiPreview(JSON.stringify(out, null, 2));
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function mcpExecute() {
    if (!selectedId || !taskId) return;
    setBusy(true);
    try {
      const body = {
        directive_id: selectedId,
        task_id: taskId,
        agent_role: mcpRole.trim(),
        command: mcpCmd,
        target: mcpTarget.trim(),
        explicitly_approved: mcpApprove,
      };
      const out = await apiJson<unknown>("/v1/mcp/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setLastApiPreview(JSON.stringify(out, null, 2));
      if (selectedId) await loadDetail(selectedId);
    } catch (e) {
      const err = e as Error & { body?: unknown };
      setLoadErr(err.message + (err.body ? ` — ${JSON.stringify(err.body)}` : ""));
    } finally {
      setBusy(false);
    }
  }

  async function routerProbe() {
    if (!selectedId || !taskId) return;
    setBusy(true);
    try {
      const body = {
        directive_id: selectedId,
        task_id: taskId,
        agent_role: mcpRole.trim(),
        intent: routerIntent,
        payload: {},
      };
      const out = await apiJson<unknown>("/v1/router/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setLastApiPreview(JSON.stringify(out, null, 2));
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const ledger = detail?.task_ledger;
  const handoffs = (memory?.handoffs as unknown[]) ?? [];
  const entries = (memory?.memory_entries as unknown[]) ?? [];

  return (
    <div className="app-shell">
      <nav className="side">
        <div className="small muted" style={{ padding: "0 0.65rem 0.75rem" }}>
          API: <code className="small">{getApiBase()}</code>
        </div>
        {(
          [
            ["directives", "Directives"],
            ["memory", "Memory"],
            ["agents", "Agents"],
            ["git", "Git / locks"],
            ["logs", "Execution logs"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" className={nav === k ? "active" : ""} onClick={() => setNav(k)}>
            {label}
          </button>
        ))}
      </nav>

      <main className="workspace">
        <div className="header-row">
          <h1>Trident — web control plane</h1>
          {schemaStatus && (
            <span className={`badge ${schemaStatus.ok ? "ok" : "pending"}`}>
              schema {schemaStatus.ok ? "ok" : "check"}
            </span>
          )}
        </div>
        {loadErr && <div className="err-text card">{loadErr}</div>}

        {nav === "directives" && (
          <>
            <p className="muted small">
              Live data from <code>/v1/directives</code>. Select a directive to drive MCP/router panels.
            </p>
            <div className="row" style={{ marginBottom: "0.75rem" }}>
              <button type="button" className="ghost" onClick={() => void refreshDirectives()} disabled={busy}>
                Refresh list
              </button>
              {selectedId && (
                <button type="button" className="primary" onClick={() => void runWorkflow()} disabled={busy}>
                  Run LangGraph workflow
                </button>
              )}
            </div>
            {directives.map((d) => (
              <div
                key={d.id}
                role="button"
                tabIndex={0}
                className={`card clickable ${selectedId === d.id ? "active" : ""}`}
                onClick={() => setSelectedId(d.id)}
                onKeyDown={(ev) => ev.key === "Enter" && setSelectedId(d.id)}
              >
                <div className="row">
                  <strong>{d.title}</strong>
                  <span className="badge pending">{d.status}</span>
                </div>
                <div className="small muted">{d.id}</div>
              </div>
            ))}
            <h2>Create directive</h2>
            <form className="card" onSubmit={createDirective}>
              <label className="small muted">workspace_id (uuid)</label>
              <input value={createWs} onChange={(e) => setCreateWs(e.target.value)} required />
              <label className="small muted">project_id (uuid)</label>
              <input value={createProj} onChange={(e) => setCreateProj(e.target.value)} required />
              <label className="small muted">created_by_user_id (uuid)</label>
              <input value={createUser} onChange={(e) => setCreateUser(e.target.value)} required />
              <label className="small muted">title</label>
              <input value={createTitle} onChange={(e) => setCreateTitle(e.target.value)} />
              <div style={{ marginTop: "0.5rem" }}>
                <button type="submit" className="primary" disabled={busy}>
                  POST /v1/directives/
                </button>
              </div>
            </form>
          </>
        )}

        {nav === "memory" && (
          <>
            <p className="muted small">
              Project-scoped memory via <code>/v1/memory/project/{"{id}"}</code>
              {detail ? ` — project ${detail.directive.project_id}` : directives[0] ? ` — project ${directives[0].project_id}` : ""}.
            </p>
            {projectMemory ? (
              <pre className="json card">{JSON.stringify(projectMemory, null, 2)}</pre>
            ) : (
              <p className="muted">Load directives first or select a directive with a project.</p>
            )}
          </>
        )}

        {nav === "agents" && (
          <>
            <p className="muted small">
              Agent visibility comes from <code>task_ledger.current_agent_role</code> and memory handoffs — no extra agent APIs.
            </p>
            {ledger ? (
              <div className="card">
                <div>
                  <strong>Current role:</strong> {ledger.current_agent_role}
                </div>
                <div className="small muted">Ledger state: {ledger.current_state}</div>
              </div>
            ) : (
              <p className="muted">Select a directive.</p>
            )}
            <p className="small muted">
              Spine nodes (architect → engineer → reviewer → documentation → close) appear in workflow run output and audits after execution.
            </p>
          </>
        )}

        {nav === "git" && (
          <>
            <div className="card" style={{ borderColor: "var(--warn)" }}>
              <strong>UI limitation (100U)</strong>
              <p className="small muted" style={{ margin: "0.45rem 0 0" }}>
                No dedicated Git read APIs — per architect: surface locks/proofs/audits only. Repo status and diffs are not exposed as standalone endpoints.
              </p>
            </div>
            <h2>Proof objects (GIT-related)</h2>
            {gitProofHints.length ? (
              <pre className="json card">{JSON.stringify(gitProofHints, null, 2)}</pre>
            ) : (
              <p className="muted small">
                No GIT_* proof rows on this directive yet. Lock flows may still validate Git server-side during acquire/simulated-mutation.
              </p>
            )}
          </>
        )}

        {nav === "logs" && (
          <>
            <p className="muted small">Recent Nike events {selectedId ? `(filtered)` : `(global)`}.</p>
            <pre className="json card">{JSON.stringify(nikeEvents, null, 2)}</pre>
          </>
        )}

        <h2>Directive workspace</h2>
        {!selectedId && <p className="muted">Select a directive.</p>}
        {detail && (
          <div className="card">
            <div className="row">
              <strong>{detail.directive.title}</strong>
              <span className="badge pending">{detail.directive.status}</span>
            </div>
            <div className="small muted">Graph id: {detail.directive.graph_id ?? "—"}</div>
          </div>
        )}
        {entries.length > 0 && (
          <>
            <h3 className="muted small">Memory timeline (structured)</h3>
            {entries.map((row, i) => (
              <pre
                key={
                  typeof row === "object" && row !== null && "id" in row
                    ? String((row as { id: string }).id)
                    : `mem-${i}`
                }
                className="json card"
              >
                {JSON.stringify(row, null, 2)}
              </pre>
            ))}
          </>
        )}
      </main>

      <aside className="control">
        <h2>LangGraph / ledger</h2>
        {ledger ? (
          <>
            <div className="card">
              <div>
                State: <strong>{ledger.current_state}</strong>
              </div>
              <div className="small muted">Agent role: {ledger.current_agent_role}</div>
              <div className="small muted">Task id: {ledger.id}</div>
            </div>
            <h3 className="muted small">Handoffs</h3>
            {handoffs.length ? (
              <pre className="json card">{JSON.stringify(handoffs, null, 2)}</pre>
            ) : (
              <p className="muted small">No handoffs returned.</p>
            )}
          </>
        ) : (
          <p className="muted small">Select a directive for ledger + handoffs (from memory read).</p>
        )}

        <h2>Subsystem router</h2>
        <textarea value={routerIntent} onChange={(e) => setRouterIntent(e.target.value)} />
        <button type="button" className="primary" style={{ marginTop: "0.35rem", width: "100%" }} disabled={!selectedId || !taskId || busy} onClick={() => void routerProbe()}>
          POST /v1/router/route
        </button>

        <h2>MCP</h2>
        <label className="small muted">agent_role</label>
        <input value={mcpRole} onChange={(e) => setMcpRole(e.target.value)} />
        <label className="small muted">target</label>
        <input value={mcpTarget} onChange={(e) => setMcpTarget(e.target.value)} />
        <label className="small muted">command</label>
        <textarea value={mcpCmd} onChange={(e) => setMcpCmd(e.target.value)} />
        <label className="row small muted">
          <input type="checkbox" checked={mcpApprove} onChange={(e) => setMcpApprove(e.target.checked)} />
          explicitly_approved (HIGH gate)
        </label>
        <div className="row" style={{ marginTop: "0.35rem" }}>
          <button type="button" className="ghost" disabled={!selectedId || !taskId || busy} onClick={() => void mcpClassify()}>
            Classify
          </button>
          <button type="button" className="primary" disabled={!selectedId || !taskId || busy} onClick={() => void mcpExecute()}>
            Execute
          </button>
        </div>

        <h2>Last API sample</h2>
        {lastApiPreview ? <pre className="json card">{lastApiPreview}</pre> : <p className="muted small">No calls yet.</p>}
      </aside>
    </div>
  );
}
