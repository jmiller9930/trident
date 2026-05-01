import * as vscode from "vscode";
import { withPatchApplyScope } from "./patchApplyScope";

/** Persists governed content so server disk verification matches (100M apply-complete). */
export async function writeGovernedFileUtf8(uri: vscode.Uri, text: string): Promise<void> {
  await withPatchApplyScope(async () => {
    await vscode.workspace.fs.writeFile(uri, new TextEncoder().encode(text));
    await vscode.workspace.openTextDocument(uri);
  });
}
