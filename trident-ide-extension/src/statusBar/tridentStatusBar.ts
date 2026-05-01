import * as vscode from "vscode";

interface RoutingInfo {
  outcome: string;       // LOCAL | EXTERNAL
  triggerCode?: string;  // LOW_CONFIDENCE etc.
  model?: string;        // sonnet_46_external etc.
}

export class TridentStatusBar {
  private readonly _lockBar: vscode.StatusBarItem;
  private readonly _routingBar: vscode.StatusBarItem;

  private _lockId: string | null = null;
  private _lockFile: string | null = null;

  constructor(context: vscode.ExtensionContext) {
    this._lockBar = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      101
    );
    this._routingBar = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100
    );
    this._lockBar.tooltip = "Trident: lock held. Click to release.";
    this._lockBar.command = "trident.releaseLock";
    context.subscriptions.push(this._lockBar, this._routingBar);
    this._routingBar.show();
    this.setRoutingIdle();
  }

  showLock(lockId: string, filePath: string): void {
    this._lockId = lockId;
    this._lockFile = filePath;
    const short = filePath.split("/").pop() ?? filePath;
    this._lockBar.text = `$(lock) ${short}`;
    this._lockBar.show();
  }

  clearLock(): void {
    this._lockId = null;
    this._lockFile = null;
    this._lockBar.hide();
  }

  get currentLockId(): string | null {
    return this._lockId;
  }

  get currentLockFile(): string | null {
    return this._lockFile;
  }

  setRoutingIdle(): void {
    this._routingBar.text = "$(circuit-board) Trident";
    this._routingBar.tooltip = "Trident model router: no recent decision";
    this._routingBar.color = undefined;
  }

  setRouting(info: RoutingInfo): void {
    const label =
      info.outcome === "EXTERNAL"
        ? `$(circuit-board) EXT · ${info.triggerCode ?? "escalated"}`
        : `$(circuit-board) LOCAL`;

    this._routingBar.text = label;
    this._routingBar.tooltip = [
      `Outcome: ${info.outcome}`,
      info.triggerCode ? `Trigger: ${info.triggerCode}` : null,
      info.model ? `Model: ${info.model}` : null,
    ]
      .filter(Boolean)
      .join(" | ");

    this._routingBar.color =
      info.outcome === "EXTERNAL"
        ? new vscode.ThemeColor("statusBarItem.warningForeground")
        : undefined;
  }

  updateFromIdeStatus(data: {
    last_routing_decision?: {
      routing_outcome?: string;
      escalation_trigger_code?: string;
    } | null;
    last_routing_model?: string | null;
  }): void {
    const rd = data.last_routing_decision;
    if (!rd || !rd.routing_outcome) {
      this.setRoutingIdle();
      return;
    }
    this.setRouting({
      outcome: rd.routing_outcome,
      triggerCode: rd.escalation_trigger_code ?? undefined,
      model: data.last_routing_model ?? undefined,
    });
  }
}
