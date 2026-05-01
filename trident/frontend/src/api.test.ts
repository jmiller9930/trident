import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiBase, normalizeBasePath } from "./api";

function stubWindow(locOrigin: string, bp: string, pub: string) {
  vi.stubGlobal("window", {
    location: { origin: locOrigin },
    __TRIDENT_BASE_PATH__: bp,
    __TRIDENT_PUBLIC_BASE_URL__: pub,
  } as Window & typeof globalThis);
}

describe("getApiBase", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses origin + base path + /api when public URL empty", () => {
    stubWindow("http://localhost:3000", "/trident", "");
    expect(getApiBase()).toBe("http://localhost:3000/trident/api");
  });

  it("ignores public URL when origin differs (mixed port / scheme)", () => {
    stubWindow("http://clawbot.a51.corp:3000", "/trident", "https://clawbot.a51.corp/trident");
    expect(getApiBase()).toBe("http://clawbot.a51.corp:3000/trident/api");
  });

  it("uses public URL + /api when origin matches page", () => {
    stubWindow("http://localhost:3000", "/trident", "http://localhost:3000/trident");
    expect(getApiBase()).toBe("http://localhost:3000/trident/api");
  });

  it("uses /api only when base path empty and public empty", () => {
    stubWindow("http://localhost:3000", "", "");
    expect(getApiBase()).toBe("http://localhost:3000/api");
  });
});

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
