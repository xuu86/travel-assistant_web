import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { usePersistentState } from "../local-storage/useWorkspacePersistence";
import { LedgerContext, modules } from "./context";
import type { ContactStatuses, LedgerContextValue, SourceState } from "./context";
import type { LedgerModule, LedgerObservation, LedgerSourceScan } from "./model";

const defaultSources = modules.reduce((sources, module) => {
  sources[module] = { scan: { module, status: "not_loaded" }, observations: [] };
  return sources;
}, {} as Record<LedgerModule, SourceState>);

export function UnknownLedgerProvider({ children }: { children: ReactNode }) {
  const [sources, setSources] = useState(defaultSources);
  const [contacts, setContacts] = usePersistentState<ContactStatuses>("unknown-ledger.contact-statuses", {});

  const registerSource = useCallback((module: LedgerModule, scan: LedgerSourceScan, observations: LedgerObservation[]) => {
    setSources((current) => ({ ...current, [module]: { scan, observations } }));
  }, []);

  const setContactStatus = useCallback((sourceKey: string, status: "not_contacted" | "contacted") => {
    setContacts((current) => {
      if (status === "not_contacted") {
        const next = { ...current };
        delete next[sourceKey];
        return next;
      }
      return { ...current, [sourceKey]: status };
    });
  }, [setContacts]);

  const value = useMemo<LedgerContextValue>(() => ({ sources, contacts, registerSource, setContactStatus }), [
    sources, contacts, registerSource, setContactStatus,
  ]);

  return <LedgerContext.Provider value={value}>{children}</LedgerContext.Provider>;
}
