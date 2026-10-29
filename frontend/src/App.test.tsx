import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const mockForecast = {
  state: "demo",
  items: [{
    date: "2026-10-27", weather_code: 0, temperature_max_c: 20, temperature_min_c: 13,
    precipitation_probability_max_pct: 0, precipitation_sum_mm: 0, wind_speed_10m_max_kmh: 5,
    missing_fields: [],
  }],
  sources: [{
    source_id: "fixture.weather", display_name: "Weather fixture", url: "https://fixture.example/weather",
    retrieved_at: "2026-10-27T00:00:00Z", valid_from: null, valid_to: null,
    attribution: "Fixture only", evidence_state: "demo",
  }],
  queried_at: "2026-10-27T00:00:00Z", request_id: "weather-request",
  message: "天气数据来自测试 fixture。",
  coverage: {
    requested: { start: "2026-10-27", end: "2026-10-27" },
    covered: [{ start: "2026-10-27", end: "2026-10-27" }], missing: [],
  },
  error: null,
  location: {
    city_id: "shanghai", requested_latitude: 31.222222, requested_longitude: 121.458056,
    coordinate_system: "WGS84", resolved_latitude: null, resolved_longitude: null, elevation_m: null,
  },
} as const;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function activateDestination(cityId = "shanghai") {
  fireEvent.change(screen.getByRole("combobox", { name: "目的城市" }), { target: { value: cityId } });
  fireEvent.click(screen.getByRole("button", { name: "开始规划" }));
}

describe("App weather query", () => {
  it("requires an explicit registered destination before mounting tools or requesting data", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(screen.getByRole("heading", { name: "先选一座目的城市" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
    expect(screen.queryByRole("navigation", { name: "旅行工具" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始规划" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请选择目的城市");
    expect(screen.queryByRole("heading", { name: "旅行预算" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers exactly five registered destination id/name options without a default", () => {
    render(<App />);
    expect(screen.getAllByRole("option").map((option) => [option.getAttribute("value"), option.textContent])).toEqual([
      ["", "请选择"], ["shanghai", "上海"], ["suzhou", "苏州"], ["wuxi", "无锡"],
      ["jiaxing", "嘉兴"], ["hangzhou", "杭州"],
    ]);
  });

  it.each([["shanghai", "上海"], ["suzhou", "苏州"], ["wuxi", "无锡"], ["jiaxing", "嘉兴"], ["hangzhou", "杭州"]])(
    "opens a workspace for the registered city %s",
    (id, name) => {
      render(<App />);
      activateDestination(id);
      expect(screen.getByText(name, { selector: ".workspace-destination" })).toBeVisible();
    },
  );

  it("starts without a weather request and clearly labels the unconfigured service", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination();

    expect(screen.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("天气服务尚未配置");
    expect(screen.getByText("上海", { selector: ".workspace-destination" })).toBeVisible();
    const startDate = screen.getByLabelText("开始日期").getAttribute("value");
    const endDate = screen.getByLabelText("结束日期").getAttribute("value");
    expect(startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(endDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const startParts = startDate!.split("-").map(Number);
    const endParts = endDate!.split("-").map(Number);
    expect(Date.UTC(endParts[0], endParts[1] - 1, endParts[2]) - Date.UTC(startParts[0], startParts[1] - 1, startParts[2])).toBe(2 * 86_400_000);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks a range longer than 16 local days without calling the API", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination();

    fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-27" } });
    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByRole("button", { name: "查询天气" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("单次最多查询 16 个当地日");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts the selected city and date range, then labels fixture results honestly", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(mockForecast), {
      status: 200, headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination("hangzhou");
    fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-27" } });
    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-27" } });
    fireEvent.click(screen.getByRole("button", { name: "查询天气" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith("/api/weather/forecast", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ city_id: "hangzhou", start_date: "2026-10-27", end_date: "2026-10-27" }),
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("测试数据已载入");
    expect(screen.getByText("晴")).toBeInTheDocument();
    expect(screen.getByText(/测试 fixture/)).toBeVisible();

    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-28" } });
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("尚未查询天气");
  });

  it("ignores a weather response that arrives after the destination workspace was replaced", async () => {
    let resolveForecast: ((response: Response) => void) | undefined;
    const pendingForecast = new Promise<Response>((resolve) => { resolveForecast = resolve; });
    const fetchMock = vi.fn<typeof fetch>().mockReturnValue(pendingForecast);
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination("hangzhou");
    fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-27" } });
    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-27" } });
    fireEvent.click(screen.getByRole("button", { name: "查询天气" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "更换目的地" }));
    fireEvent.change(screen.getByRole("combobox", { name: "新目的城市" }), { target: { value: "suzhou" } });
    fireEvent.click(screen.getByRole("button", { name: "确认更换" }));
    resolveForecast?.(new Response(JSON.stringify(mockForecast), { status: 200, headers: { "content-type": "application/json" } }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("天气服务尚未配置"));
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getByText("苏州", { selector: ".workspace-destination" })).toBeVisible();
  });
});

describe("App feature navigation", () => {
  it("opens the assistant alongside the existing itinerary view without an automatic request", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination("hangzhou");

    expect(screen.getByRole("button", { name: "行程" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "AI 助手" }));
    expect(screen.getByRole("heading", { name: "AI 旅行助手" })).toBeVisible();
    expect(screen.getByRole("button", { name: "AI 助手" })).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "行程" }));
    expect(screen.getByRole("heading", { name: "旅行行程" })).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("switches between weather, budget, and transport without triggering API requests", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination();

    fireEvent.click(screen.getByRole("button", { name: "交通" }));
    expect(screen.getByRole("heading", { name: "交通查询" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("交通服务尚未配置");
    expect(screen.getByRole("button", { name: "交通" })).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    expect(screen.getByRole("heading", { name: "旅行预算" })).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "天气" }));
    expect(screen.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("天气服务尚未配置");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves budget drafts across tools and resets them only after confirming a destination change", () => {
    render(<App />);
    activateDestination("hangzhou");
    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    const budget = screen.getByRole("textbox", { name: "整趟总预算（元）" });
    fireEvent.change(budget, { target: { value: "6000" } });
    fireEvent.click(screen.getByRole("button", { name: "天气" }));
    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    expect(screen.getByRole("textbox", { name: "整趟总预算（元）" })).toHaveValue("6000");

    fireEvent.click(screen.getByRole("button", { name: "更换目的地" }));
    fireEvent.change(screen.getByRole("combobox", { name: "新目的城市" }), { target: { value: "suzhou" } });
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByRole("textbox", { name: "整趟总预算（元）" })).toHaveValue("6000");
    expect(screen.getByText("杭州", { selector: ".workspace-destination" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "更换目的地" }));
    fireEvent.change(screen.getByRole("combobox", { name: "新目的城市" }), { target: { value: "suzhou" } });
    fireEvent.click(screen.getByRole("button", { name: "确认更换" }));
    expect(screen.getByText("苏州", { selector: ".workspace-destination" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    expect(screen.getByRole("textbox", { name: "整趟总预算（元）" })).toHaveValue("");
  });

  it("returns to city selection after confirming and clears the workspace without a reload", () => {
    render(<App />);
    activateDestination("hangzhou");
    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    fireEvent.change(screen.getByRole("textbox", { name: "整趟总预算（元）" }), { target: { value: "4200" } });
    fireEvent.click(screen.getByRole("button", { name: "返回选择城市" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("将清除本页预算草稿");
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByRole("textbox", { name: "整趟总预算（元）" })).toHaveValue("4200");

    fireEvent.click(screen.getByRole("button", { name: "返回选择城市" }));
    fireEvent.click(screen.getByRole("button", { name: "确认返回" }));
    expect(screen.getByRole("heading", { name: "先选一座目的城市" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
    expect(screen.queryByRole("navigation", { name: "旅行工具" })).not.toBeInTheDocument();
  });
});

