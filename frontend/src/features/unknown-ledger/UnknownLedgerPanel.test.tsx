import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceStoreContext, type WorkspaceStore } from "../local-storage/workspace-context";
import { useLedgerSource } from "./context";
import { UnknownLedgerProvider } from "./UnknownLedgerProvider";
import { UnknownLedgerPanel } from "./UnknownLedgerPanel";
import type { LedgerObservation } from "./model";

const observation: LedgerObservation = {
  source_key: "weather:forecast:2026-12-01:precipitation_probability_max_pct",
  module: "weather",
  subject: "2026-12-01 天气预报",
  field: "降水概率",
  evidence_state: "unknown",
  impact: "medium",
  travel_date: "2026-12-01",
  retrieved_at: null,
};

function makeStore(): WorkspaceStore {
  return {
    ready: true, status: "saved", error: null, writable: true,
    read: () => undefined, save: () => undefined, clear: async () => undefined, retry: () => undefined,
  };
}

function WeatherSource() {
  useLedgerSource("weather", { module: "weather", status: "complete" }, [observation]);
  return null;
}

function renderPanel(onOpenSource = vi.fn()) {
  render(
    <WorkspaceStoreContext.Provider value={makeStore()}>
      <UnknownLedgerProvider>
        <WeatherSource />
        <UnknownLedgerPanel departureDate="2026-12-01" onOpenSource={onOpenSource} />
      </UnknownLedgerProvider>
    </WorkspaceStoreContext.Provider>,
  );
  return onOpenSource;
}

afterEach(cleanup);

describe("UnknownLedgerPanel", () => {
  it("shows candidate status and routes back to its source module", async () => {
    const onOpenSource = renderPanel();
    expect(await screen.findByText("降水概率")).toBeTruthy();
    expect(screen.getByText("中影响")).toBeTruthy();
    expect(screen.getByRole("listitem").querySelector(".unknown-ledger__meta")?.textContent).toContain("2026-11-28");
    fireEvent.click(screen.getByRole("button", { name: "前往复核" }));
    expect(onOpenSource).toHaveBeenCalledWith("weather", observation.source_key);
  });

  it("keeps contacted items open and labels their evidence unchanged", async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "标记已联系" }));
    expect(await screen.findByText("已联系，仍待核实")).toBeTruthy();
    expect(screen.getByRole("button", { name: "撤销已联系" })).toBeTruthy();
    expect(screen.getByText(/状态未知/)).toBeTruthy();
  });

  it("does not claim the ledger is empty while source coverage is incomplete", async () => {
    render(
      <WorkspaceStoreContext.Provider value={makeStore()}>
        <UnknownLedgerProvider>
          <UnknownLedgerPanel departureDate="2026-12-01" onOpenSource={() => undefined} />
        </UnknownLedgerProvider>
      </WorkspaceStoreContext.Provider>,
    );
    expect(await screen.findByText(/来源尚未全部就绪/)).toBeTruthy();
    expect(screen.queryByText("当前已扫描来源没有待核实项。")).toBeNull();
  });
});
