import { describe, expect, it } from "vitest";
import { calculateBudgetDimension, calculatePhysicalDimension, calculateTimeDimension, calculateUnknownDimension, calculateWeatherDimension, combineCheckupDimensions, rankCheckupSuggestions } from "./checkup";
import type { CheckupBudgetInput, CheckupItineraryItem, CheckupWeatherInput, DimensionResult } from "./checkup";

function item(id: string, time: string, stayMinutes: number | null, transitMinutes: number | null): CheckupItineraryItem {
  return {
    id, date: "2026-12-01", time, title: id, locked: false,
    stayMinutes, transitMinutes,
  };
}

function budget(overrides: Partial<CheckupBudgetInput> = {}): CheckupBudgetInput {
  return {
    totalBudgetFen: 1_000_000,
    reserveFen: 100_000,
    costs: [{ paidFen: 200_000, unpaidFen: 400_000, complete: true }],
    ...overrides,
  };
}

function outdoorItem(overrides: Partial<CheckupItineraryItem> = {}): CheckupItineraryItem {
  return {
    id: "walk", date: "2026-12-01", time: "09:00", title: "户外步行", locked: false,
    stayMinutes: 120, transitMinutes: null, environment: "outdoor", walkKm: 5,
    stairSteps: 50, transfers: 4, ...overrides,
  };
}

function weather(overrides: Partial<CheckupWeatherInput> = {}): CheckupWeatherInput {
  return {
    state: "live", verified: true,
    coveredRanges: [{ start: "2026-12-01", end: "2026-12-01" }],
    days: [{ date: "2026-12-01", weatherCode: 0, precipitationPct: 25, temperatureMaxC: 24, temperatureMinC: 12 }],
    ...overrides,
  };
}

describe("itinerary checkup time and budget dimensions", () => {
  it("scores day buffer against the approved 30% scale and uses the tightest day", () => {
    const result = calculateTimeDimension([
      item("museum", "09:00", 60, 30),
      item("lunch", "10:45", 60, null),
    ]);
    expect(result.score).toBe(30);
    expect(result.status).toBe("ready");
    expect(result.details).toEqual(expect.arrayContaining([expect.stringContaining("2026-12-01")]));
  });

  it("requires start time, dwell, and each nonfinal leg duration without guessing", () => {
    expect(calculateTimeDimension([]).score).toBeNull();
    expect(calculateTimeDimension([item("museum", "09:00", null, null)]).missing.join(" ")).toContain("停留分钟");
    expect(calculateTimeDimension([
      item("museum", "09:00", 60, null), item("lunch", "11:00", 60, null),
    ]).score).toBeNull();
  });

  it("keeps zero distinct, reports overlap separately from formula buffer, and sorts dates deterministically", () => {
    const zero = calculateTimeDimension([
      item("zero", "09:00", 60, 0), item("next", "10:00", 60, null),
    ]);
    expect(zero.score).toBe(0);
    const overlap = calculateTimeDimension([
      item("first", "09:00", 90, 0), item("second", "10:00", 60, null),
    ]);
    expect(overlap.score).toBe(0);
    expect(overlap.details.join(" ")).toMatch(/公式缓冲.*时段重叠/);
    const overlapWithLaterGap = calculateTimeDimension([
      item("first", "09:00", 180, 30), item("second", "09:30", 60, 0), item("late", "18:00", 30, null),
    ]);
    expect(overlapWithLaterGap.score).toBe(100);
    expect(overlapWithLaterGap.details.join(" ")).toContain("另有时段重叠");
  });

  it("scores complete budget margin on the approved 30% scale and clamps overspend", () => {
    expect(calculateBudgetDimension(budget()).score).toBe(100);
    expect(calculateBudgetDimension(budget({ reserveFen: 250_000 })).score).toBe(50);
    expect(calculateBudgetDimension(budget({ reserveFen: 500_000 })).score).toBe(0);
  });

  it("does not treat missing totals, zero caps, unknown costs, or empty costs as zero spend", () => {
    expect(calculateBudgetDimension(budget({ totalBudgetFen: null })).score).toBeNull();
    expect(calculateBudgetDimension(budget({ totalBudgetFen: 0 })).score).toBeNull();
    expect(calculateBudgetDimension(budget({ costs: [] })).score).toBeNull();
    expect(calculateBudgetDimension(budget({ costs: [{ paidFen: 0, unpaidFen: null, complete: false }] })).score).toBeNull();
  });

  it("scores physical comfort from the worst workload ratio and requires every input", () => {
    expect(calculatePhysicalDimension([outdoorItem()]).score).toBe(50);
    expect(calculatePhysicalDimension([outdoorItem({ walkKm: 10, stairSteps: 0, transfers: 0, stayMinutes: 0 })]).score).toBe(0);
    expect(calculatePhysicalDimension([outdoorItem({ stairSteps: null })]).score).toBeNull();
    expect(calculatePhysicalDimension([outdoorItem({ environment: "unknown" })]).score).toBeNull();
  });

  it("scores rainfall risk and marks approved extreme weather codes and temperatures", () => {
    expect(calculateWeatherDimension([outdoorItem()], weather()).score).toBe(50);
    for (const code of [95, 96, 99, 66, 67, 75, 86]) {
      expect(calculateWeatherDimension([outdoorItem()], weather({
        days: [{ ...weather().days[0]!, weatherCode: code }],
      })).score).toBe(0);
    }
    expect(calculateWeatherDimension([outdoorItem()], weather({
      days: [{ ...weather().days[0]!, temperatureMaxC: 35.1 }],
    })).score).toBe(0);
    expect(calculateWeatherDimension([outdoorItem()], weather({
      days: [{ ...weather().days[0]!, temperatureMinC: -5.1 }],
    })).score).toBe(0);
  });

  it("requires verified current coverage, date fields, environment, and duration for weather scoring", () => {
    expect(calculateWeatherDimension([outdoorItem()], weather({ verified: false })).score).toBeNull();
    expect(calculateWeatherDimension([outdoorItem()], weather({ coveredRanges: [] })).score).toBeNull();
    expect(calculateWeatherDimension([outdoorItem()], weather({
      days: [{ ...weather().days[0]!, precipitationPct: null }],
    })).score).toBeNull();
    expect(calculateWeatherDimension([outdoorItem({ environment: "unknown" })], weather()).score).toBeNull();
    expect(calculateWeatherDimension([outdoorItem({ stayMinutes: null })], weather()).score).toBeNull();
  });
});

describe("itinerary checkup unknown dimension and suggestions", () => {
  const readyDimensions: DimensionResult[] = ["time", "budget", "physical", "weather", "unknown"].map((id) => ({
    id: id as DimensionResult["id"], label: id, score: 80, status: "ready", coverage: 1,
    missing: [], details: [], sourceKeys: [],
  }));

  it("uses ledger impact only once per unresolved item and requires complete coverage", () => {
    const items = [
      { impact: "high" as const, source_key: "itinerary:a:1" },
      { impact: "medium" as const, source_key: "budget:b:1" },
      { impact: "low" as const, source_key: "budget:c:1" },
    ];
    expect(calculateUnknownDimension(items, "complete").score).toBe(65);
    expect(calculateUnknownDimension(items, "partial").score).toBeNull();
  });

  it("shows a composite only when all five dimensions have scores", () => {
    expect(combineCheckupDimensions(readyDimensions)).toBe(80);
    expect(combineCheckupDimensions(readyDimensions.map((dimension, index) => index === 3 ? { ...dimension, score: null } : dimension))).toBeNull();
    expect(combineCheckupDimensions(readyDimensions.slice(0, 4))).toBeNull();
  });

  it("orders suggestions by impact, date, stable id and limits the result to three", () => {
    const suggestions = ["d", "c", "b", "a"].map((id) => ({
      id, title: id, reason: "依据", date: "2026-12-01", impact: "medium" as const,
      sourceKey: `itinerary:${id}:arrangement`, locked: id === "a",
    }));
    expect(rankCheckupSuggestions(suggestions).map(({ id }) => id)).toEqual(["a", "b", "c"]);
    expect(rankCheckupSuggestions([
      { ...suggestions[0]!, id: "unknown:high", impact: "high" },
      { ...suggestions[0]!, id: "overlap:first", impact: "low" },
    ])[0]?.id).toBe("overlap:first");
  });
});
