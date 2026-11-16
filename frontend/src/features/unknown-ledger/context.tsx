import { createContext, useContext, useEffect } from "react";
import {
  buildLedgerView,
  type ContactStatus,
  type LedgerModule,
  type LedgerObservation,
  type LedgerSourceScan,
} from "./model";

export type SourceState = { scan: LedgerSourceScan; observations: LedgerObservation[] };
export type ContactStatuses = Record<string, ContactStatus>;
export type LedgerContextValue = {
  sources: Record<LedgerModule, SourceState>;
  contacts: ContactStatuses;
  registerSource: (module: LedgerModule, scan: LedgerSourceScan, observations: LedgerObservation[]) => void;
  setContactStatus: (sourceKey: string, status: ContactStatus) => void;
};

export const modules: LedgerModule[] = [
  "weather", "transport", "hotels", "activities", "attractions", "budget", "itinerary",
];
export const LedgerContext = createContext<LedgerContextValue | null>(null);

export function useLedgerSource(
  module: LedgerModule,
  scan: LedgerSourceScan,
  observations: LedgerObservation[],
): void {
  const ledger = useContext(LedgerContext);
  const registerSource = ledger?.registerSource;
  const sourceSnapshot = JSON.stringify([scan, observations]);

  useEffect(() => {
    if (!registerSource) return;
    const [nextScan, nextObservations] = JSON.parse(sourceSnapshot) as [LedgerSourceScan, LedgerObservation[]];
    registerSource(module, nextScan, nextObservations);
    return () => registerSource(module, { module, status: "not_loaded" }, []);
  }, [module, registerSource, sourceSnapshot]);
}

function beijingToday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function useUnknownLedger(departureDate: string, today = beijingToday()) {
  const ledger = useContext(LedgerContext);
  if (!ledger) return {
    view: buildLedgerView([], [], departureDate, today),
    setContactStatus: () => undefined,
  };
  const observations = modules.flatMap((module) => ledger.sources[module].observations);
  const scans = modules.map((module) => ledger.sources[module].scan);
  return {
    view: buildLedgerView(observations, scans, departureDate, today, ledger.contacts),
    setContactStatus: ledger.setContactStatus,
  };
}
