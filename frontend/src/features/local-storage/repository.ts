import {
  METADATA_STORE,
  openWorkspaceDatabase,
  requestResult,
  SNAPSHOT_STORE,
  transactionComplete,
} from "./database";
import { encodeWorkspaceSnapshot } from "./snapshot";
import type { GuestOwnerRecord, WorkspaceSnapshotRecord } from "./types";

function randomOwnerId(): string {
  if (typeof crypto.randomUUID === "function") return `guest-${crypto.randomUUID()}`;
  const values = crypto.getRandomValues(new Uint8Array(16));
  return `guest-${Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("")}`;
}

export async function getGuestOwnerId(): Promise<string> {
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(METADATA_STORE, "readwrite");
  const store = transaction.objectStore(METADATA_STORE);
  const existing = await requestResult(store.get("guest-owner-id")) as GuestOwnerRecord | undefined;
  if (existing?.value) {
    await transactionComplete(transaction);
    return existing.value;
  }
  const record: GuestOwnerRecord = { key: "guest-owner-id", value: randomOwnerId() };
  await requestResult(store.put(record));
  await transactionComplete(transaction);
  return record.value;
}

export async function listWorkspaceSnapshots(ownerId: string): Promise<WorkspaceSnapshotRecord[]> {
  if (!ownerId) throw new Error("本地行程身份无效。");
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(SNAPSHOT_STORE, "readonly");
  const records = await requestResult(
    transaction.objectStore(SNAPSHOT_STORE).index("by-owner").getAll(ownerId),
  ) as WorkspaceSnapshotRecord[];
  await transactionComplete(transaction);
  return records;
}

export async function getWorkspaceSnapshot(
  ownerId: string,
  featureId: string,
): Promise<WorkspaceSnapshotRecord | undefined> {
  if (!ownerId || !featureId) throw new Error("本地行程身份或分区无效。");
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(SNAPSHOT_STORE, "readonly");
  const record = await requestResult(
    transaction.objectStore(SNAPSHOT_STORE).get([ownerId, featureId]),
  ) as WorkspaceSnapshotRecord | undefined;
  await transactionComplete(transaction);
  return record;
}

export async function saveWorkspaceSnapshot(
  ownerId: string,
  featureId: string,
  schemaVersion: number,
  data: unknown,
): Promise<void> {
  if (!ownerId || !featureId || !Number.isInteger(schemaVersion) || schemaVersion < 1) {
    throw new Error("本地行程快照标识无效。");
  }
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(SNAPSHOT_STORE, "readwrite");
  const record: WorkspaceSnapshotRecord = {
    owner_id: ownerId,
    feature_id: featureId,
    schema_version: schemaVersion,
    updated_at: new Date().toISOString(),
    data: encodeWorkspaceSnapshot(data),
  };
  await requestResult(transaction.objectStore(SNAPSHOT_STORE).put(record));
  await transactionComplete(transaction);
}

export async function deleteWorkspaceSnapshot(ownerId: string, featureId: string): Promise<void> {
  if (!ownerId || !featureId) throw new Error("本地行程身份或分区无效。");
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(SNAPSHOT_STORE, "readwrite");
  await requestResult(transaction.objectStore(SNAPSHOT_STORE).delete([ownerId, featureId]));
  await transactionComplete(transaction);
}

export async function deleteAllWorkspaceSnapshots(ownerId: string): Promise<void> {
  if (!ownerId) throw new Error("本地行程身份无效。");
  const database = await openWorkspaceDatabase();
  const transaction = database.transaction(SNAPSHOT_STORE, "readwrite");
  const store = transaction.objectStore(SNAPSHOT_STORE);
  const keys = await requestResult(store.index("by-owner").getAllKeys(ownerId));
  for (const key of keys) store.delete(key);
  await transactionComplete(transaction);
}
