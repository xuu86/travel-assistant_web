import { expect, test } from "@playwright/test";

const source = [{
  source_id: "fixture.transport.e2e",
  display_name: "Transport E2E fixture",
  retrieved_at: "2026-10-28T02:00:00Z",
  attribution: "Synthetic test data only",
  evidence_state: "demo",
}];

const unconfigured = {
  state: "unconfigured",
  items: [],
  sources: [],
  queried_at: "2026-10-28T02:00:00Z",
  request_id: "transport-unconfigured",
  message: "交通查询尚未配置。",
  coverage: null,
  error: null,
};

const railFare = {
  state: "demo",
  items: [{
    offer_id: "rail-e2e-001",
    source_id: source[0].source_id,
    mode: "rail",
    travel_date: "2026-11-10",
    segments: [
      { segment_id: "rail-leg-1", origin_name: "测试站 A", destination_name: "测试站 B", service_number: "G-TEST-101" },
      { segment_id: "rail-leg-2", origin_name: "测试站 B", destination_name: "测试站 C", service_number: "G-TEST-202", transfer_place: "测试站 B" },
    ],
    service_number: null,
    origin_name: "测试站 A",
    destination_name: "测试站 C",
    price_fen: null,
    currency_code: "CNY",
    price_basis: "unknown",
    price_scope: "entire_journey",
    passenger_count: 2,
    included_charges: [],
    availability: "unknown",
    remaining_seats: null,
    evidence_state: "demo",
    missing_fields: ["price_fen", "remaining_seats", "availability"],
  }],
  sources: source,
  queried_at: "2026-10-28T02:00:00Z",
  request_id: "transport-fare-fixture",
  message: "合成测试数据，不代表实时班次或票价。",
  coverage: null,
  error: null,
};

function routeResult(mode: "transit" | "walking" | "taxi") {
  const taxi = mode === "taxi";
  return {
    state: "demo",
    items: [{
      route_id: `${mode}-e2e-route`,
      source_id: source[0].source_id,
      mode,
      origin_name: "测试地点 A",
      destination_name: "测试地点 B",
      distance_m: taxi ? null : 1250,
      duration_seconds: taxi ? null : 900,
      duration_basis: taxi ? "unknown" : "typical_estimate",
      steps: [],
      geometry_points: null,
      fare_amount_fen: taxi ? 3500 : null,
      currency_code: "CNY",
      fare_basis: taxi ? "meter_estimate" : "unknown",
      fare_evidence_state: taxi ? "estimate" : "unknown",
      evidence_state: "demo",
      missing_fields: ["geometry_points"],
    }],
    sources: source,
    queried_at: "2026-10-28T02:00:00Z",
    request_id: `${mode}-e2e-request`,
    message: "合成测试路线，不代表真实导航。",
    coverage: null,
    error: null,
  };
}

async function enterTransport(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("hangzhou");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "交通" }).click();
  await expect(page.getByRole("heading", { name: "交通查询" })).toBeVisible();
}

async function fillPlaces(page: import("@playwright/test").Page, origin = "测试地点 A", destination = "测试地点 B") {
  await page.getByRole("textbox", { name: /起点/ }).fill(origin);
  await page.getByRole("textbox", { name: /目的地/ }).fill(destination);
}

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const size = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(size.content).toBeLessThanOrEqual(size.viewport);
}

test("transport starts without a request and keeps synthetic rail details explicit", async ({ page }) => {
  let fareCalls = 0;
  await page.route("**/api/transport/fares/search", async (route) => {
    fareCalls += 1;
    const request = route.request().postDataJSON() as { mode: string; travel_date: string };
    expect(request.mode).toBe("rail");
    expect(request.travel_date).toBe("2026-11-10");
    if (fareCalls === 1) {
      await route.fulfill({ status: 200, json: unconfigured });
      return;
    }
    await route.fulfill({ status: 200, json: railFare });
  });

  await enterTransport(page);
  expect(fareCalls).toBe(0);
  await expect(page.getByText("交通服务尚未配置", { exact: true })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoHorizontalOverflow(page);
  await fillPlaces(page, "测试站 A", "测试站 C");
  await page.getByLabel(/交通方式/).selectOption("rail");
  await page.getByLabel(/目标出行日期/).fill("2026-11-10");
  await page.getByLabel(/乘客人数/).fill("2");
  await page.getByRole("button", { name: "查询班次" }).click();
  await expect(page.getByRole("status")).toContainText("服务尚未配置");
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByText("测试 fixture")).toHaveCount(0);

  await page.getByRole("button", { name: "查询班次" }).click();

  await expect(page.getByText("测试数据", { exact: true })).toBeVisible();
  await expect(page.getByText("G-TEST-101")).toBeVisible();
  await expect(page.getByText(/G-TEST-202/)).toBeVisible();
  await expect(page.getByText(/换乘地点：测试站 B/)).toBeVisible();
  await expect(page.getByText("金额待核实")).toBeVisible();
  await expect(page.getByText("余量未知")).toBeVisible();
  await expect(page.getByText(/Transport E2E fixture/)).toBeVisible();
  await expect(page.getByText("¥0.00")).toHaveCount(0);
  expect(fareCalls).toBe(2);
  await expectNoHorizontalOverflow(page);
});

test("route modes keep separate success, failure, and taxi estimate states", async ({ page }) => {
  const calls: string[] = [];
  await page.route("**/api/transport/routes/search", async (route) => {
    const request = route.request().postDataJSON() as { mode: "transit" | "walking" | "taxi" };
    calls.push(request.mode);
    if (request.mode === "walking") {
      await route.fulfill({
        status: 503,
        json: { code: "PROVIDER_UNAVAILABLE", message: "步行服务暂不可用。", retryable: true, request_id: "walking-e2e-error" },
      });
      return;
    }
    await route.fulfill({ status: 200, json: routeResult(request.mode) });
  });

  await enterTransport(page);
  await fillPlaces(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "市内路线" }).click();
  await page.getByRole("button", { name: "查询公交 / 地铁路线" }).click();
  await expect(page.getByRole("region", { name: "公交 / 地铁查询结果" })).toContainText("未提供地图线路，不绘制直线或估算路径。");

  await page.getByRole("button", { name: "查询步行路线" }).click();
  await expect(page.getByRole("region", { name: "步行查询结果" })).toContainText("步行服务暂不可用。");

  await page.getByRole("button", { name: "查询出租车 / 驾车路线" }).click();
  const taxi = page.getByRole("region", { name: "出租车 / 驾车查询结果" });
  await expect(taxi).toContainText("¥35.00");
  await expect(taxi).toContainText("计价估算");
  await expect(page.getByRole("region", { name: "公交 / 地铁查询结果" })).toContainText("未提供地图线路，不绘制直线或估算路径。");
  await expect(page.getByRole("region", { name: "步行查询结果" })).toContainText("步行服务暂不可用。");
  expect(calls).toEqual(["transit", "walking", "taxi"]);
  await expectNoHorizontalOverflow(page);
});

test("changing fare conditions clears prior data and a slow response cannot overwrite the new query", async ({ page }) => {
  let firstRequestStarted: (() => void) | undefined;
  const started = new Promise<void>((resolve) => { firstRequestStarted = resolve; });
  let releaseFirst: (() => void) | undefined;
  const blocked = new Promise<void>((resolve) => { releaseFirst = resolve; });
  let calls = 0;
  await page.route("**/api/transport/fares/search", async (route) => {
    calls += 1;
    if (calls === 1) {
      firstRequestStarted?.();
      await blocked;
      await route.fulfill({ status: 200, json: railFare });
      return;
    }
    await route.fulfill({
      status: 200,
      json: {
        ...railFare,
        items: railFare.items.map((item) => ({ ...item, offer_id: "new-fare", destination_name: "新测试目的地" })),
        request_id: "transport-new-query",
      },
    });
  });

  await enterTransport(page);
  await fillPlaces(page);
  await page.getByLabel(/目标出行日期/).fill("2026-11-10");
  await page.getByLabel(/乘客人数/).fill("2");
  await page.getByRole("button", { name: "查询班次" }).click();
  await started;

  await page.getByRole("textbox", { name: /目的地/ }).fill("新测试目的地");
  await expect(page.getByText("提交查询后显示来源与结果；未配置数据源时不会用测试路线或旧结果填补。")).toBeVisible();
  await page.getByRole("button", { name: "查询班次" }).click();
  await expect(page.getByRole("heading", { name: /测试站 A.*新测试目的地/ })).toBeVisible();

  releaseFirst?.();
  await expect(page.getByRole("heading", { name: /测试站 A.*新测试目的地/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /测试站 A.*测试站 C/ })).toHaveCount(0);
  expect(calls).toBe(2);
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 812, height: 375 });
  await expectNoHorizontalOverflow(page);
});
