import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import { PlacesPanel } from "./PlacesPanel";
import { searchPlaces, type PlaceResult } from "./api";

vi.mock("./api", () => ({ searchPlaces: vi.fn() }));
const search = vi.mocked(searchPlaces);
const point = { id: "B001", source_id: "amap.place" as const, name: "测试酒店", address: "上海市测试路", location: {
  longitude: 121.47, latitude: 31.23, coordinate_system: "GCJ02" as const,
} };
const result: PlaceResult = {
  state: "live", city_id: "shanghai", category: "hotels", page: 1, has_more: true,
  items: [point, { id: "B002", source_id: "amap.place", name: "无坐标酒店", location: null }], sources: [],
  request_id: "fixture", queried_at: "2026-11-04T10:00:00Z", message: "仅展示地点资料。",
};
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("searches explicitly, pages with submitted keywords, and selects only located places", async () => {
  search.mockResolvedValueOnce(result).mockResolvedValueOnce({ ...result, page: 2, has_more: false });
  const onSelect = vi.fn();
  render(<PlacesPanel category="hotels" cityId="shanghai" cityName="上海" onSelect={onSelect} />);
  expect(search).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("酒店关键词"), { target: { value: " 浦东 " } });
  fireEvent.click(screen.getByRole("button", { name: /查询酒店/ }));
  await screen.findByRole("heading", { name: point.name });
  expect(search).toHaveBeenCalledWith("hotels", { city_id: "shanghai", keywords: "浦东", page: 1 }, expect.any(AbortSignal));
  expect(screen.getByRole("button", { name: "在地图查看无坐标酒店" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "在地图查看测试酒店" }));
  expect(onSelect).toHaveBeenCalledWith(point);
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  await waitFor(() => expect(search).toHaveBeenLastCalledWith("hotels", { city_id: "shanghai", keywords: "浦东", page: 2 }, expect.any(AbortSignal)));
  await waitFor(() => expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled());
});

it("cancels an edited query and ignores an old response even if the transport resolves it", async () => {
  let complete!: (data: PlaceResult) => void;
  search.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }));
  render(<PlacesPanel category="hotels" cityId="shanghai" cityName="上海" onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: /查询酒店/ }));
  expect(screen.getByRole("status")).toHaveTextContent("正在查询");
  const signal = search.mock.calls[0][2];
  fireEvent.change(screen.getByLabelText("酒店关键词"), { target: { value: "新的关键词" } });
  expect(signal?.aborted).toBe(true);
  await act(async () => complete(result));
  expect(screen.queryByRole("heading", { name: point.name })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /查询酒店/ })).toBeEnabled();
});

it("shows provider failure distinctly from a successful empty query and permits retry", async () => {
  search.mockResolvedValueOnce({ ...result, items: [], state: "rate_limited", has_more: false, message: "高德服务额度已用尽。" })
    .mockResolvedValueOnce({ ...result, items: [], state: "empty", has_more: false, message: "未查询到符合条件的地点。" });
  render(<PlacesPanel category="hotels" cityId="shanghai" cityName="上海" onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: /查询酒店/ }));
  await screen.findByText("高德服务额度已用尽。");
  expect(screen.queryByText("未查询到符合条件的地点。")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /查询酒店/ }));
  await screen.findByText("未查询到符合条件的地点。");
});

it("aborts requests when the city workspace unmounts", () => {
  search.mockImplementation(() => new Promise(() => {}));
  const { unmount } = render(<PlacesPanel category="attractions" cityId="hangzhou" cityName="杭州" onSelect={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: /查询景点/ }));
  expect(search.mock.calls[0][1].city_id).toBe("hangzhou");
  const signal = search.mock.calls[0][2];
  unmount();
  expect(signal?.aborted).toBe(true);
});
