import { useContext, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { WorkspaceStoreContext, type WorkspaceStore } from "./workspace-context";

export function usePersistentState<T>(
  featureId: string,
  initialState: T | (() => T),
): [T, Dispatch<SetStateAction<T>>] {
  const store = useContext(WorkspaceStoreContext);
  const { read, save } = store;
  const [state, setState] = useState<T>(() => {
    const saved = read<T>(featureId);
    return saved !== undefined
      ? saved
      : typeof initialState === "function"
        ? (initialState as () => T)()
        : initialState;
  });

  useEffect(() => {
    save(featureId, state);
  }, [featureId, state, save]);

  return [state, setState];
}

export function useWorkspacePersistence(): Pick<WorkspaceStore, "status" | "error" | "retry" | "clear"> {
  const { status, error, retry, clear } = useContext(WorkspaceStoreContext);
  return { status, error, retry, clear };
}

export function useWorkspaceReady(): boolean {
  return useContext(WorkspaceStoreContext).ready;
}
