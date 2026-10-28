import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchTransportFares, fetchTransportRoute, TransportApiError } from "./api";

const fareQuery = {
  origin: { display_name: "上海虹桥", coordinate_system: "WGS84" },
  destination: { display_name: "杭州萧山", coordinate_system: "WGS84" },
  mode: "flight",
  travel_date: "2026-11-10",
  passenger_count: 2,
} as const;

const routeQuery = {
  origin: { display_name: "起点 A", coordinate_system: "WGS84" },
  destination: { display_name: "目的地 B", coordinate_system: "WGS84" },
  mode: "walking",
  depart_at: null,
} as const;

const fareResult = {
  state: "unconfigured",
  items: [],
  sources: [],
  queried_at: "2026-10-28T02:00:00Z",
  request_id: "fare-request",
  message: "交通查询尚未配置。",
  coverage: null,
  error: null,
} as const;

const routeResult = {
  state: "unconfigured",
  items: [],
  sources: [],
  queried_at: "2026-10-28T02:00:00Z",
  request_id: "route-request",
  message: "交通查询尚未配置。",
  coverage: null,
  error: null,
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

describe("transport API clients", () => {
  it("posts fare queries to the same-origin endpoint using the generated contract shape", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(fareResult));

    const result = await fetchTransportFares(fareQuery, fetchMock);

    expect(result.state).toBe("unconfigured");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/transport/fares/search",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fareQuery),
      }),
    );
  });

  it("posts one route mode at a time without mixing route and fare endpoints", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(routeResult));

    await fetchTransportRoute(routeQuery, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/transport/routes/search",
      expect.objectContaining({ body: JSON.stringify(routeQuery) }),
    );
  });

  it.each([
    [503, "PROVIDER_UNAVAILABLE", true],
    [429, "RATE_LIMITED", true],
    [422, "VALIDATION_ERROR", false],
  ] as const)("maps %s public errors without exposing the response body", async (status, code, retryable) => {
    const privateBody = "private-location-and-provider-response";
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      response(
        { code, message: "交通服务状态", retryable, request_id: "body-request", privateBody },
        { status },
      ),
    );

    const error = await fetchTransportFares(fareQuery, fetchMock).catch((value: unknown) => value);

    expect(error).toBeInstanceOf(TransportApiError);
    expect(error).toMatchObject({ code, requestId: "body-request", retryable, status });
    expect((error as Error).message).not.toContain(privateBody);
  });

  it("rejects invalid JSON and invalid result envelopes safely", async () => {
    const invalidJsonFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("not-json", { status: 503, headers: { "x-request-id": "invalid-json" } }),
    );
    const invalidResultFetch = vi.fn<typeof fetch>().mockResolvedValue(
      response({ items: [], privateBody: "secret" }),
    );

    const invalidJson = await fetchTransportRoute(routeQuery, invalidJsonFetch).catch(
      (value: unknown) => value,
    );
    const invalidResult = await fetchTransportRoute(routeQuery, invalidResultFetch).catch(
      (value: unknown) => value,
    );

    expect(invalidJson).toMatchObject({
      code: "TRANSPORT_RESPONSE_INVALID",
      requestId: "invalid-json",
      status: 503,
    });
    expect(invalidResult).toMatchObject({ code: "TRANSPORT_RESPONSE_INVALID", status: 200 });
    expect((invalidResult as Error).message).not.toContain("secret");
  });
});
