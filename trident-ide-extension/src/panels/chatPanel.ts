import * as vscode from "vscode";
import { TridentClient } from "../api/tridentClient";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getNonce(): string {
  let text = "";
  const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

export async function openChatPanel(
  context: vscode.ExtensionContext,
  client: TridentClient
): Promise<void> {
  let directiveId = context.workspaceState.get<string>("trident.selectedDirectiveId");
  if (!directiveId) {
    const list = await client.listDirectives();
    const pick = await vscode.window.showQuickPick(
      list.items.map((i) => ({ label: i.title, description: i.status, id: i.id })),
      { placeHolder: "Choose directive for chat context" }
    );
    if (!pick || !("id" in pick)) {
      return;
    }
    directiveId = (pick as { id: string }).id;
  }

  const panel = vscode.window.createWebviewPanel(
    "tridentChat",
    "Trident chat",
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  const nonce = getNonce();
  panel.webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'" />
  <style>
    body { font-family: var(--vscode-font-family); padding: 8px; color: var(--vscode-foreground); }
    textarea { width: 100%; height: 80px; box-sizing: border-box; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); }
    button { margin-top: 8px; padding: 6px 12px; cursor: pointer; }
    pre { white-space: pre-wrap; margin-top: 12px; padding: 8px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; }
    .meta { font-size: 11px; opacity: 0.85; margin-top: 6px; }
  </style>
</head>
<body>
  <p>Directive context: <strong>${escapeHtml(directiveId)}</strong></p>
  <textarea id="prompt" placeholder="Message (sent to Trident API only)"></textarea>
  <div><button id="send">Send</button></div>
  <pre id="out"></pre>
  <div class="meta" id="meta"></div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    document.getElementById('send').addEventListener('click', () => {
      const text = document.getElementById('prompt').value;
      vscode.postMessage({ type: 'send', text });
    });
    window.addEventListener('message', (event) => {
      const m = event.data;
      if (m.type === 'reply') {
        document.getElementById('out').textContent = m.reply || '';
        document.getElementById('meta').textContent = m.meta || '';
      }
      if (m.type === 'error') {
        document.getElementById('out').textContent = 'Error: ' + (m.message || '');
      }
    });
  </script>
</body>
</html>`;

  panel.webview.onDidReceiveMessage(async (msg: { type?: string; text?: string }) => {
    if (msg.type !== "send" || typeof msg.text !== "string") {
      return;
    }
    try {
      const res = await client.postIdeChat(directiveId!, msg.text);
      await panel.webview.postMessage({
        type: "reply",
        reply: res.reply,
        meta: `correlation_id=${res.correlation_id} proof_object_id=${res.proof_object_id}`,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      await panel.webview.postMessage({ type: "error", message });
    }
  });
}
