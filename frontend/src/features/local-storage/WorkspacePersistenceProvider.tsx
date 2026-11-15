import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { deleteAllWorkspaceSnapshots, listWorkspaceSnapshots, saveWorkspaceSnapshot } from "./repository";
import { WorkspaceStoreContext } from "./workspace-context";
import type { SaveState, WorkspaceStore } from "./workspace-context";
import { decodeWorkspaceSnapshot } from "./snapshot";

function publicStorageError(reason: unknown): string {
  if (reason instanceof DOMException && reason.name === "QuotaExceededError") {
    return "本地空间不足，当前操作仍保留在页面中。请释放空间后重试。";
  }
  return reason instanceof Error ? reason.message : "本地保存失败，当前操作仍保留在页面中。";
}
export function WorkspacePersistenceProvider({ ownerId, children, beforeSwitchRef }: {
  ownerId: string;
  children: ReactNode;
  beforeSwitchRef?: RefObject<(() => Promise<void>) | null>;
}) {
  const [ready, setReady] = useState(false);
  const [snapshots, setSnapshots] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState<SaveState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [writable, setWritable] = useState(true);
  const pending = useRef(new Map<string, unknown>());
  const queues = useRef(new Map<string, Promise<void>>());
  const alive = useRef(true);
  const clearing = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    alive.current = true;
    let active = true;
    void listWorkspaceSnapshots(ownerId).then((records) => {
      if (!active) return;
      const values: Record<string, unknown> = {};
      let supported = true;
      for (const record of records) {
        try {
          values[record.feature_id] = decodeWorkspaceSnapshot(record);
        } catch (reason) {
          supported = false;
          setError(reason instanceof Error ? reason.message : "本地数据不可读取，原内容不会被覆盖。");
        }
      }
      setSnapshots(values);
      setWritable(supported);
      if (supported) setError(null);
      setStatus(supported ? "saved" : "error");
      setReady(true);
    }).catch((reason: unknown) => {
      if (!active) return;
      setError(publicStorageError(reason));
      setWritable(false);
      setStatus("error");
      setReady(true);
    });
    return () => {
      active = false;
      alive.current = false;
    };
  }, [ownerId]);

  const enqueue = useCallback((featureId: string) => {
    const previous = queues.current.get(featureId) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(async () => {
      const latest = pending.current.get(featureId);
      if (latest === undefined) return;
      await saveWorkspaceSnapshot(ownerId, featureId, 1, latest);
      if (pending.current.get(featureId) === latest) pending.current.delete(featureId);
    }).then(() => {
      if (alive.current && pending.current.size === 0) setStatus("saved");
    }).catch((reason: unknown) => {
      if (!alive.current) return;
      setError(publicStorageError(reason));
      setStatus("error");
    });
    queues.current.set(featureId, next);
    return next;
  }, [ownerId]);

  const flush = useCallback(async () => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    await Promise.all([...pending.current.keys()].map(enqueue));
    if (pending.current.size > 0) throw new Error("操作尚未保存，请重试本地保存后再切换账号。");
  }, [enqueue]);

  useEffect(() => {
    if (beforeSwitchRef) beforeSwitchRef.current = flush;
    const saveBeforeLeaving = () => { void flush().catch(() => undefined); };
    window.addEventListener("pagehide", saveBeforeLeaving);
    const saveWhenHidden = () => { if (document.visibilityState === "hidden") saveBeforeLeaving(); };
    document.addEventListener("visibilitychange", saveWhenHidden);
    return () => {
      if (beforeSwitchRef?.current === flush) beforeSwitchRef.current = null;
      window.removeEventListener("pagehide", saveBeforeLeaving);
      document.removeEventListener("visibilitychange", saveWhenHidden);
      saveBeforeLeaving();
    };
  }, [flush, beforeSwitchRef]);

  const persist = useCallback((featureId: string, data: unknown) => {
    if (!writable || clearing.current) return;
    pending.current.set(featureId, data);
    setSnapshots((current) => ({ ...current, [featureId]: data }));
    setError(null);
    setStatus("saving");
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush().catch(() => undefined); }, 200);
  }, [writable, flush]);

  const clear = useCallback(async () => {
    if (!writable) throw new Error("本地数据当前只读，无法重置。");
    clearing.current = true;
    try {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
      await Promise.all([...queues.current.values()].map((queue) => queue.catch(() => undefined)));
      await deleteAllWorkspaceSnapshots(ownerId);
      pending.current.clear();
      setSnapshots({});
      setError(null);
      setStatus("saved");
    } catch (reason) {
      setError(publicStorageError(reason));
      setStatus("error");
      throw reason;
    } finally {
      clearing.current = false;
    }
  }, [ownerId, writable]);

  const retry = useCallback(() => {
    if (pending.current.size > 0) {
      setError(null);
      setStatus("saving");
      void flush().catch(() => undefined);
      return;
    }
    setReady(false);
    void listWorkspaceSnapshots(ownerId).then((records) => {
      const values: Record<string, unknown> = {};
      let supported = true;
      for (const record of records) {
        try {
          values[record.feature_id] = decodeWorkspaceSnapshot(record);
        } catch (reason) {
          supported = false;
          setError(reason instanceof Error ? reason.message : "本地数据不可读取，原内容不会被覆盖。");
        }
      }
      setSnapshots(values);
      setWritable(supported);
      if (supported) setError(null);
      setStatus(supported ? "saved" : "error");
      setReady(true);
    }).catch((reason: unknown) => {
      setWritable(false);
      setError(publicStorageError(reason));
      setStatus("error");
      setReady(true);
    });
  }, [ownerId, flush]);

  const store = useMemo<WorkspaceStore>(() => ({
    ready,
    status,
    error,
    writable,
    read: <T,>(featureId: string) => snapshots[featureId] as T | undefined,
    save: persist,
    retry,
    clear,
  }), [ready, status, error, snapshots, writable, persist, retry, clear]);

  if (!ready) {
    return <main className="auth-startup" aria-live="polite"><span className="auth-startup__mark" aria-hidden="true" />正在恢复本地操作…</main>;
  }
  return <WorkspaceStoreContext.Provider value={store}>{children}</WorkspaceStoreContext.Provider>;
}
