import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it } from "vitest";
import type { components } from "../../shared/api-contracts";
import { WeatherApiError } from "./api";
import { WeatherPanel, type WeatherPanelState } from "./WeatherPanel";

const partialData = {
  state: "demo",
  items: [
    {
      date: "2026-10-27", weather_code: 0, temperature_max_c: 20, temperature_min_c: 13,
      precipitation_probability_max_pct: 0, precipitation_sum_mm: 0, wind_speed_10m_max_kmh: null,
      missing_fields: ["wind_speed_10m_max_kmh"],
    },
    {
      date: "2026-10-29", weather_code: 999, temperature_max_c: null, temperature_min_c: null,
      precipitation_probability_max_pct: null, precipitation_sum_mm: null, wind_speed_10m_max_kmh: null,
      missing_fields: ["temperature_max_c", "temperature_min_c", "precipitation_probability_max_pct", "precipitation_sum_mm", "wind_speed_10m_max_kmh"],
    },
  ],
  sources: [{
    source_id: "fixture.weather", display_name: "Weather fixture", url: "https://fixture.example/weather",
    retrieved_at: "2026-10-27T00:00:00Z", valid_from: null, valid_to: null,
    attribution: "Fixture only", evidence_state: "demo",
  }],
  queried_at: "2026-10-27T00:00:00Z", request_id: "weather-request",
  message: "天气数据来自测试 fixture。",
  coverage: {
    requested: { start: "2026-10-27", end: "2026-10-29" },
    covered: [{ start: "2026-10-27", end: "2026-10-27" }, { start: "2026-10-29", end: "2026-10-29" }],
    missing: [{ start: "2026-10-28", end: "2026-10-28" }],
  },
  error: null,
  location: {
    city_id: "shanghai", requested_latitude: 31.222222, requested_longitude: 121.458056,
    coordinate_system: "WGS84", resolved_latitude: null, resolved_longitude: null, elevation_m: null,
  },
} satisfies components["schemas"]["WeatherResult"];

afterEach(cleanup);

describe("WeatherPanel", () => {
  it("explains that weather is not configured without showing demo data", () => {
    render(<WeatherPanel cityName="上海" state={{ status: "unconfigured" }} />);
    expect(screen.getByRole("heading", { name: "天气预报" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("天气服务尚未配置");
    expect(screen.getByText("当前页面不会用演示数据或旧数据填补天气预报。")).toBeVisible();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows idle and loading states accessibly", () => {
    const { rerender } = render(<WeatherPanel cityName="苏州" state={{ status: "idle" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("尚未查询天气");
    expect(screen.getByText(/不会保留与当前条件不一致的旧结果/)).toBeVisible();
    rerender(<WeatherPanel cityName="苏州" state={{ status: "loading" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("正在读取天气预报");
    expect(screen.getByLabelText("正在加载天气预报")).toBeVisible();
  });

  it("shows partial coverage, null metrics, and unknown weather codes safely", () => {
    const state: WeatherPanelState = { status: "success", data: partialData };
    render(<WeatherPanel cityName="上海" state={state} />);
    expect(screen.getByText(/以下日期暂无预报：10月28日/)).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getByText("测试数据 · 部分日期已覆盖")).toBeVisible();
    expect(screen.getByText("晴")).toBeVisible();
    expect(screen.getByText("天气现象待识别（999）")).toBeVisible();
    expect(screen.getAllByText("暂无").length).toBeGreaterThan(0);
    expect(screen.getByText(/来源：Weather fixture/)).toBeVisible();
    expect(screen.getByText(/测试 fixture/)).toBeVisible();
  });

  it.each([
    ["rate_limited", "查询暂受额度限制"],
    ["policy_unavailable", "服务权限暂不可用"],
    ["unavailable", "天气服务暂不可用"],
    ["no_coverage", "请求日期暂无覆盖"],
  ] as const)("renders the %s result state honestly", (resultState, label) => {
    const state: WeatherPanelState = {
      status: "success",
      data: {
        ...partialData, state: resultState, items: [], sources: [], message: label,
        coverage: resultState === "no_coverage" ? {
          requested: { start: "2026-10-27", end: "2026-10-29" },
          covered: [], missing: [{ start: "2026-10-27", end: "2026-10-29" }],
        } : null,
      },
    };
    render(<WeatherPanel cityName="上海" state={state} />);
    expect(screen.getAllByRole("status")[0]).toHaveTextContent(label);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(label))[0]).toBeVisible();
  });

  it("renders an unconfigured API result without falling back to fixture data", () => {
    const state: WeatherPanelState = {
      status: "success",
      data: {
        ...partialData,
        state: "unconfigured",
        items: [],
        sources: [],
        coverage: null,
        message: "天气服务尚未配置。",
      },
    };
    render(<WeatherPanel cityName="杭州" state={state} />);

    expect(screen.getAllByRole("status")[0]).toHaveTextContent("天气服务尚未配置");
    expect(screen.getByText("当前页面不会用演示数据或旧数据填补天气预报。")).toBeVisible();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows safe provider errors and request identifiers", () => {
    const error = new WeatherApiError("天气服务暂不可用。", {
      code: "PROVIDER_UNAVAILABLE", requestId: "error-request", retryable: true, status: 503,
    });
    render(<WeatherPanel cityName="杭州" state={{ status: "error", error }} />);
    expect(screen.getByRole("status")).toHaveTextContent("天气服务暂不可用。");
    expect(screen.getByText("请求编号：error-request")).toBeVisible();
  });
});




