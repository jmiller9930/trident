/** Serialize governed edits that must bypass patch-only revert (100M). */

let depth = 0;

export function isPatchApplyInProgress(): boolean {
  return depth > 0;
}

export async function withPatchApplyScope<T>(fn: () => Thenable<T>): Promise<T> {
  depth += 1;
  try {
    return await fn();
  } finally {
    depth -= 1;
  }
}
