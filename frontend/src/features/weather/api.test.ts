import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchWeatherForecast, WeatherApiError } from "./api";

const query = {
  city_id: "shanghai",
  start_date: "2026-10-27",
  end_date: "2026-10-29",
} as const;

const successBody = {
  state: "partial",
  items: [],
  sources: [],
  queried_at: "2026-10-27T00:00:00Z",
  request_id: "req-weather",
  message: "",
  coverage: {
    requested: { start: "2026-10-27", end: "2026-10-29" },
    covered: [{ start: "2026-10-27", end: "2026-10-27" }],
    missing: [{ start: "2026-10-28", end: "2026-10-29" }],
  },
  error: null,
  location: {
    city_id: "shanghai",
    requested_latitude: 31.222222,
    requested_longitude: 121.458056,
    coordinate_system: "WGS84",
    resolved_latitude: null,
    resolved_longitude: null,
    elevation_m: null,
  },
} as const;

function response(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", "x-request-id": "header-request" },
    ...init,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchWeatherForecast", () => {
  it("posts to the same-origin weather endpoint and returns partial data", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(successBody));

    const result = await fetchWeatherForecast(query, fetchMock);

    expect(result.state).toBe("partial");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/weather/forecast",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(query),
      }),
    );
  });

  it.each([
    [503, "PROVIDER_UNAVAILABLE", true],
    [429, "RATE_LIMITED", true],
    [422, "VALIDATION_ERROR", false],
  ] as const)("maps %s public errors without logging the request body", async (status, code, retryable) => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      response(
        {
          code,
          message: "天气服务状态",
          retryable,
          request_id: "body-request",
        },
        { status },
      ),
    );

    await expect(fetchWeatherForecast(query, fetchMock)).rejects.toMatchObject({
      code,
      requestId: "body-request",
      retryable,
      status,
    });
  });

  it("rejects invalid JSON with a safe client error", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("not-json", {
        status: 503,
        headers: { "x-request-id": "invalid-json-request" },
      }),
    );

    const error = await fetchWeatherForecast(query, fetchMock).catch((value: unknown) => value);

    expect(error).toBeInstanceOf(WeatherApiError);
    expect(error).toMatchObject({
      code: "WEATHER_RESPONSE_INVALID",
      requestId: "invalid-json-request",
      status: 503,
    });
    expect((error as Error).message).not.toContain("not-json");
  });

  it("rejects malformed success payloads before they reach the UI", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({ state: "live", items: [] }));

    await expect(fetchWeatherForecast(query, fetchMock)).rejects.toMatchObject({
      code: "WEATHER_RESPONSE_INVALID",
      status: 200,
    });
  });
});
