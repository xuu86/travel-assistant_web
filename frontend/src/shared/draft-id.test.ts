import { afterEach, describe, expect, it, vi } from "vitest";
import { createDraftId } from "./draft-id";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("createDraftId", () => {
  it("uses native UUID generation when available", () => {
    const uuid = "12345678-1234-4234-8234-123456789abc";
    const native = vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(uuid);
    expect(createDraftId()).toBe(uuid);
    expect(native).toHaveBeenCalledOnce();
  });

  it("generates distinct v4 UUIDs on HTTP origins without randomUUID", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto),
    });
    const ids = Array.from({ length: 100 }, createDraftId);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    }
  });
});
