import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BudgetPanel } from "./BudgetPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function successResponse(overrides: Record<string, unknown> = {}) {
  return new Response(JSON.stringify({
    trip_id: "current-trip",
    total_budget_fen: 600000,
    paid_total_fen: 200000,
    known_unpaid_total_fen: 300000,
    remaining_to_allocate_fen: 400000,
    expected_balance_fen: 40000,
    minimum_over_budget_fen: null,
    budget_state: "within_budget",
    completeness: "complete",
    reserve_fen: 60000,
    reserve_reminder: false,
    request_id: "budget-request",
    ...overrides,
  }), { status: 200, headers: { "content-type": "application/json" } });
}

describe("BudgetPanel", () => {
  it("submits integer-fen amounts and distinguishes all budget metrics", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(successResponse());
    vi.stubGlobal("fetch", fetchMock);
    render(<BudgetPanel destinationName="杭州" />);

    fireEvent.change(screen.getByRole("textbox", { name: "整趟总预算（元）" }), { target: { value: "6000" } });
    fireEvent.change(screen.getByRole("textbox", { name: "预留金（元）" }), { target: { value: "600" } });
    fireEvent.change(screen.getByRole("combobox", { name: "类别" }), { target: { value: "住宿" } });
    fireEvent.change(screen.getByRole("textbox", { name: "费用项 1 已支付（元）" }), { target: { value: "2000" } });
    fireEvent.change(screen.getByRole("textbox", { name: "费用项 1 预计待支付（元）" }), { target: { value: "3000" } });
    fireEvent.click(screen.getByRole("button", { name: "计算预算" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(request.total_budget_fen).toBe(600000);
    expect(request.reserve_fen).toBe(60000);
    expect(request.cost_items[0]).toMatchObject({ paid_fen: 200000, unpaid_estimate_fen: 300000, completeness: "complete" });
    expect(await screen.findByRole("heading", { name: "预算概览" })).toBeVisible();
    expect(screen.getByText("已支付")).toBeVisible();
    expect(screen.getByText("剩余可安排")).toBeVisible();
    expect(screen.getByText("预计结余")).toBeVisible();
    expect(screen.getByText("计算请求编号：budget-request")).toBeVisible();
  });

  it("rejects more than two decimal places before making an API request", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<BudgetPanel destinationName="杭州" />);
    fireEvent.change(screen.getByRole("textbox", { name: "整趟总预算（元）" }), { target: { value: "10.001" } });
    fireEvent.click(screen.getByRole("button", { name: "计算预算" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("最多填写两位小数");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the user-entered non-platform quote label when selected", () => {
    render(<BudgetPanel destinationName="杭州" />);
    fireEvent.change(screen.getByRole("combobox", { name: "类别" }), { target: { value: "住宿" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "这是我补填的未报价费用" }));

    expect(screen.getByRole("note")).toHaveTextContent("用户填写，非平台报价");
  });
});
