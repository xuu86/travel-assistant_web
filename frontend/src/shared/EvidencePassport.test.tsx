import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it } from "vitest";
import { EvidencePassport } from "./EvidencePassport";

afterEach(cleanup);

describe("EvidencePassport", () => {
  it("shows source, retrieval time, validity and explicit coverage when opened", () => {
    render(<EvidencePassport
      source={{
        source_id: "weather.provider",
        display_name: "天气服务",
        url: "https://example.com/weather",
        retrieved_at: "2026-11-15T01:00:00Z",
        valid_from: "2026-11-15T00:00:00Z",
        valid_to: "2026-11-20T00:00:00Z",
        evidence_state: "verified",
      }}
      coverage={{
        requested: { start: "2026-11-16", end: "2026-11-18" },
        covered: [{ start: "2026-11-16", end: "2026-11-17" }],
        missing: [{ start: "2026-11-18", end: "2026-11-18" }],
      }}
    />);

    fireEvent.click(screen.getByText("已核实 · 信息护照"));
    expect(screen.getByText("天气服务")).toBeVisible();
    expect(screen.getByText("weather.provider")).toBeVisible();
    expect(screen.getByText("请求范围").parentElement).toHaveTextContent("2026-11-16 至 2026-11-18");
    expect(screen.getByText("未覆盖").parentElement).toHaveTextContent("2026-11-18");
    expect(screen.getByRole("link", { name: "打开来源 ↗" })).toHaveAttribute("href", "https://example.com/weather");
  });

  it("does not imply a user-provided value has a provider timestamp or expiry", () => {
    render(<EvidencePassport source={{ display_name: "用户手动录入", evidence_state: "user_provided" }} />);
    fireEvent.click(screen.getByText("用户提供 · 信息护照"));

    expect(screen.getByText("用户手动录入")).toBeVisible();
    expect(screen.getByText("未记录")).toBeVisible();
    expect(screen.getByText("来源未提供；当前无法判断是否仍有效")).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("rejects non-http source links", () => {
    render(<EvidencePassport source={{ display_name: "数据源", url: "javascript:alert(1)", evidence_state: "unknown" }} />);
    fireEvent.click(screen.getByText("状态未知 · 信息护照"));
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
