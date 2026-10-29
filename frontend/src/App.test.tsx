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

const unconfiguredForecast = {
  ...mockForecast,
  state: "unconfigured",
  items: [],
  sources: [],
  message: "天气服务尚未配置。",
  coverage: null,
  error: { code: "UNCONFIGURED", message: "天气服务尚未配置。", retryable: false, request_id: "weather-unconfigured" },
};

function stubWeatherResponse(
  fetchMock: ReturnType<typeof vi.fn<typeof fetch>>,
  response: unknown = mockForecast,
) {
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(response), {
    status: 200, headers: { "content-type": "application/json" },
  }));
  vi.stubGlobal("fetch", fetchMock);
}

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

    expect(screen.getByRole("heading", { name: "先选好目的地与出发地" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
    expect(screen.queryByRole("navigation", { name: "旅行工具" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始规划" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请选择目的城市");
    expect(screen.queryByRole("heading", { name: "旅行预算" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers the current location by default and registered or custom departure places", () => {
    render(<App />);
    expect(screen.getByRole("combobox", { name: "目的城市" }).querySelectorAll("option").length).toBe(6);
    expect(Array.from(screen.getByRole("combobox", { name: "目的城市" }).querySelectorAll("option")).map((option) => [option.getAttribute("value"), option.textContent])).toEqual([
      ["", "请选择"], ["shanghai", "上海"], ["suzhou", "苏州"], ["wuxi", "无锡"],
      ["jiaxing", "嘉兴"], ["hangzhou", "杭州"],
    ]);
    expect(screen.getByRole("combobox", { name: "出发地点" })).toHaveValue("current");
    expect(screen.getByRole("option", { name: "自定义地点" })).toBeInTheDocument();
  });

  it("uses browser coordinates as the default origin when location permission is granted", () => {
    vi.stubGlobal("navigator", Object.assign(Object.create(navigator), {
      geolocation: {
        getCurrentPosition: (success: PositionCallback) => success({
          coords: { latitude: 30.25, longitude: 120.16 },
        } as GeolocationPosition),
      },
    }));
    render(<App />);
    activateDestination("hangzhou");
    expect(screen.getByText("当前位置", { selector: ".workspace-origin" })).toBeVisible();
    expect(screen.getByText("定位完成")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "交通" }));
    expect(screen.getByRole("textbox", { name: /起点/ })).toHaveValue("当前位置");
  });

  it("supports a custom departure place before entering the workspace", () => {
    render(<App />);
    fireEvent.change(screen.getByRole("combobox", { name: "出发地点" }), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("自定义出发地点"), { target: { value: "杭州东站" } });
    activateDestination("hangzhou");
    expect(screen.getByText("杭州东站", { selector: ".workspace-origin" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "交通" }));
    expect(screen.getByRole("textbox", { name: /起点/ })).toHaveValue("杭州东站");
  });

  it.each([["shanghai", "上海"], ["suzhou", "苏州"], ["wuxi", "无锡"], ["jiaxing", "嘉兴"], ["hangzhou", "杭州"]])(
    "opens a workspace for the registered city %s",
    (id, name) => {
      render(<App />);
      activateDestination(id);
      expect(screen.getByText(name, { selector: ".workspace-destination" })).toBeVisible();
    },
  );

  it("automatically requests today's weather after selecting a destination", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    stubWeatherResponse(fetchMock);
    render(<App />);
    activateDestination();

    expect(screen.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();
    expect(await screen.findByText("晴")).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const weatherCall = fetchMock.mock.calls[0];
    expect(weatherCall[0]).toBe("/api/weather/forecast");
    expect(JSON.parse(String(weatherCall[1]?.body))).toEqual({
      city_id: "shanghai", start_date: expect.any(String), end_date: expect.any(String),
    });
    expect(JSON.parse(String(weatherCall[1]?.body)).end_date).toBe(JSON.parse(String(weatherCall[1]?.body)).start_date);
    expect(screen.getByText("上海", { selector: ".workspace-destination" })).toBeVisible();
    const startDate = screen.getByLabelText("开始日期").getAttribute("value");
    const endDate = screen.getByLabelText("结束日期").getAttribute("value");
    expect(startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(endDate).toBe(startDate);
  });

  it("shows the automatically fetched today's weather inside the field note card", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (_input, init) => {
      const query = JSON.parse(String(init?.body)) as { start_date: string };
      const response = {
        ...mockForecast,
        items: mockForecast.items.map((day) => ({ ...day, date: query.start_date })),
        coverage: {
          requested: { start: query.start_date, end: query.start_date },
          covered: [{ start: query.start_date, end: query.start_date }],
          missing: [],
        },
      };
      return new Response(JSON.stringify(response), {
        status: 200, headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination("hangzhou");

    const card = screen.getByRole("complementary", { name: "杭州当天的天气摘要" });
    expect(await screen.findByText("晴", { selector: ".signal-card__quote" })).toBeVisible();
    expect(card).toHaveTextContent("20° / 13°");
    expect(card).toHaveTextContent("0 mm / 0%");
    expect(card).toHaveTextContent("5 km/h");
  });

  it("blocks a range longer than 16 local days without making an additional API call", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination();

    fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-27" } });
    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByRole("button", { name: "查询天气" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("单次最多查询 16 个当地日");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("posts the selected city and date range, then labels fixture results honestly", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    stubWeatherResponse(fetchMock);
    render(<App />);
    activateDestination("hangzhou");
    fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-27" } });
    fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-27" } });
    fireEvent.click(screen.getByRole("button", { name: "查询天气" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock).toHaveBeenLastCalledWith("/api/weather/forecast", expect.objectContaining({
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
    const fetchMock = vi.fn<typeof fetch>()
      .mockReturnValueOnce(pendingForecast)
      .mockResolvedValueOnce(new Response(JSON.stringify(unconfiguredForecast), {
        status: 200, headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    activateDestination("hangzhou");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "更换目的地" }));
    fireEvent.change(screen.getByRole("combobox", { name: "新目的城市" }), { target: { value: "suzhou" } });
    fireEvent.click(screen.getByRole("button", { name: "确认更换" }));
    resolveForecast?.(new Response(JSON.stringify(mockForecast), { status: 200, headers: { "content-type": "application/json" } }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("天气服务尚未配置"));
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText("苏州", { selector: ".workspace-destination" })).toBeVisible();
  });
});

describe("App feature navigation", () => {
  it("opens the assistant alongside the existing itinerary view without an automatic request", () => {
    const fetchMock = vi.fn<typeof fetch>();
    stubWeatherResponse(fetchMock, unconfiguredForecast);
    render(<App />);
    activateDestination("hangzhou");

    expect(screen.getByRole("button", { name: "行程" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "AI 助手" }));
    expect(screen.getByRole("heading", { name: "AI 旅行助手" })).toBeVisible();
    expect(screen.getByRole("button", { name: "AI 助手" })).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "行程" }));
    expect(screen.getByRole("heading", { name: "旅行行程" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("switches between weather, budget, and transport without duplicate API requests", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    stubWeatherResponse(fetchMock, unconfiguredForecast);
    render(<App />);
    activateDestination();

    fireEvent.click(screen.getByRole("button", { name: "交通" }));
    expect(screen.getByRole("heading", { name: "交通查询" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("交通服务尚未配置");
    expect(screen.getByRole("button", { name: "交通" })).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "预算" }));
    expect(screen.getByRole("heading", { name: "旅行预算" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "天气" }));
    expect(screen.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();
    expect(await screen.findByRole("status")).toHaveTextContent("天气服务尚未配置");
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
    expect(screen.getByRole("heading", { name: "先选好目的地与出发地" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
    expect(screen.queryByRole("navigation", { name: "旅行工具" })).not.toBeInTheDocument();
  });
});

