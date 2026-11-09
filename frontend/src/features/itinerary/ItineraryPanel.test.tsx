import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it } from "vitest";
import { ItineraryPanel } from "./ItineraryPanel";

describe("ItineraryPanel", () => {
  afterEach(cleanup);
  it("adds an item and protects locked items from deletion", () => {
    render(<ItineraryPanel destinationName="上海" startDate="2026-10-27" endDate="2026-10-28" />);
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "外滩散步" } });
    fireEvent.change(screen.getByLabelText("备注 可选"), { target: { value: "傍晚" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    expect(screen.getByRole("heading", { name: "外滩散步" })).toBeVisible();
    expect(screen.getByText("傍晚")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "锁定" }));
    expect(screen.getByRole("button", { name: "删除" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "解锁" }));
    expect(screen.getByRole("button", { name: "删除" })).toBeEnabled();
  });

  it("requires an item title and offers each trip date", () => {
    render(<ItineraryPanel destinationName="杭州" startDate="2026-10-27" endDate="2026-10-29" />);
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请填写安排名称");
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["2026-10-27", "2026-10-28", "2026-10-29"]);
  });

  it("groups items by date, marks them complete, and edits existing items", () => {
    render(<ItineraryPanel destinationName="上海" startDate="2026-10-27" endDate="2026-10-28" />);
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "早茶" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    fireEvent.change(screen.getByLabelText("日期"), { target: { value: "2026-10-28" } });
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "博物馆" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));

    expect(screen.getByRole("heading", { name: /2026-10-27/ })).toBeVisible();
    expect(screen.getByRole("heading", { name: /2026-10-28/ })).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "已完成" })[0]);
    expect(screen.getByRole("heading", { name: "早茶" }).closest("article")).toHaveClass("is-completed");

    fireEvent.click(screen.getByRole("button", { name: "编辑 早茶" }));
    expect(screen.getByRole("heading", { name: "编辑安排" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "早茶（已改）" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    expect(screen.getByRole("heading", { name: "早茶（已改）" })).toBeVisible();
  });

  it("does not overwrite an item after it is locked during editing", () => {
    render(<ItineraryPanel destinationName="杭州" startDate="2026-10-27" endDate="2026-10-28" />);
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "湖滨散步" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    fireEvent.click(screen.getByRole("button", { name: "编辑 湖滨散步" }));
    fireEvent.click(screen.getByRole("button", { name: "锁定" }));
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "覆盖尝试" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    expect(screen.getByRole("alert")).toHaveTextContent("已锁定");
    expect(screen.getByRole("heading", { name: "湖滨散步" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "覆盖尝试" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "解锁" })).toBeVisible();
  });

  it("moves the new-item draft with the trip range and preserves existing out-of-range items", async () => {
    const { rerender } = render(<ItineraryPanel destinationName="杭州" startDate="2026-10-27" endDate="2026-10-28" />);
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "原日期安排" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));

    rerender(<ItineraryPanel destinationName="杭州" startDate="2026-10-29" endDate="2026-10-30" />);
    await waitFor(() => expect(screen.getByLabelText("日期")).toHaveValue("2026-10-29"));
    expect(screen.getByRole("status")).toHaveTextContent("有 1 项安排在日期范围外");
    expect(screen.getByRole("heading", { name: "原日期安排" })).toBeVisible();

    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "范围内安排" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    expect(screen.getByRole("heading", { name: "范围内安排" }).closest("section")).toHaveAttribute("aria-labelledby", "itinerary-day-2026-10-29");
  });

  it("rejects saving an edited item until its date is moved into the current trip range", () => {
    const { rerender } = render(<ItineraryPanel destinationName="杭州" startDate="2026-10-27" endDate="2026-10-28" />);
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "旧安排" } });
    fireEvent.click(screen.getByRole("button", { name: "添加到行程" }));
    rerender(<ItineraryPanel destinationName="杭州" startDate="2026-10-29" endDate="2026-10-30" />);
    fireEvent.click(screen.getByRole("button", { name: "编辑 旧安排" }));
    fireEvent.change(screen.getByLabelText("安排名称"), { target: { value: "编辑中的安排" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    expect(screen.getByRole("alert")).toHaveTextContent("当前旅行日期范围内");
    expect(screen.getByRole("heading", { name: "旧安排" })).toBeVisible();

    fireEvent.change(screen.getByLabelText("日期"), { target: { value: "2026-10-29" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
    expect(screen.getByRole("heading", { name: "编辑中的安排" })).toBeVisible();
  });
});
