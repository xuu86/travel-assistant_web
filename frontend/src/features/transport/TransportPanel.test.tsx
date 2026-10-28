import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TransportPanel } from "./TransportPanel";
import type { FareResponse, RouteMode, RouteResponse } from "./api";

const source = {
  source_id: "fixture.transport",
  display_name: "合成交通来源",
  retrieved_at: "2026-10-28T02:00:00Z",
  evidence_state: "demo" as const,
  attribution: "仅用于测试",
};

function fareResponse(overrides: Partial<FareResponse> = {}): FareResponse {
  return {
    state: "demo",
    items: [{
      offer_id: "fare-1",
      source_id: source.source_id,
      mode: "flight",
      travel_date: "2026-11-10",
      segments: [{ segment_id: "segment-1", origin_name: "上海虹桥", destination_name: "杭州萧山" }],
      service_number: "FAKE-01",
      origin_name: "上海虹桥",
      destination_name: "杭州萧山",
      price_fen: null,
      currency_code: "CNY",
      price_basis: "unknown",
      price_scope: "unknown",
      passenger_count: 2,
      availability: "unknown",
      remaining_seats: null,
      included_charges: [],
      evidence_state: "demo",
      missing_fields: ["price_fen", "remaining_seats"],
    }],
    sources: [source],
    queried_at: "2026-10-28T02:00:00Z",
    request_id: "fare-request",
    message: "测试结果；非真实交通数据。",
    coverage: null,
    error: null,
    ...overrides,
  };
}

function routeResponse(mode: RouteMode, overrides: Partial<RouteResponse> = {}): RouteResponse {
  return {
    state: "demo",
    items: [{
      route_id: `${mode}-route`,
      source_id: source.source_id,
      mode,
      origin_name: "地点甲",
      destination_name: "地点乙",
      distance_m: null,
      duration_seconds: null,
      duration_basis: "unknown",
      steps: [],
      geometry_points: null,
      fare_amount_fen: null,
      currency_code: "CNY",
      fare_basis: "unknown",
      fare_evidence_state: "unknown",
      evidence_state: "demo",
      missing_fields: ["distance_m", "duration_seconds", "geometry_points", "fare_amount_fen"],
    }],
    sources: [source],
    queried_at: "2026-10-28T02:00:00Z",
    request_id: `${mode}-request`,
    message: "测试结果；非真实交通数据。",
    coverage: null,
    error: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fillFareQuery() {
  fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海虹桥" } });
  fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "杭州萧山" } });
  fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
  fireEvent.change(screen.getByLabelText(/乘客人数/), { target: { value: "2" } });
}

function fillRouteQuery() {
  fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "地点甲" } });
  fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "地点乙" } });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TransportPanel", () => {
  it("starts unconfigured without issuing requests or showing synthetic results", () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);

    expect(screen.getByRole("heading", { name: "交通查询" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("交通服务尚未配置");
    expect(screen.getByRole("status")).toHaveTextContent("提交查询后仍不会使用测试数据或旧结果填补。");
    expect(screen.queryByText("测试 fixture")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("prefills the destination while leaving origin empty and both editable", () => {
    render(<TransportPanel initialDestination="杭州" />);
    expect(screen.getByRole("textbox", { name: /起点/ })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: /目的地/ })).toHaveValue("杭州");
    fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "杭州东" } });
    expect(screen.getByRole("textbox", { name: /目的地/ })).toHaveValue("杭州东");
  });

  it("displays the backend unconfigured state without substituting fixture data", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse({
      state: "unconfigured",
      items: [],
      sources: [],
      message: "交通查询尚未配置。",
    })));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    await screen.findByText("交通查询尚未配置。");
    const resultStatus = screen.getByRole("status");
    expect(resultStatus).toHaveTextContent("服务尚未配置");
    expect(resultStatus).toHaveTextContent("交通查询尚未配置。");
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.queryByText("测试 fixture")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("submits an explicit fare date and keeps unknown amounts and source evidence distinct", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse()));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByText("金额待核实")).toBeVisible();
    expect(screen.getByText(/计价人数基准待核实/)).toBeVisible();
    expect(screen.getByText("航班 · 2026-11-10")).toBeVisible();
    expect(screen.getByText(/合成交通来源/)).toBeVisible();
    expect(screen.getByText("测试 fixture")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/transport/fares/search", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        origin: { display_name: "上海虹桥", coordinate_system: "WGS84" },
        destination: { display_name: "杭州萧山", coordinate_system: "WGS84" },
        mode: "flight",
        travel_date: "2026-11-10",
        passenger_count: 2,
      }),
    }));
  });

  it("renders provider-returned transfer segments without inventing a through service", async () => {
    const railOffer = fareResponse().items![0];
    const response = fareResponse({ items: [{
      ...railOffer,
      offer_id: "rail-transfer",
      mode: "rail",
      destination_name: "杭州东",
      service_number: null,
      price_fen: 36000,
      price_basis: "party_total",
      price_scope: "entire_journey",
      segments: [
        { segment_id: "leg-1", origin_name: "上海虹桥", destination_name: "苏州北", service_number: "G101" },
        { segment_id: "leg-2", origin_name: "苏州北", destination_name: "杭州东", service_number: "G202", transfer_place: "苏州北" },
      ],
    }] });
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response)));
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.change(screen.getByLabelText(/交通方式/), { target: { value: "rail" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByRole("heading", { name: /上海虹桥.*杭州东/ })).toBeVisible();
    expect(screen.getByText("G101")).toBeVisible();
    expect(screen.getByText(/G202/)).toBeVisible();
    expect(screen.getByText(/换乘地点：苏州北/)).toBeVisible();
    expect(screen.getByText(/2 人合计/)).toBeVisible();
    expect(screen.getByText("编号待核实")).toBeVisible();
  });

  it("isolates each route mode when one request fails and other modes succeed", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (_input, init) => {
      const query = JSON.parse(String(init?.body)) as { mode: RouteMode };
      if (query.mode === "walking") {
        return jsonResponse({
          code: "PROVIDER_UNAVAILABLE",
          message: "步行服务暂不可用。",
          retryable: true,
          request_id: "walking-error",
        }, 503);
      }
      return jsonResponse(routeResponse(query.mode));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fillRouteQuery();
    fireEvent.click(screen.getByRole("button", { name: "市内路线" }));

    fireEvent.click(screen.getByRole("button", { name: "查询公交 / 地铁路线" }));
    expect(await screen.findByText("未提供地图线路，不绘制直线或估算路径。")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查询步行路线" }));
    expect(await screen.findByText("步行服务暂不可用。")).toBeVisible();
    expect(screen.getByRole("button", { name: "重试步行路线" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "查询出租车 / 驾车路线" }));
    expect(await screen.findByRole("heading", { name: "出租车 / 驾车" })).toBeVisible();

    const transit = screen.getByRole("region", { name: "公交 / 地铁查询结果" });
    const walking = screen.getByRole("region", { name: "步行查询结果" });
    const taxi = screen.getByRole("region", { name: "出租车 / 驾车查询结果" });
    expect(within(transit).getByText("未提供地图线路，不绘制直线或估算路径。")).toBeVisible();
    expect(within(walking).getByRole("alert")).toHaveTextContent("步行服务暂不可用。");
    expect(within(taxi).getByText("金额待核实")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("clears a prior fare result when a query condition changes", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse())));
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
    expect(await screen.findByText("金额待核实")).toBeVisible();

    fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海站" } });
    expect(screen.queryByText("金额待核实")).not.toBeInTheDocument();
    expect(screen.getByText(/提交查询后显示来源与结果/)).toBeVisible();
  });

  it("keeps route results when only fare-specific query conditions change", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(routeResponse("transit"))));
    render(<TransportPanel initialDestination="杭州" />);
    fillRouteQuery();
    fireEvent.click(screen.getByRole("button", { name: "市内路线" }));
    fireEvent.click(screen.getByRole("button", { name: "查询公交 / 地铁路线" }));
    expect(await screen.findByText("未提供地图线路，不绘制直线或估算路径。")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "班次与票价" }));
    fireEvent.change(screen.getByLabelText(/交通方式/), { target: { value: "rail" } });
    fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
    fireEvent.click(screen.getByRole("button", { name: "市内路线" }));

    const transit = screen.getByRole("region", { name: "公交 / 地铁查询结果" });
    expect(within(transit).getByText("未提供地图线路，不绘制直线或估算路径。")).toBeVisible();
  });

  it("does not allow an earlier slow response to replace a result for changed conditions", async () => {
    let resolveOld: ((response: Response) => void) | undefined;
    const oldRequest = new Promise<Response>((resolve) => { resolveOld = resolve; });
    const newData = fareResponse({
      items: fareResponse().items?.map((offer) => ({ ...offer, offer_id: "new-fare", destination_name: "新目的地" })),
      request_id: "new-request",
    });
    const fetchMock = vi.fn<typeof fetch>()
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce(jsonResponse(newData));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "新目的地" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
    expect(await screen.findByRole("heading", { name: /上海虹桥.*新目的地/ })).toBeVisible();

    resolveOld?.(jsonResponse(fareResponse()));
    await waitFor(() => expect(screen.getByRole("heading", { name: /上海虹桥.*新目的地/ })).toBeVisible());
    expect(screen.queryByRole("heading", { name: /上海虹桥.*杭州萧山/ })).not.toBeInTheDocument();
  });
});
