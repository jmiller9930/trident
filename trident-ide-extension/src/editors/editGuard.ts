import * as vscode from "vscode";
import { TridentClient } from "../api/tridentClient";
import { LockClient } from "../locking/lockClient";
import { relativePathIfGoverned } from "../locking/lockInterceptor";
import {
  getGovernanceIdentity,
  getLockHeartbeatIntervalSec,
  getPatchWorkflowRequired,
  isEditGovernanceEnabled,
} from "../utils/config";
import { isPatchApplyInProgress } from "../patch/patchApplyScope";

const DEBOUNCE_MS = 450;

type Held = { lockId: string; filePath: string; directiveId: string };

export function registerEditGuard(
  context: vscode.ExtensionContext,
  api: TridentClient
): vscode.OutputChannel {
  const log = vscode.window.createOutputChannel("Trident governance");
  const locks = new LockClient(api);
  const baseline = new Map<string, string>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const held = new Map<string, Held>();
  let heartbeatTimer: ReturnType<typeof setInterval> | undefined;

  function stopLockHeartbeat(): void {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = undefined;
    }
  }

  function syncLockHeartbeatTimer(): void {
    const sec = getLockHeartbeatIntervalSec();
    stopLockHeartbeat();
    if (sec <= 0 || held.size === 0) {
      return;
    }
    heartbeatTimer = setInterval(() => {
      void sendHeldHeartbeats();
    }, sec * 1000);
  }

  async function sendHeldHeartbeats(): Promise<void> {
    const id = getGovernanceIdentity();
    if (!id || held.size === 0) {
      return;
    }
    for (const [, rec] of held) {
      try {
        await locks.heartbeat({
          lock_id: rec.lockId,
          project_id: id.projectId,
          directive_id: rec.directiveId,
          agent_role: id.agentRole,
          user_id: id.userId,
          file_path: rec.filePath,
        });
      } catch (e) {
        log.appendLine(`heartbeat failed (${rec.filePath}): ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  }

  function uriKey(u: vscode.Uri): string {
    return u.toString();
  }

  function directiveId(): string | undefined {
    return context.workspaceState.get<string>("trident.selectedDirectiveId");
  }

  function governanceApplies(doc: vscode.TextDocument): boolean {
    if (!isEditGovernanceEnabled()) {
      return false;
    }
    if (!getGovernanceIdentity()) {
      return false;
    }
    if (!directiveId()) {
      return false;
    }
    return relativePathIfGoverned(doc) !== null;
  }

  async function lockMatchesSession(
    doc: vscode.TextDocument,
    rel: string
  ): Promise<boolean> {
    const id = getGovernanceIdentity();
    const dir = directiveId();
    if (!id || !dir) {
      return false;
    }
    try {
      const row = await locks.getActive(id.projectId, rel);
      if (!row) {
        return false;
      }
      return (
        row.locked_by_user_id.toLowerCase() === id.userId.toLowerCase() &&
        row.locked_by_agent_role === id.agentRole &&
        row.directive_id.toLowerCase() === dir.toLowerCase()
      );
    } catch (e) {
      log.appendLine(`lock check error: ${e instanceof Error ? e.message : String(e)}`);
      return false;
    }
  }

  async function revertToBaseline(doc: vscode.TextDocument, reason: string): Promise<void> {
    const key = uriKey(doc.uri);
    const text = baseline.get(key);
    if (text === undefined) {
      return;
    }
    const edit = new vscode.WorkspaceEdit();
    const end = doc.positionAt(doc.getText().length);
    edit.replace(doc.uri, new vscode.Range(new vscode.Position(0, 0), end), text);
    const applied = await vscode.workspace.applyEdit(edit);
    if (applied) {
      log.appendLine(`${reason}: reverted ${doc.uri.fsPath}`);
      void vscode.window.showWarningMessage(`Trident: ${reason} — edits reverted for ${relativePathIfGoverned(doc)}`);
    }
  }

  async function verifyAfterEdit(doc: vscode.TextDocument): Promise<void> {
    if (!governanceApplies(doc)) {
      return;
    }
    const rel = relativePathIfGoverned(doc);
    if (!rel) {
      return;
    }
    const ok = await lockMatchesSession(doc, rel);
    const key = uriKey(doc.uri);
    if (!ok) {
      await revertToBaseline(doc, "No valid backend lock for this file/directive");
      return;
    }
    baseline.set(key, doc.getText());
  }

  function scheduleVerify(doc: vscode.TextDocument): void {
    const key = uriKey(doc.uri);
    const t = timers.get(key);
    if (t) {
      clearTimeout(t);
    }
    timers.set(
      key,
      setTimeout(() => {
        timers.delete(key);
        void verifyAfterEdit(doc);
      }, DEBOUNCE_MS)
    );
  }

  function seedBaselines(): void {
    for (const doc of vscode.workspace.textDocuments) {
      if (governanceApplies(doc)) {
        baseline.set(uriKey(doc.uri), doc.getText());
      }
    }
  }

  seedBaselines();

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("trident")) {
        seedBaselines();
        syncLockHeartbeatTimer();
      }
    }),
    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (!governanceApplies(doc)) {
        return;
      }
      baseline.set(uriKey(doc.uri), doc.getText());
    }),
    vscode.workspace.onDidChangeTextDocument((ev) => {
      const doc = ev.document;
      if (!governanceApplies(doc)) {
        return;
      }
      if (getPatchWorkflowRequired() && !isPatchApplyInProgress()) {
        void revertToBaseline(doc, "Patch workflow required — use Trident: Patch workflow");
        return;
      }
      scheduleVerify(doc);
    }),
    vscode.workspace.onWillSaveTextDocument((ev) => {
      ev.waitUntil(
        (async (): Promise<void> => {
          const doc = ev.document;
          if (!governanceApplies(doc)) {
            return;
          }
          const rel = relativePathIfGoverned(doc);
          if (!rel) {
            return;
          }
          const ok = await lockMatchesSession(doc, rel);
          if (!ok) {
            log.appendLine(`save blocked: ${doc.uri.fsPath}`);
            throw new Error(
              "Trident: save blocked — acquire a backend lock for this file (matching project, user, agentRole, and active directive)."
            );
          }
        })()
      );
    }),
    vscode.commands.registerCommand("trident.acquireLock", async () => {
      const editor = vscode.window.activeTextEditor;
      const id = getGovernanceIdentity();
      const dir = directiveId();
      if (!editor || !id || !dir) {
        void vscode.window.showErrorMessage(
          "Trident: set trident.projectId, trident.userId, select a directive, and open a workspace file."
        );
        return;
      }
      const rel = relativePathIfGoverned(editor.document);
      if (!rel) {
        void vscode.window.showErrorMessage("Trident: active file is not under a workspace folder.");
        return;
      }
      try {
        const res = await locks.acquire({
          project_id: id.projectId,
          directive_id: dir,
          agent_role: id.agentRole,
          user_id: id.userId,
          file_path: rel,
        });
        held.set(uriKey(editor.document.uri), {
          lockId: res.lock_id,
          filePath: rel,
          directiveId: dir,
        });
        syncLockHeartbeatTimer();
        void sendHeldHeartbeats();
        baseline.set(uriKey(editor.document.uri), editor.document.getText());
        void vscode.window.showInformationMessage(`Trident: lock acquired for ${rel}`);
        log.appendLine(`acquired lock ${res.lock_id} ${rel}`);
      } catch (e) {
        void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
      }
    }),
    vscode.commands.registerCommand("trident.releaseLock", async () => {
      const editor = vscode.window.activeTextEditor;
      const id = getGovernanceIdentity();
      if (!editor || !id) {
        void vscode.window.showErrorMessage("Trident: missing identity or editor.");
        return;
      }
      const rec = held.get(uriKey(editor.document.uri));
      const dir = rec?.directiveId ?? directiveId();
      const rel = rec?.filePath ?? relativePathIfGoverned(editor.document);
      if (!dir || !rel) {
        void vscode.window.showErrorMessage("Trident: no held lock context for this file.");
        return;
      }
      const lockId = rec?.lockId;
      if (!lockId) {
        void vscode.window.showErrorMessage("Trident: acquire a lock from this session first (lock id not tracked).");
        return;
      }
      try {
        await locks.release({
          lock_id: lockId,
          project_id: id.projectId,
          directive_id: dir,
          agent_role: id.agentRole,
          user_id: id.userId,
          file_path: rel,
        });
        held.delete(uriKey(editor.document.uri));
        syncLockHeartbeatTimer();
        void vscode.window.showInformationMessage(`Trident: lock released for ${rel}`);
        log.appendLine(`released lock ${lockId} ${rel}`);
      } catch (e) {
        void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
      }
    }),
    log,
    { dispose: stopLockHeartbeat }
  );

  return log;
}
