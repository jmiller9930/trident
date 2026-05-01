import * as vscode from "vscode";
import { TridentClient } from "../api/tridentClient";
import { TridentStatusBar } from "../statusBar/tridentStatusBar";
import { humanStatus } from "../utils/config";

const DIR_HEADER_ID = "trident-directives-header";

export class TridentSidebarProvider implements vscode.TreeDataProvider<SidebarNode> {
  private readonly _onDidChange = new vscode.EventEmitter<SidebarNode | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  constructor(
    private readonly client: TridentClient,
    private readonly context: vscode.ExtensionContext,
    private readonly statusBar: TridentStatusBar
  ) {}

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(element: SidebarNode): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: SidebarNode): Promise<SidebarNode[]> {
    if (!element) {
      const conn = await this.client.connectionLabel();
      const connItem = new vscode.TreeItem(conn.label, vscode.TreeItemCollapsibleState.None);
      connItem.id = "trident-connection";
      connItem.description = conn.detail;
      connItem.iconPath = new vscode.ThemeIcon(
        conn.label.includes("connected") ? "debug-start" : "error"
      );

      const newTask = new vscode.TreeItem("New task…", vscode.TreeItemCollapsibleState.None);
      newTask.id = "trident-new-task";
      newTask.iconPath = new vscode.ThemeIcon("add");
      newTask.command = { command: "trident.createWorkRequest", title: "New task" };

      const dirHeader = new vscode.TreeItem("Tasks", vscode.TreeItemCollapsibleState.Collapsed);
      dirHeader.id = DIR_HEADER_ID;
      dirHeader.iconPath = new vscode.ThemeIcon("list-tree");

      const chatCmd = new vscode.TreeItem("Open chat…", vscode.TreeItemCollapsibleState.None);
      chatCmd.id = "trident-open-chat";
      chatCmd.iconPath = new vscode.ThemeIcon("comment");
      chatCmd.command = { command: "trident.openChat", title: "Open chat" };

      const timelineCmd = new vscode.TreeItem("Task progress…", vscode.TreeItemCollapsibleState.None);
      timelineCmd.id = "trident-timeline";
      timelineCmd.iconPath = new vscode.ThemeIcon("timeline-view-icon");
      timelineCmd.command = { command: "trident.showTimeline", title: "Task progress" };

      const agentCmd = new vscode.TreeItem("Task summary…", vscode.TreeItemCollapsibleState.None);
      agentCmd.id = "trident-agent-state";
      agentCmd.iconPath = new vscode.ThemeIcon("organization");
      agentCmd.command = { command: "trident.showAgentState", title: "Task summary" };

      const statusCmd = new vscode.TreeItem("Backend status…", vscode.TreeItemCollapsibleState.None);
      statusCmd.id = "trident-status";
      statusCmd.iconPath = new vscode.ThemeIcon("pulse");
      statusCmd.command = { command: "trident.showStatus", title: "Status" };

      const selectedId = this.context.workspaceState.get<string>("trident.selectedDirectiveId");
      const selectedTitle = this.context.workspaceState.get<string>("trident.selectedDirectiveTitle");
      if (selectedId && selectedTitle) {
        const activeItem = new vscode.TreeItem(
          `Active: ${selectedTitle}`,
          vscode.TreeItemCollapsibleState.None
        );
        activeItem.id = "trident-active-task";
        activeItem.iconPath = new vscode.ThemeIcon("target");
        activeItem.tooltip = "Currently selected task";
        return [connItem, activeItem, newTask, dirHeader, chatCmd, timelineCmd, agentCmd, statusCmd];
      }

      return [connItem, newTask, dirHeader, chatCmd, timelineCmd, agentCmd, statusCmd];
    }

    if (element.id === DIR_HEADER_ID) {
      try {
        const list = await this.client.listDirectives();
        const selectedId = this.context.workspaceState.get<string>("trident.selectedDirectiveId");
        return list.items.map((d) => {
          const isActive = d.id === selectedId;
          const it = new vscode.TreeItem(d.title, vscode.TreeItemCollapsibleState.None);
          it.id = `directive-${d.id}`;
          it.description = humanStatus(d.status);
          it.iconPath = new vscode.ThemeIcon(
            isActive ? "arrow-right" : "symbol-interface"
          );
          if (isActive) {
            it.contextValue = "activeDirective";
          }
          it.command = {
            command: "trident.selectDirective",
            title: "Select task",
            arguments: [d.id, d.title],
          };
          return it;
        });
      } catch (e) {
        const err = new vscode.TreeItem("Failed to load tasks", vscode.TreeItemCollapsibleState.None);
        err.id = "trident-directives-error";
        err.description = e instanceof Error ? e.message : String(e);
        err.iconPath = new vscode.ThemeIcon("warning");
        return [err];
      }
    }

    return [];
  }

  getParent(): undefined {
    return undefined;
  }
}

type SidebarNode = vscode.TreeItem;
