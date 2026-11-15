import type { WorkspaceSnapshotRecord } from "./types";

export const WORKSPACE_SCHEMA_VERSION = 1;
const MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024;
const PRIVATE_FIELD_NAME = /(password|token|session|secret|api.?key)/i;

export class SnapshotError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SnapshotError";
  }
}

function assertJsonValue(value: unknown, depth = 0): void {
  if (depth > 24) throw new SnapshotError("本地快照层级超出限制。");
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (Number.isFinite(value)) return;
    throw new SnapshotError("本地快照包含无效数字。");
  }
  if (Array.isArray(value)) {
    for (const item of value) assertJsonValue(item, depth + 1);
    return;
  }
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new SnapshotError("本地快照只支持普通数据对象。");
    }
    for (const [key, item] of Object.entries(value)) {
      if (PRIVATE_FIELD_NAME.test(key)) throw new SnapshotError("本地快照不能包含认证或密钥字段。");
      assertJsonValue(item, depth + 1);
    }
    return;
  }
  throw new SnapshotError("本地快照包含不支持的数据类型。");
}

export function encodeWorkspaceSnapshot<T>(value: T): T {
  assertJsonValue(value);
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    throw new SnapshotError("本地快照无法序列化。");
  }
  if (new TextEncoder().encode(serialized).byteLength > MAX_SNAPSHOT_BYTES) {
    throw new SnapshotError("本地快照超过 2 MB 上限。");
  }
  return value;
}

export function decodeWorkspaceSnapshot(record: WorkspaceSnapshotRecord): unknown {
  if (record.schema_version !== WORKSPACE_SCHEMA_VERSION) {
    throw new SnapshotError("本地数据版本较新，当前版本只读，原有内容不会被覆盖。");
  }
  return encodeWorkspaceSnapshot(record.data);
}
