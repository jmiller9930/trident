import * as vscode from "vscode";
import { TridentClient } from "../api/tridentClient";
import { getGovernanceIdentity } from "../utils/config";
import { relativePathIfGoverned } from "../locking/lockInterceptor";
import { writeGovernedFileUtf8 } from "./patchApplier";
import { looksLikeUnifiedDiff } from "./patchValidator";
import { PatchClient } from "./patchClient";

function panelHtml(nonce: string, beforeText: string): string {
  const safeBefore = JSON.stringify(beforeText);
  return `<!DOCTYPE html>
<html><head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';" />
<style>
body{font-family:system-ui,sans-serif;padding:12px;}
textarea{width:100%;box-sizing:border-box;font-family:monospace;min-height:180px;}
pre.diff{background:#111;color:#eee;padding:8px;overflow:auto;max-height:280px;font-size:12px;white-space:pre-wrap;}
button{margin:6px 6px 0 0;}
.summary{color:#555;margin:8px 0;}
.err{color:#b00;}
</style></head><body>
<h3>Trident patch (100M)</h3>
<p>Edit proposed content, then <strong>Propose patch</strong>. Review the unified diff, then record or reject.</p>
<label>Proposed file content</label>
<textarea id="after"></textarea>
<div><button id="prop">Propose patch</button></div>
<p class="summary" id="sum"></p>
<pre class="diff" id="diff"></pre>
<div id="actions" style="display:none">
<button id="apply">Write file to disk &amp; record on server</button>
<button id="rej">Reject</button>
</div>
<p class="err" id="err"></p>
<script nonce="${nonce}">
(function(){
  const vscode = acquireVsCodeApi();
  const initial = ${safeBefore};
  const ta = document.getElementById('after');
  ta.value = initial;
  let correlationId = null;
  let unifiedDiff = '';
  let resultText = '';
  document.getElementById('prop').onclick = () => {
    document.getElementById('err').textContent = '';
    vscode.postMessage({ type: 'propose', afterText: ta.value });
  };
  document.getElementById('apply').onclick = () => {
    document.getElementById('err').textContent = '';
    vscode.postMessage({ type: 'applyComplete', correlationId: correlationId, unifiedDiff: unifiedDiff, afterText: resultText });
  };
  document.getElementById('rej').onclick = () => {
    vscode.postMessage({ type: 'reject', correlationId: correlationId });
  };
  window.addEventListener('message', (ev) => {
    const m = ev.data;
    if (m.type === 'proposed') {
      correlationId = m.correlation_id;
      unifiedDiff = m.unified_diff;
      resultText = m.result_text;
      document.getElementById('sum').textContent = m.summary || '';
      document.getElementById('diff').textContent = m.unified_diff || '';
      document.getElementById('actions').style.display = 'block';
    }
    if (m.type === 'error') {
      document.getElementById('err').textContent = m.message || 'error';
    }
  });
})();
</script>
</body></html>`;
}

type WebviewMsg =
  | { type: "propose"; afterText?: string }
  | { type: "reject"; correlationId?: string | null }
  | { type: "applyComplete"; correlationId?: string | null; unifiedDiff?: string; afterText?: string };

export function registerPatchWorkflow(context: vscode.ExtensionContext, client: TridentClient): void {
  const patches = new PatchClient(client);
  context.subscriptions.push(
    vscode.commands.registerCommand("trident.patchWorkflow", async () => {
      const editor = vscode.window.activeTextEditor;
      const id = getGovernanceIdentity();
      const dir = context.workspaceState.get<string>("trident.selectedDirectiveId");
      if (!editor || !id || !dir) {
        void vscode.window.showErrorMessage(
          "Trident: set trident.projectId, trident.userId, select a directive, open a workspace file."
        );
        return;
      }
      const rel = relativePathIfGoverned(editor.document);
      if (!rel) {
        void vscode.window.showErrorMessage("Trident: active file must be saved under a workspace folder.");
        return;
      }
      const beforeText = editor.document.getText();
      const uri = editor.document.uri;
      const nonce = String(Math.random()).slice(2);
      const panel = vscode.window.createWebviewPanel(
        "tridentPatchWorkflow",
        `Trident patch: ${rel}`,
        vscode.ViewColumn.Beside,
        { enableScripts: true, retainContextWhenHidden: true }
      );
      panel.webview.html = panelHtml(nonce, beforeText);

      panel.webview.onDidReceiveMessage(async (msg: WebviewMsg) => {
        if (msg.type === "propose") {
          try {
            const res = await patches.propose({
              project_id: id.projectId,
              directive_id: dir,
              agent_role: id.agentRole,
              user_id: id.userId,
              file_path: rel,
              before_text: beforeText,
              after_text: msg.afterText ?? "",
            });
            if (!looksLikeUnifiedDiff(res.unified_diff)) {
              panel.webview.postMessage({
                type: "error",
                message: "Server did not return a valid unified diff.",
              });
              return;
            }
            panel.webview.postMessage({ type: "proposed", ...res });
          } catch (e) {
            panel.webview.postMessage({
              type: "error",
              message: e instanceof Error ? e.message : String(e),
            });
          }
          return;
        }
        if (msg.type === "reject") {
          try {
            await patches.reject({
              project_id: id.projectId,
              directive_id: dir,
              agent_role: id.agentRole,
              user_id: id.userId,
              file_path: rel,
              correlation_id: msg.correlationId ?? undefined,
            });
            void vscode.window.showInformationMessage("Trident: patch rejected (audited).");
          } catch (e) {
            void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
          }
          panel.dispose();
          return;
        }
        if (msg.type === "applyComplete") {
          try {
            const afterText = msg.afterText ?? "";
            await writeGovernedFileUtf8(uri, afterText);
            await patches.applyComplete({
              project_id: id.projectId,
              directive_id: dir,
              agent_role: id.agentRole,
              user_id: id.userId,
              file_path: rel,
              unified_diff: msg.unifiedDiff ?? "",
              after_text: afterText,
              correlation_id: msg.correlationId ?? undefined,
            });
            void vscode.window.showInformationMessage("Trident: patch written and recorded (proof + audit).");
          } catch (e) {
            void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
          }
          panel.dispose();
        }
      });
    })
  );
}
