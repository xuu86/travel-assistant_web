export const DATABASE_NAME = "xinglv-workspace";
export const DATABASE_VERSION = 1;
export const SNAPSHOT_STORE = "snapshots";
export const METADATA_STORE = "metadata";

let opening: Promise<IDBDatabase> | null = null;

export function openWorkspaceDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("当前浏览器不支持本地行程保存。"));
  }
  if (opening) return opening;

  const promise = new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(SNAPSHOT_STORE)) {
        const snapshots = database.createObjectStore(SNAPSHOT_STORE, {
          keyPath: ["owner_id", "feature_id"],
        });
        snapshots.createIndex("by-owner", "owner_id", { unique: false });
      }
      if (!database.objectStoreNames.contains(METADATA_STORE)) {
        database.createObjectStore(METADATA_STORE, { keyPath: "key" });
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => reject(new Error("无法打开本地行程存储。"));
    request.onblocked = () => reject(new Error("本地行程存储正在升级，请关闭其他应用标签页后重试。"));
  }).catch((error: unknown) => {
    opening = null;
    throw error;
  });
  opening = promise;
  return promise;
}

export function closeWorkspaceDatabase(): void {
  opening?.then((database) => database.close()).catch(() => undefined);
  opening = null;
}

export function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("本地行程存储操作失败。"));
  });
}

export function transactionComplete(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = transaction.onerror = () => reject(new Error("本地行程存储事务失败。"));
  });
}
