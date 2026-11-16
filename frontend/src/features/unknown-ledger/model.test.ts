import { describe, expect, it } from "vitest";
import {
  buildLedgerView,
  type LedgerObservation,
  type LedgerSourceScan,
} from "./model";

const observations: LedgerObservation[] = [
  {
    source_key: "budget:cost-1:unpaid",
    module: "budget",
    subject: "车票订单",
    field: "待支付金额",
    evidence_state: "unknown",
    impact: "low",
    travel_date: "2026-12-01",
    retrieved_at: null,
  },
  {
    source_key: "places:booking:reservation",
    module: "attractions",
    subject: "博物馆",
    field: "预约要求",
    evidence_state: "unverified",
    impact: "high",
    travel_date: "2026-12-01",
    retrieved_at: "2026-11-01T00:00:00Z",
  },
  {
    source_key: "weather:trip:coverage",
    module: "weather",
    subject: "天气预报",
    field: "日期覆盖",
    evidence_state: "estimate",
    impact: "medium",
    travel_date: "2026-12-01",
    retrieved_at: null,
  },
];

const completeScans: LedgerSourceScan[] = [
  { module: "budget", status: "complete" },
  { module: "attractions", status: "complete" },
  { module: "weather", status: "complete" },
];

describe("unknown ledger model", () => {
  it("uses the approved T-7, T-3, T-0 Beijing calendar checkpoints", () => {
    const view = buildLedgerView(observations, completeScans, "2026-12-01", "2026-11-24");
    expect(view.items.map((item) => [item.source_key, item.reminder_date, item.reminder_status])).toEqual([
      ["places:booking:reservation", "2026-11-24", "due"],
      ["weather:trip:coverage", "2026-11-28", "upcoming"],
      ["budget:cost-1:unpaid", "2026-12-01", "upcoming"],
    ]);
  });

  it("keeps null distinct from zero and leaves contacted facts unresolved", () => {
    const view = buildLedgerView(observations, completeScans, "2026-12-01", "2026-11-20", {
      "budget:cost-1:unpaid": "contacted",
    });
    const cost = view.items.find((item) => item.source_key === "budget:cost-1:unpaid");
    expect(cost?.evidence_state).toBe("unknown");
    expect(cost?.contact_status).toBe("contacted");
    expect(cost?.reminder_date).toBe("2026-12-01");
  });

  it("excludes verified and demo observations while reporting complete empty scans", () => {
    const view = buildLedgerView([
      { ...observations[0], evidence_state: "verified" },
      { ...observations[1], evidence_state: "demo" },
    ], [
      { module: "budget", status: "complete" },
      { module: "attractions", status: "complete" },
    ], "2026-12-01", "2026-11-20");
    expect(view.items).toEqual([]);
    expect(view.coverage).toBe("complete");
    expect(view.emptyState).toBe("empty");
  });

  it("does not claim an empty ledger when scans are missing or unavailable", () => {
    const notLoaded = buildLedgerView([], [{ module: "weather", status: "not_loaded" }], "2026-12-01", "2026-11-20");
    const unavailable = buildLedgerView([], [{ module: "weather", status: "unavailable" }], "2026-12-01", "2026-11-20");
    expect(notLoaded.coverage).toBe("not_loaded");
    expect(notLoaded.emptyState).toBe("scan_required");
    expect(unavailable.coverage).toBe("unavailable");
    expect(unavailable.emptyState).toBe("scan_required");
  });

  it("orders candidates deterministically by trip date, checkpoint, impact and key", () => {
    const view = buildLedgerView(observations, completeScans, "2026-12-01", "2026-11-20");
    expect(view.items.map((item) => item.source_key)).toEqual([
      "places:booking:reservation",
      "weather:trip:coverage",
      "budget:cost-1:unpaid",
    ]);
  });

  it("validates stable source keys and rejects duplicate observations", () => {
    expect(() => buildLedgerView([
      observations[0], { ...observations[0], subject: "duplicate" },
    ], completeScans, "2026-12-01", "2026-11-20")).toThrow(/重复/);
    expect(() => buildLedgerView([
      { ...observations[0], source_key: "../secret" },
    ], completeScans, "2026-12-01", "2026-11-20")).toThrow(/source_key/);
  });

  it("rejects invalid dates instead of applying device-local date arithmetic", () => {
    expect(() => buildLedgerView(observations, completeScans, "2026-02-30", "2026-02-20"))
      .toThrow(/日期/);
  });
});
