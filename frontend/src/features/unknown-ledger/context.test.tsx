import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WorkspaceStoreContext, type WorkspaceStore } from "../local-storage/workspace-context";
import {
  useLedgerSource,
  useUnknownLedger,
} from "./context";
import { UnknownLedgerProvider } from "./UnknownLedgerProvider";
import type { LedgerObservation, LedgerSourceScan } from "./model";

const emptyScan: LedgerSourceScan = { module: "weather", status: "complete" };
const observation: LedgerObservation = {
  source_key: "weather:forecast:rain",
  module: "weather",
  subject: "天气预报",
  field: "降水概率",
  evidence_state: "estimate",
  impact: "medium",
  travel_date: "2026-12-01",
  retrieved_at: "2026-11-20T00:00:00Z",
};

afterEach(cleanup);

function makeStore(snapshots: Record<string, unknown> = {}): WorkspaceStore {
  return {
    ready: true,
    status: "saved",
    error: null,
    writable: true,
    read: <T,>(featureId: string) => snapshots[featureId] as T | undefined,
    save: () => undefined,
    clear: async () => undefined,
    retry: () => undefined,
  };
}

function LedgerHarness({ source }: { source: { scan: LedgerSourceScan; observations: LedgerObservation[] } }) {
  useLedgerSource("weather", source.scan, source.observations);
  const ledger = useUnknownLedger("2026-12-01", "2026-11-20");
  return <>
    <output data-testid="coverage">{ledger.view.coverage}</output>
    <output data-testid="keys">{ledger.view.items.map((item) => item.source_key).join(",")}</output>
    <output data-testid="contact">{ledger.view.items[0]?.contact_status ?? "none"}</output>
    {ledger.view.items[0] && <button onClick={() => ledger.setContactStatus(ledger.view.items[0].source_key, "contacted")}>已联系</button>}
  </>;
}

function InlineSourceHarness() {
  useLedgerSource("weather", { module: "weather", status: "complete" }, [{ ...observation }]);
  const ledger = useUnknownLedger("2026-12-01", "2026-11-20");
  return <>
    <output data-testid="inline-coverage">{ledger.view.coverage}</output>
    <output data-testid="inline-keys">{ledger.view.items.map((item) => item.source_key).join(",")}</output>
  </>;
}

function renderLedger(source: { scan: LedgerSourceScan; observations: LedgerObservation[] }, snapshots: Record<string, unknown> = {}) {
  return render(
    <WorkspaceStoreContext.Provider value={makeStore(snapshots)}>
      <UnknownLedgerProvider><LedgerHarness source={source} /></UnknownLedgerProvider>
    </WorkspaceStoreContext.Provider>,
  );
}

describe("unknown ledger context", () => {
  it("keeps inline source values stable across provider renders", async () => {
    render(
      <WorkspaceStoreContext.Provider value={makeStore()}>
        <UnknownLedgerProvider><InlineSourceHarness /></UnknownLedgerProvider>
      </WorkspaceStoreContext.Provider>,
    );
    expect((await screen.findByTestId("inline-coverage")).textContent).toBe("partial");
    expect(screen.getByTestId("inline-keys").textContent).toBe(observation.source_key);
  });

  it("replaces source observations when a source updates and removes stale candidates", async () => {
    const { rerender } = renderLedger({ scan: emptyScan, observations: [observation] });
    expect((await screen.findByTestId("keys")).textContent).toBe(observation.source_key);

    rerender(
      <WorkspaceStoreContext.Provider value={makeStore()}>
        <UnknownLedgerProvider><LedgerHarness source={{ scan: emptyScan, observations: [] }} /></UnknownLedgerProvider>
      </WorkspaceStoreContext.Provider>,
    );
    expect((await screen.findByTestId("keys")).textContent).toBe("");
    expect(screen.getByTestId("coverage").textContent).toBe("partial");
  });

  it("keeps contacted candidates visible and persists workflow status by owner snapshot", async () => {
    const snapshots: Record<string, unknown> = {};
    const store = makeStore();
    store.save = (featureId, data) => { snapshots[featureId] = data; };
    render(
      <WorkspaceStoreContext.Provider value={store}>
        <UnknownLedgerProvider><LedgerHarness source={{ scan: emptyScan, observations: [observation] }} /></UnknownLedgerProvider>
      </WorkspaceStoreContext.Provider>,
    );
    await screen.findByTestId("keys");
    fireEvent.click(screen.getByRole("button", { name: "已联系" }));
    expect((await screen.findByTestId("contact")).textContent).toBe("contacted");
    expect(screen.getByTestId("keys").textContent).toBe(observation.source_key);
    await act(async () => {});
    expect(snapshots["unknown-ledger.contact-statuses"]).toEqual({ [observation.source_key]: "contacted" });
  });

  it("distinguishes unmounted/not-loaded and unavailable sources from complete scans", async () => {
    const { rerender } = renderLedger({ scan: { module: "weather", status: "not_loaded" }, observations: [] });
    expect((await screen.findByTestId("coverage")).textContent).toBe("not_loaded");

    rerender(
      <WorkspaceStoreContext.Provider value={makeStore()}>
        <UnknownLedgerProvider><LedgerHarness source={{ scan: { module: "weather", status: "unavailable" }, observations: [] }} /></UnknownLedgerProvider>
      </WorkspaceStoreContext.Provider>,
    );
    expect((await screen.findByTestId("coverage")).textContent).toBe("partial");
  });
});
