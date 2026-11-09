import { afterEach, expect, it, vi } from "vitest";
import { fetchStaticMap, searchPlaces } from "./api";

const payload = {
  state: "live", city_id: "shanghai", category: "attractions", page: 1, has_more: false,
  items: [{ id: "B001", name: "公园", location: { longitude: 121.47, latitude: 31.23, coordinate_system: "GCJ02" } }],
  sources: [], request_id: "fixture", queried_at: "2026-11-04T10:00:00Z", message: "地点资料",
};
afterEach(() => { vi.unstubAllGlobals(); });

it.each([
  { ...payload, city_id: "hangzhou" },
  { ...payload, category: "hotels" },
  { ...payload, state: "unavailable" },
  { ...payload, items: [{ ...payload.items[0], location: { longitude: 121.47, latitude: 31.23, coordinate_system: "WGS84" } }] },
])("rejects wrong-city, wrong-category, contradictory or wrong-coordinate responses %#", async (body) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
  await expect(searchPlaces("attractions", { city_id: "shanghai", keywords: "", page: 1 })).rejects.toThrow("无法识别的结果");
});

it("posts a GCJ02 point to the same-origin image proxy without a supplier key", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["image"]), { headers: { "content-type": "image/png" } }));
  vi.stubGlobal("fetch", fetchMock);
  const query = { city_id: "shanghai", location: { longitude: 121.47, latitude: 31.23, coordinate_system: "GCJ02" as const }, zoom: 15 };
  const blob = await fetchStaticMap(query);
  expect(blob.type).toBe("image/png");
  expect(fetchMock).toHaveBeenCalledWith("/api/maps/static", expect.objectContaining({ body: JSON.stringify(query) }));
});

it("shows public map errors and rejects an HTTP-200 JSON response as an image", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ message: "高德服务额度已用尽。" }), { status: 429 }))
    .mockResolvedValueOnce(new Response("{}", { headers: { "content-type": "application/json" } })));
  await expect(fetchStaticMap({ city_id: "shanghai", zoom: 13 })).rejects.toThrow("高德服务额度已用尽。");
  await expect(fetchStaticMap({ city_id: "shanghai", zoom: 13 })).rejects.toThrow("地图暂不可用");
});
