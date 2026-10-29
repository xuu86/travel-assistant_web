import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssistantResponse } from "./api";
import { AssistantPanel } from "./AssistantPanel";

const liveResponse: AssistantResponse = {
  state: "live",
  request_id: "assistant-r1",
  message: "",
  reply: "建议先确认天气；<img src=x onerror=alert(1)>",
  candidate_patch: { pace: "relaxed", travelers: 2 },
  sources: [{
    source_id: "weather.provider",
    display_name: "天气查询",
    url: "https://weather.example/forecast",
    retrieved_at: "2026-10-29T00:00:00Z",
    valid_from: null,
    valid_to: null,
    attribution: null,
    evidence_state: "verified",
  }],
  error: null,
};

afterEach(cleanup);

describe("AssistantPanel", () => {
  it("shows unconfigured status and keeps the prompt available", async () => {
    const unconfigured = {
      state: "unconfigured", request_id: "r", message: "AI 助手尚未配置。", reply: "",
      candidate_patch: null, sources: [],
      error: { code: "UNCONFIGURED", message: "AI 助手尚未配置。", retryable: false },
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(unconfigured), { status: 200 }));
    render(<AssistantPanel destinationName="杭州" startDate="2026-11-01" endDate="2026-11-03" fetchImpl={fetchMock} />);
    fireEvent.change(screen.getByLabelText("发送给 AI 助手"), { target: { value: "你好" } });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    expect(await screen.findByText("AI 服务尚未配置，其他旅行工具仍可使用。")).toBeVisible();
    expect(screen.getByLabelText("发送给 AI 助手")).toHaveValue("你好");
  });

  it("defaults context off, sends only selected context/evidence, and previews patch without applying", async () => {
    const onResponse = vi.fn();
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(liveResponse), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    render(<AssistantPanel
      destinationName="杭州"
      startDate="2026-11-01"
      endDate="2026-11-03"
      fetchImpl={fetchMock}
      onResponse={onResponse}
      evidence={[{
        evidence_id: "w-1", kind: "weather", state: "live", summary: "晴，最高 20°C。",
        source: liveResponse.sources![0],
      }]}
    />);

    expect(screen.getByRole("checkbox", { name: /将当前行程条件用于本次回答/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: /天气查询/ }));
    fireEvent.change(screen.getByLabelText("发送给 AI 助手"), { target: { value: "按我的条件安排" } });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.include_trip_context).toBe(false);
    expect(body.trip_context).toBeUndefined();
    expect(body.evidence).toHaveLength(1);
    expect(body.evidence[0].source.evidence_state).toBe("user_provided");
    expect(screen.getByText("待确认的条件建议")).toBeVisible();
    expect(screen.getByText("出行节奏")).toBeVisible();
    expect(screen.queryByRole("button", { name: /应用/ })).not.toBeInTheDocument();
    expect(onResponse).toHaveBeenCalledWith(liveResponse);
    expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeVisible();
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect(screen.getByText("天气查询 · 用户提供，未核实")).toBeVisible();
    expect(screen.queryByRole("link", { name: "天气查询" })).not.toBeInTheDocument();
  });

  it("includes trip context only after the current-turn toggle is enabled", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(liveResponse), { status: 200 }));
    render(<AssistantPanel destinationName="杭州" startDate="2026-11-01" endDate="2026-11-03" fetchImpl={fetchMock} />);

    fireEvent.click(screen.getByRole("checkbox", { name: /将当前行程条件用于本次回答/ }));
    fireEvent.change(screen.getByLabelText("发送给 AI 助手"), { target: { value: "推荐安排" } });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.include_trip_context).toBe(true);
    expect(body.trip_context).toEqual({ destination: "杭州", start_date: "2026-11-01", end_date: "2026-11-03" });
  });

  it("preserves input on failure and allows a user-triggered retry", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(new Response(JSON.stringify(liveResponse), { status: 200 }));
    render(<AssistantPanel destinationName="杭州" startDate="2026-11-01" endDate="2026-11-03" fetchImpl={fetchMock} />);

    const input = screen.getByLabelText("发送给 AI 助手");
    fireEvent.change(input, { target: { value: "如何安排？" } });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("请求失败");
    expect(input).toHaveValue("如何安排？");
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
