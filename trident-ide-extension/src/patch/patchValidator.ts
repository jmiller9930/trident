/** Minimal unified-diff shape check (100M §6). */

export function looksLikeUnifiedDiff(s: string): boolean {
  return /^---\s+/m.test(s) && /^\+\+\+\s+/m.test(s);
}
