import * as vscode from "vscode";
import { TridentClient, type IdeActionResponseBody, type IdeStatusResponse } from "../api/tridentClient";
import { getGovernanceIdentity, humanLedgerState, humanStatus, isDebugMode } from "../utils/config";
import { TridentStatusBar } from "../statusBar/tridentStatusBar";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getNonce(): string {
  let t = "";
  const c = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) t += c.charAt(Math.floor(Math.random() * c.length));
  return t;
}

function buildHtml(
  nonce: string,
  title: string,
  cspSource: string,
  debugMode: boolean
): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'" />
  <style>
    body{font-family:var(--vscode-font-family);padding:8px;color:var(--vscode-foreground);font-size:13px;}
    .title{font-weight:600;margin-bottom:4px;font-size:14px;}
    .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;margin-bottom:8px;}
    .pill-running{background:var(--vscode-statusBarItem-activeBackground);color:#fff;}
    .pill-complete{background:#1e7e34;color:#fff;}
    .pill-waiting{background:#856404;color:#fff;}
    .pill-failed{background:#7b1a1a;color:#fff;}
    .pill-default{background:var(--vscode-badge-background);color:var(--vscode-badge-foreground);}
    .routing{font-size:11px;opacity:0.85;margin-bottom:10px;}
    .routing-ext{color:var(--vscode-statusBarItem-warningForeground);}
    textarea{width:100%;height:80px;box-sizing:border-box;background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border);font-family:var(--vscode-editor-font-family);}
    button{margin-top:8px;margin-right:8px;padding:6px 12px;cursor:pointer;background:var(--vscode-button-background);color:var(--vscode-button-foreground);border:none;border-radius:3px;}
    button:hover{background:var(--vscode-button-hoverBackground);}
    .reply{white-space:pre-wrap;margin-top:12px;padding:8px;background:var(--vscode-textBlockQuote-background);border-radius:4px;font-size:12px;min-height:40px;}
    .debug{font-size:11px;opacity:0.75;margin-top:8px;white-space:pre-wrap;font-family:monospace;display:${debugMode ? "block" : "none"};}
    .sep{border:none;border-top:1px solid var(--vscode-panel-border);margin:12px 0;}
    .agent-badge{font-size:11px;opacity:0.8;margin-top:4px;}
  </style>
</head>
<body>
  <div class="title" id="task-title">${escapeHtml(title)}</div>
  <span class="pill pill-default" id="status-pill">Loading…</span>
  <div class="agent-badge" id="agent-badge"></div>
  <div class="routing" id="routing-badge"></div>
  <hr class="sep" />
  <textarea id="prompt" placeholder="Ask a question or describe what you want to do…"></textarea>
  <div>
    <button id="send">Ask</button>
    <button id="run">Run workflow step</button>
    <button id="proof">View proof summary</button>
  </div>
  <div class="reply" id="out">Ready.</div>
  <pre class="debug" id="debug"></pre>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    function statusClass(s) {
      if (s === 'Running') return 'pill-running';
      if (s === 'Complete' || s === 'Closed') return 'pill-complete';
      if (s === 'Waiting' || s === 'In Review') return 'pill-waiting';
      if (s === 'Failed') return 'pill-failed';
      return 'pill-default';
    }
    document.getElementById('send').addEventListener('click', () =>
      vscode.postMessage({ type: 'send', text: document.getElementById('prompt').value }));
    document.getElementById('run').addEventListener('click', () =>
      vscode.postMessage({ type: 'runWorkflow' }));
    document.getElementById('proof').addEventListener('click', () =>
      vscode.postMessage({ type: 'viewProof' }));
    window.addEventListener('message', (event) => {
      const m = event.data;
      if (m.type === 'reply') {
        document.getElementById('out').textContent = m.reply || '';
        if (m.debug) document.getElementById('debug').textContent = m.debug;
      }
      if (m.type === 'error') {
        document.getElementById('out').textContent = '⚠ ' + (m.message || 'Unknown error');
      }
      if (m.type === 'statusUpdate') {
        const pill = document.getElementById('status-pill');
        const s = m.status || 'Draft';
        pill.textContent = s;
        pill.className = 'pill ' + statusClass(s);
        const ab = document.getElementById('agent-badge');
        ab.textContent = m.agent ? 'Agent: ' + m.agent : '';
        const rb = document.getElementById('routing-badge');
        if (m.routingOutcome) {
          const cls = m.routingOutcome === 'EXTERNAL' ? 'routing routing-ext' : 'routing';
          rb.className = cls;
          rb.textContent = m.routingOutcome === 'EXTERNAL'
            ? '⬆ External · ' + (m.routingTrigger || 'escalated') + (m.routingModel ? ' · ' + m.routingModel : '')
            : '⬇ Local' + (m.routingModel ? ' · ' + m.routingModel : '');
        } else {
          rb.textContent = '';
        }
      }
    });
  </script>
</body>
</html>`;
}

function debugMeta(res: IdeActionResponseBody): string {
  return JSON.stringify(
    {
      correlation_id: res.correlation_id,
      action: res.action,
      directive_status: res.directive_status,
      task_ledger_state: res.task_ledger_state,
      current_agent_role: res.current_agent_role,
      proof_object_id: res.proof_object_id,
      nodes_executed: res.nodes_executed,
      router: res.router,
      patch_guidance: res.patch_guidance,
    },
    null,
    2
  );
}

function pushStatusUpdate(
  panel: vscode.WebviewPanel,
  status: IdeStatusResponse
): void {
  const rd = status.last_routing_decision;
  void panel.webview.postMessage({
    type: "statusUpdate",
    status: humanStatus(status.directive_status),
    agent: status.current_agent_role,
    routingOutcome: rd?.routing_outcome ?? null,
    routingTrigger: rd?.escalation_trigger_code ?? null,
    routingModel: status.last_routing_model ?? null,
  });
}

export async function openChatPanel(
  context: vscode.ExtensionContext,
  client: TridentClient,
  statusBar: TridentStatusBar
): Promise<void> {
  const identity = getGovernanceIdentity();
  if (!identity) {
    void vscode.window.showErrorMessage(
      "Trident: set trident.projectId and trident.userId to use the chat panel."
    );
    return;
  }

  let directiveId = context.workspaceState.get<string>("trident.selectedDirectiveId");
  let directiveTitle = context.workspaceState.get<string>("trident.selectedDirectiveTitle") ?? directiveId ?? "Task";

  if (!directiveId) {
    const list = await client.listDirectives();
    const pick = await vscode.window.showQuickPick(
      list.items.map((i) => ({ label: i.title, description: humanStatus(i.status), id: i.id })),
      { placeHolder: "Choose task to work on" }
    );
    if (!pick || !("id" in pick)) return;
    const chosen = pick as { id: string; label: string };
    directiveId = chosen.id;
    directiveTitle = chosen.label;
    void context.workspaceState.update("trident.selectedDirectiveId", directiveId);
    void context.workspaceState.update("trident.selectedDirectiveTitle", directiveTitle);
  }

  const panel = vscode.window.createWebviewPanel(
    "tridentChat",
    `Trident: ${directiveTitle}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  const nonce = getNonce();
  panel.webview.html = buildHtml(nonce, directiveTitle, panel.webview.cspSource, isDebugMode());

  // Initial status push
  client.getIdeStatus(directiveId).then((s) => {
    pushStatusUpdate(panel, s);
    statusBar.updateFromIdeStatus(s);
  }).catch(() => {/* silent if offline */});

  // Poll every 8 s while panel visible
  const pollHandle = setInterval(() => {
    if (!panel.visible) return;
    client.getIdeStatus(directiveId!).then((s) => {
      pushStatusUpdate(panel, s);
      statusBar.updateFromIdeStatus(s);
    }).catch(() => {/* silent */});
  }, 8000);
  panel.onDidDispose(() => clearInterval(pollHandle));

  const debug = isDebugMode();

  async function callAction(
    action: "ASK" | "RUN_WORKFLOW" | "PROPOSE_PATCH",
    prompt?: string
  ): Promise<void> {
    try {
      const body: Parameters<TridentClient["postIdeAction"]>[0] = {
        project_id: identity!.projectId,
        directive_id: directiveId!,
        agent_role: identity!.agentRole,
        action,
        actor_id: "vscode-trident-extension",
      };
      if (action === "ASK" || action === "PROPOSE_PATCH") {
        body.prompt = prompt ?? "";
      }
      const res = await client.postIdeAction(body);
      await panel.webview.postMessage({
        type: "reply",
        reply: res.reply ?? "",
        debug: debug ? debugMeta(res) : "",
      });
      // Update status bar + pill from action response
      statusBar.updateFromIdeStatus({
        last_routing_decision: res.router
          ? { routing_outcome: res.router.route ?? undefined }
          : null,
        last_routing_model: undefined,
      });
      // Refresh proper status
      client.getIdeStatus(directiveId!).then((s) => {
        pushStatusUpdate(panel, s);
        statusBar.updateFromIdeStatus(s);
      }).catch(() => {/* silent */});
    } catch (e) {
      await panel.webview.postMessage({
        type: "error",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  }

  panel.webview.onDidReceiveMessage(async (msg: { type?: string; text?: string }) => {
    if (msg.type === "send") {
      await callAction("ASK", typeof msg.text === "string" ? msg.text : "");
    } else if (msg.type === "runWorkflow") {
      await callAction("RUN_WORKFLOW");
    } else if (msg.type === "proposePatch") {
      await callAction("PROPOSE_PATCH", typeof msg.text === "string" ? msg.text : "");
    } else if (msg.type === "viewProof") {
      const summary = await client.getIdeProofSummary(directiveId!);
      await panel.webview.postMessage({
        type: "reply",
        reply: [
          `Task: ${summary.title}`,
          `Status: ${humanStatus(summary.directive_status)}`,
          `Ledger: ${humanLedgerState(summary.ledger_state)}`,
          `Proofs recorded: ${summary.proof_count}`,
          summary.last_routing_model ? `Last model: ${summary.last_routing_model}` : null,
          summary.last_patch_event?.file_path ? `Last patch: ${String(summary.last_patch_event.file_path)}` : null,
        ].filter(Boolean).join("\n"),
        debug: debug ? JSON.stringify(summary, null, 2) : "",
      });
    }
  });
}
