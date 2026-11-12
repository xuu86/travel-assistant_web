import { expect, test, type Page } from "@playwright/test";

const point = {
  id: "B001", name: "合成测试地点", address: "上海市测试路", source_id: "amap.place",
  location: { longitude: 121.47, latitude: 31.23, coordinate_system: "GCJ02" },
};
const image = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");

async function enter(page: Page) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/weather/forecast", (route) => route.fulfill({
    status: 503, json: { code: "UNCONFIGURED", message: "天气测试不联网", retryable: false },
  }));
});

test("four place entries, POI-to-map selection, zoom, and destination reset", async ({ page }) => {
  const requests: { category: string; city_id: string; page: number }[] = [];
  await page.route(/\/api\/(hotels|activities|attractions|maps)\/search$/, async (route) => {
    const query = route.request().postDataJSON() as { city_id: string; page: number };
    const category = route.request().url().split("/").at(-2)!;
    requests.push({ category, ...query });
    await route.fulfill({ json: {
      state: "live", ...query, category, has_more: false,
      items: [point, { ...point, id: "B002", name: "无坐标测试地点", location: null }],
      sources: [{ display_name: "合成地点测试数据" }], queried_at: "2026-11-04T10:00:00Z",
      request_id: "amap-fixture", message: "合成测试数据，仅用于自动化。",
    } });
  });
  const maps: { city_id: string; zoom: number; location: unknown }[] = [];
  await page.route("**/api/maps/static", async (route) => {
    maps.push(route.request().postDataJSON());
    await route.fulfill({ contentType: "image/png", body: image });
  });
  await enter(page);
  expect(maps).toHaveLength(0);
  const nav = page.getByRole("navigation", { name: "旅行工具" });
  for (const [label, button, category] of [
    ["酒店", "查询酒店", "hotels"], ["活动", "查询活动场馆", "activities"], ["景点", "查询景点", "attractions"],
  ]) {
    await nav.getByRole("button", { name: label, exact: true }).click();
    await page.getByRole("button", { name: button }).click();
    await expect(page.getByRole("heading", { name: point.name })).toBeVisible();
    expect(requests.at(-1)).toMatchObject({ category, city_id: "shanghai", page: 1 });
    await expect(page.getByRole("button", { name: "在地图查看无坐标测试地点" })).toBeDisabled();
  }
  await page.getByRole("button", { name: `在地图查看${point.name}`, exact: true }).click();
  await expect(nav.getByRole("button", { name: "地图", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: /合成测试地点的高德地图位置/ })).toBeVisible();
  expect(maps.at(-1)?.location).toEqual(point.location);
  await page.getByRole("button", { name: "放大地图" }).click();
  await expect.poll(() => maps.at(-1)?.zoom).toBe(14);
  await page.getByRole("button", { name: "搜索地点", exact: true }).click();
  await expect.poll(() => requests.at(-1)?.category).toBe("maps");

  await page.getByRole("button", { name: "更换目的地" }).click();
  await page.getByLabel("新目的城市").selectOption("hangzhou");
  await page.getByRole("button", { name: "确认更换" }).click();
  await nav.getByRole("button", { name: "酒店", exact: true }).click();
  await expect(page.getByLabel("酒店关键词")).toHaveValue("");
  await expect(page.getByRole("heading", { name: point.name })).toHaveCount(0);
  await nav.getByRole("button", { name: "地图", exact: true }).click();
  await expect(page.getByRole("img", { name: /杭州的高德地图位置/ })).toBeVisible();
  expect(maps.at(-1)).toMatchObject({ city_id: "hangzhou", location: null });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test("quota failures stay visible and the map can retry", async ({ page }) => {
  await page.route("**/api/hotels/search", (route) => route.fulfill({ json: {
    state: "rate_limited", city_id: "shanghai", category: "hotels", page: 1, has_more: false,
    items: [], sources: [], queried_at: "2026-11-04T10:00:00Z", request_id: "quota",
    message: "高德服务额度已用尽，请稍后重试。",
  } }));
  let allowMapRetry = false;
  await page.route("**/api/maps/static", async (route) => {
    if (!allowMapRetry) await route.fulfill({ status: 429, json: { message: "地图服务请求过于频繁。" } });
    else await route.fulfill({ contentType: "image/png", body: image });
  });
  await enter(page);
  await page.getByRole("button", { name: "酒店", exact: true }).click();
  await page.getByRole("button", { name: "查询酒店" }).click();
  await expect(page.getByText("高德服务额度已用尽，请稍后重试。")).toBeVisible();
  await page.getByRole("button", { name: "地图", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("地图服务请求过于频繁。");
  allowMapRetry = true;
  await page.getByRole("button", { name: "重新加载" }).click();
  await expect(page.getByRole("img", { name: /上海的高德地图位置/ })).toBeVisible();
});
