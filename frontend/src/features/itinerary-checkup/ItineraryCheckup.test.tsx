import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { components } from "../../shared/api-contracts";
import { WorkspaceStoreContext } from "../local-storage/workspace-context";
import { LedgerContext, modules } from "../unknown-ledger/context";
import type { LedgerContextValue, SourceState } from "../unknown-ledger/context";
import type { LedgerModule } from "../unknown-ledger/model";
import { ItineraryCheckup } from "./ItineraryCheckup";

afterEach(cleanup);

describe("ItineraryCheckup", () => {
  it("scores complete synthetic inputs, links source evidence, and leaves locked itinerary untouched", () => {
    const registerSource = vi.fn();
    const setContactStatus = vi.fn();
    const sources = modules.reduce((value, module) => {
      value[module] = { scan: { module, status: "complete" }, observations: [] };
      return value;
    }, {} as Record<LedgerModule, SourceState>);
    sources.itinerary.observations = [{
      source_key: "itinerary:item-1:arrangement", module: "itinerary", subject: "博物馆", field: "行程安排内容",
      evidence_state: "user_provided", impact: "high", travel_date: "2026-12-01", retrieved_at: null,
    }];
    const ledger: LedgerContextValue = { sources, contacts: {}, registerSource, setContactStatus };
    const read = <T,>(featureId: string): T | undefined => ({
      "budget.total": "1000", "budget.reserve": "0", "budget.costs": [{ paid: "50", unpaid: "50" }],
    } as Record<string, unknown>)[featureId] as T | undefined;
    const workspace = {
      ready: true, status: "saved" as const, error: null, writable: true, read,
      save: vi.fn(), clear: vi.fn(), retry: vi.fn(),
    };
    const weather: components["schemas"]["WeatherResult"] = {
      state: "live", request_id: "checkup-test", message: "", location: {
        city_id: "shanghai", coordinate_system: "WGS84", requested_latitude: 31, requested_longitude: 121,
      },
      coverage: { requested: { start: "2026-12-01", end: "2026-12-01" }, covered: [{ start: "2026-12-01", end: "2026-12-01" }], missing: [] },
      items: [{ date: "2026-12-01", weather_code: 0, precipitation_probability_max_pct: 0, temperature_max_c: 20, temperature_min_c: 10 }],
      sources: [{ source_id: "weather-fixture", display_name: "fixture", url: "https://fixture.invalid", retrieved_at: "2026-11-30T00:00:00Z", evidence_state: "verified" }],
    };
    const onFocusSource = vi.fn();
    const item = {
      id: "item-1", date: "2026-12-01", time: "09:00", title: "博物馆", locked: true,
      stayMinutes: 60, transitMinutes: null, environment: "indoor" as const,
      walkKm: 2, stairSteps: 10, transfers: 1,
    };
    render(<WorkspaceStoreContext.Provider value={workspace}><LedgerContext.Provider value={ledger}>
      <ItineraryCheckup items={[item]} startDate="2026-12-01" weatherState={{ status: "success", data: weather }} onFocusSource={onFocusSource} />
    </LedgerContext.Provider></WorkspaceStoreContext.Provider>);

    expect(screen.getByText("综合分：72 / 100")).toBeVisible();
    expect(screen.getByText("时间宽松度").parentElement).toHaveTextContent("0 分");
    expect(screen.getByText("预算余量").parentElement).toHaveTextContent("100 分");
    expect(screen.getByText("待核实项").parentElement).toHaveTextContent("80 分");
    const sourceButton = screen.getByRole("button", { name: "查看来源" });
    fireEvent.click(sourceButton);
    expect(onFocusSource).toHaveBeenCalledWith("itinerary:item-1:arrangement");
    expect(screen.getByText(/关联安排已锁定/)).toBeVisible();
    expect(screen.getByText("博物馆：行程安排内容待核实")).toBeVisible();
  });

  it("refuses to score non-verified or demo weather", () => {
    const data: components["schemas"]["WeatherResult"] = {
      state: "demo", request_id: "demo", message: "", location: {
        city_id: "shanghai", coordinate_system: "WGS84", requested_latitude: 31, requested_longitude: 121,
      }, items: [], sources: [],
    };
    const result = render(<WorkspaceStoreContext.Provider value={{
      ready: true, status: "saved", error: null, writable: false, read: () => undefined,
      save: () => undefined, clear: async () => undefined, retry: () => undefined,
    }}><LedgerContext.Provider value={{
      sources: modules.reduce((sources, module) => {
        sources[module] = { scan: { module, status: "complete" }, observations: [] };
        return sources;
      }, {} as Record<LedgerModule, SourceState>), contacts: {}, registerSource: () => undefined, setContactStatus: () => undefined,
    }}><ItineraryCheckup items={[{
      id: "a", date: "2026-12-01", time: "09:00", title: "户外", locked: false,
      stayMinutes: 30, transitMinutes: null, environment: "outdoor", walkKm: 1, stairSteps: 0, transfers: 0,
    }]} startDate="2026-12-01" weatherState={{ status: "success", data }} onFocusSource={() => undefined} /></LedgerContext.Provider></WorkspaceStoreContext.Provider>);
    expect(screen.getAllByText("数据不足").length).toBeGreaterThan(0);
    result.unmount();
  });
});
