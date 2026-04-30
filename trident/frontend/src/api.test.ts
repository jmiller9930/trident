import { describe, expect, it } from "vitest";
import { normalizeBasePath } from "./api";

describe("normalizeBasePath", () => {
  it("returns empty for blank", () => {
    expect(normalizeBasePath("")).toBe("");
    expect(normalizeBasePath(undefined)).toBe("");
  });
  it("normalizes slashes", () => {
    expect(normalizeBasePath("/trident/")).toBe("/trident");
    expect(normalizeBasePath("trident")).toBe("/trident");
  });
});
