import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
});
