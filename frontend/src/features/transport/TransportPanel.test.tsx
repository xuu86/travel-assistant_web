import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TransportPanel } from "./TransportPanel";
import type { FareResponse } from "./api";

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

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fillFareQuery() {
  fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海虹桥" } });
  fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "杭州萧山" } });
  fireEvent.change(screen.getByRole("combobox", { name: /起飞机场/ }), { target: { value: "SHA" } });
  fireEvent.change(screen.getByRole("combobox", { name: /到达机场/ }), { target: { value: "HGH" } });
  fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
  fireEvent.change(screen.getByLabelText(/成人数量/), { target: { value: "2" } });
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
    expect(screen.queryByRole("button", { name: "市内路线" })).not.toBeInTheDocument();
    expect(screen.queryByText(/票价|费用项目/)).not.toBeInTheDocument();
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

  it("submits an explicit schedule date and never renders returned price fields", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse()));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByText("FAKE-01")).toBeVisible();
    expect(screen.queryByText(/金额待核实|票价|费用项目|¥/)).not.toBeInTheDocument();
    expect(screen.getByText("航班 · 2026-11-10")).toBeVisible();
    fireEvent.click(screen.getByText("测试数据 · 信息护照"));
    expect(screen.getByText("合成交通来源")).toBeVisible();
    expect(screen.getByText("测试数据 · 信息护照")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith("/api/transport/fares/search", expect.objectContaining({
      method: "POST",
    }));
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody).toEqual({
      origin: { display_name: "上海虹桥", place_id: "SHA", coordinate_system: "WGS84" },
      destination: { display_name: "杭州萧山", place_id: "HGH", coordinate_system: "WGS84" },
      mode: "flight",
      travel_date: "2026-11-10",
      passenger_count: 2,
      child_count: null,
    });
  });

  it("inherits the selected origin coordinates and submits optional child passengers", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse()));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel
      initialDestination="杭州"
      initialOrigin={{
        display_name: "当前位置",
        latitude: 30.25,
        longitude: 120.16,
        coordinate_system: "WGS84",
      }}
      originLocationStatus="resolved"
    />);
    fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "杭州萧山" } });
    fireEvent.change(screen.getByRole("combobox", { name: /起飞机场/ }), { target: { value: "SHA" } });
    fireEvent.change(screen.getByRole("combobox", { name: /到达机场/ }), { target: { value: "HGH" } });
    fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
    fireEvent.change(screen.getByLabelText(/成人数量/), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/^儿童人数/), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    await screen.findByText("FAKE-01");
    expect(fetchMock).toHaveBeenCalledWith("/api/transport/fares/search", expect.objectContaining({
      method: "POST",
    }));
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody).toEqual({
      origin: {
        display_name: "当前位置", place_id: "SHA", latitude: 30.25, longitude: 120.16, coordinate_system: "WGS84",
      },
      destination: { display_name: "杭州萧山", place_id: "HGH", coordinate_system: "WGS84" },
      mode: "flight",
      travel_date: "2026-11-10",
      passenger_count: 3,
      child_count: 1,
    });
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
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州" />);
    fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海虹桥" } });
    fireEvent.change(screen.getByRole("textbox", { name: /目的地/ }), { target: { value: "杭州东" } });
    fireEvent.change(screen.getByLabelText(/交通方式/), { target: { value: "rail" } });
    fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
    fireEvent.change(screen.getByLabelText(/成人数量/), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByRole("heading", { name: /上海虹桥.*杭州东/ })).toBeVisible();
    expect(screen.getByText("G101")).toBeVisible();
    expect(screen.getByText(/G202/)).toBeVisible();
    expect(screen.getByText(/换乘地点：苏州北/)).toBeVisible();
    expect(screen.queryByText(/人合计|票价|费用项目|¥360\.00/)).not.toBeInTheDocument();
    expect(screen.getByText("编号待核实")).toBeVisible();
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(requestBody.mode).toBe("rail");
    expect(requestBody.origin).not.toHaveProperty("place_id");
    expect(requestBody.destination).not.toHaveProperty("place_id");
  });

  it("clears a prior fare result when a query condition changes", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse())));
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
    expect(await screen.findByText("FAKE-01")).toBeVisible();

    fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海站" } });
    expect(screen.queryByText("FAKE-01")).not.toBeInTheDocument();
    expect(screen.getByText(/提交查询后显示班次与来源/)).toBeVisible();
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
    fireEvent.change(screen.getByRole("combobox", { name: /到达机场/ }), { target: { value: "HGH" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
    expect(await screen.findByRole("heading", { name: /上海虹桥.*新目的地/ })).toBeVisible();

    resolveOld?.(jsonResponse(fareResponse()));
    await waitFor(() => expect(screen.getByRole("heading", { name: /上海虹桥.*新目的地/ })).toBeVisible());
    expect(screen.queryByRole("heading", { name: /上海虹桥.*杭州萧山/ })).not.toBeInTheDocument();
  });
  it("defaults to nearest airports and requires a selection only when the location is unknown", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="未知目的地" />);
    fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "未知起点" } });
    fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("请选择起飞机场和到达机场");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks flight queries above the provider passenger limit", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    render(<TransportPanel initialDestination="杭州萧山" />);
    fireEvent.change(screen.getByRole("textbox", { name: /起点/ }), { target: { value: "上海虹桥" } });
    fireEvent.change(screen.getByRole("combobox", { name: /起飞机场/ }), { target: { value: "SHA" } });
    fireEvent.change(screen.getByRole("combobox", { name: /到达机场/ }), { target: { value: "HGH" } });
    fireEvent.change(screen.getByLabelText(/目标出行日期/), { target: { value: "2026-11-10" } });
    fireEvent.change(screen.getByLabelText(/成人数量/), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("不能超过 9 人");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("clears a prior fare result when an airport code changes", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(fareResponse())));
    render(<TransportPanel initialDestination="杭州" />);
    fillFareQuery();
    fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
    expect(await screen.findByText("FAKE-01")).toBeVisible();

    fireEvent.change(screen.getByRole("combobox", { name: /起飞机场/ }), { target: { value: "PVG" } });
    expect(screen.queryByText("FAKE-01")).not.toBeInTheDocument();
    expect(screen.getByText(/提交查询后显示班次与来源/)).toBeVisible();
  });

  it("marks nearest default airports and allows the user to change them", () => {
    render(<TransportPanel initialDestination="杭州" initialOrigin={{
      display_name: "上海",
      coordinate_system: "WGS84",
    }} />);

    expect(screen.getByRole("combobox", { name: /起飞机场/ })).toHaveValue("SHA");
    expect(screen.getByRole("combobox", { name: /到达机场/ })).toHaveValue("HGH");
    expect(screen.getAllByText(/最近机场 · 默认选择/)).toHaveLength(2);
    fireEvent.change(screen.getByRole("combobox", { name: /起飞机场/ }), { target: { value: "PVG" } });
    expect(screen.getByRole("combobox", { name: /起飞机场/ })).toHaveValue("PVG");
    expect(screen.getByText(/最近机场 · 可更改/)).toBeVisible();
  });
});


describe("FlyAI railway display", () => {
  it.each(["https://www.fliggy.com/train?fixture=1", "javascript:alert(1)"])(
    "renders schedule details without returned prices or free-form fare hints: %s", async (bookingUrl) => {
      const base = fareResponse();
      const response = fareResponse({
        platform_hint: "<img src=x onerror=alert(1)>平台原文",
        items: [{ ...base.items![0], mode: "rail", price_fen: null, booking_url: bookingUrl,
          passenger_count: null,
          segments: [{ segment_id: "train-1", service_number: "G-TEST", seat_class: "二等座" }],
        }],
      });
      vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(response)));
      render(<TransportPanel initialDestination="杭州" />);
      fillFareQuery();
      fireEvent.change(screen.getByLabelText(/交通方式/), { target: { value: "rail" } });
      fireEvent.click(screen.getByRole("button", { name: /查询班次/ }));
      expect(await screen.findByText("G-TEST")).toBeVisible();
      expect(screen.queryByText(/票价|金额待核实|费用项目|¥|平台提示/)).not.toBeInTheDocument();
      expect(screen.getByText("席别：二等座")).toBeVisible();
      expect(document.querySelector("img[src=x]")).toBeNull();
      expect(screen.queryByRole("link", { name: /详情|购票/ })).not.toBeInTheDocument();
    },
  );
});
