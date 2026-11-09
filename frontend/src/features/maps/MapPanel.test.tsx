import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import { MapPanel } from "./MapPanel";
import { fetchStaticMap } from "../places/api";

vi.mock("../places/api", () => ({ fetchStaticMap: vi.fn(), searchPlaces: vi.fn() }));
const fetchMap = vi.mocked(fetchStaticMap);
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.resetAllMocks(); });

it("loads the selected GCJ02 point, revokes old image URLs on zoom, and can return to the city", async () => {
  fetchMap.mockResolvedValue(new Blob(["image"], { type: "image/png" }));
  const createUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test-map");
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const onSelect = vi.fn();
  const point = { id: "B001", source_id: "amap.place" as const, name: "公园", location: { longitude: 121.47, latitude: 31.23, coordinate_system: "GCJ02" as const } };
  const { unmount } = render(<MapPanel cityId="shanghai" cityName="上海" selectedPlace={point} onSelect={onSelect} />);
  await screen.findByRole("img", { name: /公园的高德地图位置/ });
  expect(fetchMap).toHaveBeenCalledWith({ city_id: "shanghai", location: point.location, zoom: 13 }, expect.any(AbortSignal));
  const signal = fetchMap.mock.calls[0][1];
  fireEvent.click(screen.getByRole("button", { name: "放大地图" }));
  await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(2));
  expect(signal?.aborted).toBe(true);
  expect(revoke).toHaveBeenCalledWith("blob:test-map");
  expect(fetchMap.mock.calls[1][0].zoom).toBe(14);
  fireEvent.click(screen.getByRole("button", { name: "城市中心" }));
  expect(onSelect).toHaveBeenCalledWith(null);
  unmount();
});

it("shows a map error and retries without creating a broken image", async () => {
  fetchMap.mockRejectedValueOnce(new Error("地图服务暂不可用。")).mockRejectedValueOnce(new Error("稍后再试。"));
  render(<MapPanel cityId="shanghai" cityName="上海" selectedPlace={null} onSelect={vi.fn()} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("地图服务暂不可用。");
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("稍后再试。");
});
