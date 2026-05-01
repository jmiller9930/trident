import * as vscode from "vscode";
import { TridentClient, type IdeStatusResponse } from "../api/tridentClient";
import { humanLedgerState, humanStatus, isDebugMode } from "../utils/config";
import { TridentStatusBar } from "../statusBar/tridentStatusBar";

function getNonce(): string {
  let t = "";
  const c = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) t += c.charAt(Math.floor(Math.random() * c.length));
  return t;
}

const SPINE_NODES = ["architect", "engineer", "reviewer", "documentation", "close"];

function nodeIndex(agent: string): number {
  const a = agent.toLowerCase().replace("documentation", "documentation");
  return SPINE_NODES.findIndex((n) => a.includes(n));
}

function buildHtml(nonce: string, cspSource: string, title: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'"/>
  <style>
    body{font-family:var(--vscode-font-family);padding:10px;color:var(--vscode-foreground);font-size:13px;}
    h2{font-size:14px;font-weight:600;margin:0 0 4px;}
    .subtitle{font-size:11px;opacity:0.8;margin-bottom:14px;}
    .timeline{list-style:none;padding:0;margin:0;}
    .timeline li{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--vscode-panel-border);}
    .circle{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:11px;font-weight:700;}
    .c-done{background:#1e7e34;color:#fff;}
    .c-active{background:var(--vscode-statusBarItem-activeBackground);color:#fff;animation:pulse 1.2s infinite;}
    .c-pending{background:var(--vscode-badge-background);color:var(--vscode-badge-foreground);}
    @keyframes pulse{0%{opacity:1}50%{opacity:0.5}100%{opacity:1}}
    .node-name{font-weight:500;flex:1;}
    .node-state{font-size:11px;opacity:0.75;}
    .routing{font-size:11px;margin-top:14px;padding:6px 8px;background:var(--vscode-textBlockQuote-background);border-radius:3px;}
    .routing-ext{color:var(--vscode-statusBarItem-warningForeground);}
    .debug{font-size:11px;opacity:0.7;white-space:pre-wrap;font-family:monospace;margin-top:10px;display:none;}
  </style>
</head>
<body>
  <h2 id="task-title">${title.replace(/</g, "&lt;")}</h2>
  <div class="subtitle" id="overall-state">Loading…</div>
  <ul class="timeline" id="timeline"></ul>
  <div class="routing" id="routing-info"></div>
  <pre class="debug" id="debug-raw"></pre>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const NODES = ${JSON.stringify(SPINE_NODES)};
    function render(data) {
      document.getElementById('task-title').textContent = data.title || 'Task';
      document.getElementById('overall-state').textContent =
        'Status: ' + (data.humanStatus || data.directive_status) +
        ' · Ledger: ' + (data.humanLedger || data.ledger_state);
      const currentIdx = data.activeNodeIndex;
      const isComplete = data.directive_status === 'COMPLETE';
      const ul = document.getElementById('timeline');
      ul.innerHTML = '';
      NODES.forEach((name, i) => {
        const li = document.createElement('li');
        let circClass, symbol;
        if (isComplete || i < currentIdx) {
          circClass = 'c-done'; symbol = '✓';
        } else if (i === currentIdx) {
          circClass = 'c-active'; symbol = '▶';
        } else {
          circClass = 'c-pending'; symbol = String(i + 1);
        }
        li.innerHTML =
          '<div class="circle ' + circClass + '">' + symbol + '</div>' +
          '<span class="node-name">' + name.charAt(0).toUpperCase() + name.slice(1) + '</span>' +
          (i === currentIdx && !isComplete ? '<span class="node-state">Running…</span>' :
           (isComplete || i < currentIdx ? '<span class="node-state">Done</span>' : ''));
        ul.appendChild(li);
      });
      const rd = data.last_routing_decision;
      const ri = document.getElementById('routing-info');
      if (rd && rd.routing_outcome) {
        const ext = rd.routing_outcome === 'EXTERNAL';
        ri.className = ext ? 'routing routing-ext' : 'routing';
        ri.textContent =
          (ext ? '⬆ External' : '⬇ Local') +
          (rd.escalation_trigger_code ? ' · ' + rd.escalation_trigger_code : '') +
          (data.last_routing_model ? ' · ' + data.last_routing_model : '');
      } else {
        ri.textContent = '';
      }
      if (data.debug) {
        const d = document.getElementById('debug-raw');
        d.style.display = 'block';
        d.textContent = data.debug;
      }
    }
    window.addEventListener('message', (e) => {
      if (e.data.type === 'update') render(e.data);
    });
  </script>
</body>
</html>`;
}

function toUpdateMsg(s: IdeStatusResponse, debugMode: boolean): Record<string, unknown> {
  const currentIdx = nodeIndex(s.current_agent_role);
  return {
    type: "update",
    title: s.title,
    directive_status: s.directive_status,
    humanStatus: humanStatus(s.directive_status),
    ledger_state: s.ledger_state,
    humanLedger: humanLedgerState(s.ledger_state),
    current_agent_role: s.current_agent_role,
    activeNodeIndex: currentIdx,
    last_routing_decision: s.last_routing_decision ?? null,
    last_routing_model: s.last_routing_model ?? null,
    debug: debugMode ? JSON.stringify(s, null, 2) : null,
  };
}

export async function openTimelinePanel(
  context: vscode.ExtensionContext,
  client: TridentClient,
  statusBar: TridentStatusBar
): Promise<void> {
  const directiveId = context.workspaceState.get<string>("trident.selectedDirectiveId");
  const directiveTitle = context.workspaceState.get<string>("trident.selectedDirectiveTitle") ?? "Task";

  if (!directiveId) {
    void vscode.window.showErrorMessage("Trident: select a task first (sidebar or createWorkRequest).");
    return;
  }

  const panel = vscode.window.createWebviewPanel(
    "tridentTimeline",
    `Progress: ${directiveTitle}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  const nonce = getNonce();
  panel.webview.html = buildHtml(nonce, panel.webview.cspSource, directiveTitle);

  const debug = isDebugMode();

  const push = async () => {
    try {
      const s = await client.getIdeStatus(directiveId);
      await panel.webview.postMessage(toUpdateMsg(s, debug));
      statusBar.updateFromIdeStatus(s);
    } catch {
      /* silent */
    }
  };

  // Initial load + poll every 3 s while visible
  await push();
  const handle = setInterval(() => {
    if (panel.visible) void push();
  }, 3000);
  panel.onDidDispose(() => clearInterval(handle));
}
