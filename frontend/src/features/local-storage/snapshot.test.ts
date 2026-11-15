import { describe, expect, it } from "vitest";
import { decodeWorkspaceSnapshot, encodeWorkspaceSnapshot, SnapshotError } from "./snapshot";

describe("workspace snapshots", () => {
  it("accepts plain JSON values and preserves unknown and empty values", () => {
    expect(encodeWorkspaceSnapshot({ items: [], amount: null, checked: false })).toEqual({
      items: [], amount: null, checked: false,
    });
    expect(encodeWorkspaceSnapshot("")).toBe("");
  });

  it("rejects credentials, non-finite values, and runtime objects", () => {
    expect(() => encodeWorkspaceSnapshot({ access_token: "never-store" })).toThrow(SnapshotError);
    expect(() => encodeWorkspaceSnapshot({ password: "secret" })).toThrow(SnapshotError);
    expect(() => encodeWorkspaceSnapshot({ count: Number.NaN })).toThrow(SnapshotError);
    expect(() => encodeWorkspaceSnapshot(new Date())).toThrow(SnapshotError);
  });

  it("rejects oversized or unsupported schema records without coercion", () => {
    expect(() => encodeWorkspaceSnapshot({ text: "x".repeat(2 * 1024 * 1024) })).toThrow(/2 MB/);
    expect(() => decodeWorkspaceSnapshot({
      owner_id: "owner", feature_id: "workspace", schema_version: 99,
      updated_at: "2026-01-01T00:00:00.000Z", data: { preserved: true },
    })).toThrow(/只读/);
  });
});
