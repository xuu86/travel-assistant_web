import { createContext } from "react";

export type SaveState = "loading" | "saved" | "saving" | "error";

export type WorkspaceStore = {
  ready: boolean;
  status: SaveState;
  error: string | null;
  writable: boolean;
  read: <T>(featureId: string) => T | undefined;
  save: (featureId: string, data: unknown) => void;
  clear: () => Promise<void>;
  retry: () => void;
};

const emptyStore: WorkspaceStore = {
  ready: true,
  status: "saved",
  error: null,
  writable: false,
  read: () => undefined,
  save: () => undefined,
  clear: async () => undefined,
  retry: () => undefined,
};

export const WorkspaceStoreContext = createContext<WorkspaceStore>(emptyStore);
