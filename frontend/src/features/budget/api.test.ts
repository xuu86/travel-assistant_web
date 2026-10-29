import { describe, expect, it, vi } from "vitest";
import { calculateBudget, BudgetApiError } from "./api";

const snapshot = {
  trip_id: "trip-1",
  total_budget_fen: 100_000,
  reserve_fen: null,
  cost_items: [],
};

describe("calculateBudget", () => {
  it("rejects malformed success payloads", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ budget_state: "within_budget" }), { status: 200 }),
    );

    const error = await calculateBudget(snapshot, fetchMock).catch((value: unknown) => value);

    expect(error).toBeInstanceOf(BudgetApiError);
    expect(error).toMatchObject({ requestId: null });
  });
});
