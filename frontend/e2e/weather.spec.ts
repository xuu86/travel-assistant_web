import { expect, test, type Page } from "@playwright/test";

const source = [{
  source_id: "fixture.weather", display_name: "Weather fixture", url: "https://fixture.example/weather",
  retrieved_at: "2026-10-27T00:00:00Z", valid_from: null, valid_to: null,
  attribution: "Fixture only", evidence_state: "demo",
}];
const item = {
  date: "2026-10-27", weather_code: 0, temperature_max_c: 20, temperature_min_c: 13,
  precipitation_probability_max_pct: 0, precipitation_sum_mm: 0, wind_speed_10m_max_kmh: 5, missing_fields: [],
};
const base = {
  state: "demo", items: [item], sources: source, queried_at: "2026-10-27T00:00:00Z",
  request_id: "weather-e2e", message: "天气数据来自测试 fixture。", error: null,
  location: {
    city_id: "shanghai", requested_latitude: 31.222222, requested_longitude: 121.458056,
    coordinate_system: "WGS84", resolved_latitude: null, resolved_longitude: null, elevation_m: null,
  },
};
const fullFixture = {
  ...base,
  items: [item, { ...item, date: "2026-10-28", weather_code: 2 }],
  coverage: {
    requested: { start: "2026-10-27", end: "2026-10-28" },
    covered: [{ start: "2026-10-27", end: "2026-10-28" }], missing: [],
  },
};
const partialFixture = {
  ...base,
  coverage: {
    requested: { start: "2026-10-27", end: "2026-10-29" },
    covered: [{ start: "2026-10-27", end: "2026-10-27" }],
    missing: [{ start: "2026-10-28", end: "2026-10-29" }],
  },
};

async function setQuery(page: Page, endDate = "2026-10-28") {
  await page.getByLabel("开始日期").fill("2026-10-27");
  await page.getByLabel("结束日期").fill(endDate);
}

async function enterWorkspace(page: Page, city = "shanghai") {
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption(city);
  await page.getByRole("button", { name: "开始规划" }).click();
}

async function assertNoHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
}

test("full forecast fixture is labeled and responsive", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/weather/forecast", async (route) => {
    calls += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fullFixture) });
  });

  await page.clock.install({ time: new Date("2026-10-27T12:00:00+08:00") });
  await enterWorkspace(page);
  await expect(page).toHaveTitle("行旅 · 智能旅游助手");
  await expect(page.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();
  await expect(page.locator(".weather-panel__state")).toContainText("天气服务尚未配置");
  await expect(page.locator(".workspace-destination")).toHaveText("上海");
  await expect(page.getByRole("button", { name: "查询天气" })).toBeVisible();
  expect(calls).toBe(0);

  await setQuery(page);
  await page.getByRole("button", { name: "查询天气" }).click();
  await expect(page.locator(".weather-panel__state")).toContainText("测试数据已载入");
  await expect(page.getByRole("article")).toHaveCount(2);
  await expect(page.getByText(/测试 fixture/)).toBeVisible();
  expect(calls).toBe(1);
  await assertNoHorizontalOverflow(page);
});

test("partial coverage shows missing dates and does not keep stale results", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/weather/forecast", async (route) => {
    calls += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(partialFixture) });
  });

  await page.clock.install({ time: new Date("2026-10-27T12:00:00+08:00") });
  await enterWorkspace(page);
  await setQuery(page, "2026-10-29");
  await page.getByRole("button", { name: "查询天气" }).click();
  await expect(page.locator(".weather-panel__state")).toContainText("测试数据 · 部分日期已覆盖");
  await expect(page.getByText(/以下日期暂无预报：10月28日/)).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(1);
  await expect(page.getByText(/测试 fixture/)).toBeVisible();
  expect(calls).toBe(1);
  await assertNoHorizontalOverflow(page);

  await page.getByLabel("结束日期").fill("2026-10-30");
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.locator(".weather-panel__state")).toContainText("尚未查询天气");
});

test("unconfigured and failure states never create demo or stale weather", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/weather/forecast", async (route) => {
    calls += 1;
    await route.fulfill({
      status: 503, contentType: "application/json", headers: { "x-request-id": "weather-e2e-failure" },
      body: JSON.stringify({
        code: "PROVIDER_UNAVAILABLE", message: "天气服务暂不可用。", retryable: true,
        request_id: "weather-e2e-failure",
      }),
    });
  });

  await page.clock.install({ time: new Date("2026-10-27T12:00:00+08:00") });
  await enterWorkspace(page);
  await expect(page.locator(".weather-panel__state")).toContainText("天气服务尚未配置");
  await expect(page.getByRole("article")).toHaveCount(0);
  expect(calls).toBe(0);
  await assertNoHorizontalOverflow(page);

  await setQuery(page);
  await page.getByRole("button", { name: "查询天气" }).click();
  await expect(page.locator(".weather-panel__state")).toContainText("天气服务暂不可用。");
  await expect(page.getByRole("alert")).toContainText("天气服务暂不可用。");
  await expect(page.getByText("请求编号：weather-e2e-failure")).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  expect(calls).toBe(1);
  await assertNoHorizontalOverflow(page);
});




test("375px portrait, landscape, and reduced motion remain usable", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-10-27T12:00:00+08:00") });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 375, height: 812 });

  let releaseResponse: (() => void) | undefined;
  const waitingForRelease = new Promise<void>((resolve) => { releaseResponse = resolve; });
  await page.route("**/api/weather/forecast", async (route) => {
    await waitingForRelease;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ code: "PROVIDER_UNAVAILABLE", message: "天气服务暂不可用。", retryable: true }),
    });
  });

  await enterWorkspace(page);
  await expect(page.getByRole("heading", { name: "查询一段天气" })).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await setQuery(page);
  await page.getByRole("button", { name: "查询天气" }).click();
  await expect(page.locator(".weather-panel__state")).toContainText("正在读取天气预报");
  await expect(page.locator(".weather-panel__loading-bar")).toHaveCSS("animation-name", "none");

  await page.setViewportSize({ width: 812, height: 375 });
  await assertNoHorizontalOverflow(page);
  releaseResponse?.();
  await expect(page.locator(".weather-panel__state")).toContainText("天气服务暂不可用。");
});
