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
    booking_url: "https://www.fliggy.com/train?fixture=e2e",
    source_id: source[0].source_id,
    mode: "rail",
    travel_date: "2026-11-10",
    segments: [
      { segment_id: "rail-leg-1", origin_name: "测试站 A", destination_name: "测试站 B", service_number: "G-TEST-101", seat_class: "二等座" },
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
  platform_hint: "合成平台提示",
  message: "合成测试数据，不代表实时班次或票价。",
  coverage: null,
  error: null,
};

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

test("transport starts without a request and keeps synthetic rail details explicit", async ({ page }, testInfo) => {
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
  await expect(page.getByRole("button", { name: "市内路线" })).toHaveCount(0);
  const primaryFields = [
    page.getByLabel(/交通方式/),
    page.getByLabel(/目标出行日期/),
    page.getByLabel(/成人数量/),
    page.getByLabel(/^儿童人数/),
  ];
  const fieldHeights = await Promise.all(primaryFields.map(async (field) => (await field.boundingBox())?.height));
  expect(fieldHeights).toEqual([48, 48, 48, 48]);
  if (testInfo.project.name === "mobile-chromium") {
    await page.setViewportSize({ width: 375, height: 812 });
  }
  await expectNoHorizontalOverflow(page);
  await fillPlaces(page, "测试站 A", "测试站 C");
  await page.getByLabel(/交通方式/).selectOption("rail");
  await page.getByLabel(/目标出行日期/).fill("2026-11-10");
  await page.getByLabel(/成人数量/).fill("2");
  await page.getByRole("button", { name: "查询班次" }).click();
  await expect(page.getByRole("status")).toContainText("服务尚未配置");
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.getByText("测试 fixture")).toHaveCount(0);

  await page.getByRole("button", { name: "查询班次" }).click();

  await expect(page.getByText("测试数据", { exact: true })).toBeVisible();
  await expect(page.getByText("G-TEST-101")).toBeVisible();
  await expect(page.getByText(/G-TEST-202/)).toBeVisible();
  await expect(page.getByText(/换乘地点：测试站 B/)).toBeVisible();
  await page.locator(".transport-results .evidence-passport summary").first().click();
  await expect(page.getByText(/Transport E2E fixture/)).toBeVisible();
  await expect(page.locator(".transport-results").getByText(/票价|费用项目|余量未知|¥|平台提示/)).toHaveCount(0);
  await expect(page.getByText("席别：二等座")).toBeVisible();
  await expect(page.getByRole("link", { name: /详情|购票/ })).toHaveCount(0);
  expect(fareCalls).toBe(2);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("railway-results.png"), fullPage: true });
});

const flightFare = {
  state: "partial",
  items: [{
    offer_id: "flight-e2e-001",
    source_id: source[0].source_id,
    mode: "flight",
    travel_date: "2026-11-10",
    segments: [{
      segment_id: "flight-leg-1",
      origin_name: "SHA",
      destination_name: "HGH",
      departure_at: "2026-11-10T00:00:00Z",
      arrival_at: "2026-11-10T01:10:00Z",
      departure_timezone: "Asia/Shanghai",
      arrival_timezone: "Asia/Shanghai",
      service_number: "MU1234",
    }],
    service_number: "MU1234",
    origin_name: "上海虹桥",
    destination_name: "杭州萧山",
    departure_at: "2026-11-10T00:00:00Z",
    arrival_at: "2026-11-10T01:10:00Z",
    departure_timezone: "Asia/Shanghai",
    arrival_timezone: "Asia/Shanghai",
    price_fen: 35534,
    currency_code: "CNY",
    price_basis: "party_total",
    price_scope: "entire_journey",
    passenger_count: 2,
    included_charges: [],
    availability: "unknown",
    remaining_seats: 3,
    evidence_state: "unverified",
    missing_fields: ["included_charges", "availability"],
  }],
  sources: [{ ...source[0], evidence_state: "unverified" }],
  queried_at: "2026-10-28T02:00:00Z",
  request_id: "transport-flight-fixture",
  message: "合成测试航班，不代表锁价或锁位。",
  coverage: null,
  error: null,
};
test("flight query defaults to nearest airports and renders only schedule details", async ({ page }) => {
  let fareRequest: Record<string, unknown> | undefined;
  await page.route("**/api/transport/fares/search", async (route) => {
    fareRequest = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ status: 200, json: flightFare });
  });

  await enterTransport(page);
  await fillPlaces(page, "上海虹桥", "杭州萧山");
  await expect(page.getByLabel("起飞机场")).toHaveValue("SHA");
  await expect(page.getByLabel("到达机场")).toHaveValue("HGH");
  await expect(page.getByText(/最近机场 · 默认选择/).first()).toBeVisible();
  await page.getByLabel(/目标出行日期/).fill("2026-11-10");
  await page.getByLabel(/成人数量/).fill("2");
  await page.getByRole("button", { name: "查询班次" }).click();

  await expect(page.getByRole("heading", { name: /上海虹桥.*杭州萧山/ })).toBeVisible();
  const scheduleResults = page.getByLabel("班次结果");
  await expect(scheduleResults).toContainText("MU1234");
  await expect(scheduleResults).not.toContainText(/票价|费用项目|¥355\.34/);
  expect(fareRequest).toMatchObject({
    origin: { display_name: "上海虹桥", place_id: "SHA", coordinate_system: "WGS84" },
    destination: { display_name: "杭州萧山", place_id: "HGH", coordinate_system: "WGS84" },
    mode: "flight",
    travel_date: "2026-11-10",
    passenger_count: 2,
  });
  await expectNoHorizontalOverflow(page);
});
test("changing fare conditions clears prior data and a slow response cannot overwrite the new query", async ({ page }, testInfo) => {
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
  await page.getByLabel(/交通方式/).selectOption("rail");
  await page.getByLabel(/目标出行日期/).fill("2026-11-10");
  await page.getByLabel(/成人数量/).fill("2");
  await page.getByRole("button", { name: "查询班次" }).click();
  await started;

  await page.getByRole("textbox", { name: /目的地/ }).fill("新测试目的地");
  await expect(page.getByText("提交查询后显示班次与来源；未配置数据源时不会用测试结果或旧结果填补。")).toBeVisible();
  await page.getByRole("button", { name: "查询班次" }).click();
  await expect(page.getByRole("heading", { name: /测试站 A.*新测试目的地/ })).toBeVisible();

  releaseFirst?.();
  await expect(page.getByRole("heading", { name: /测试站 A.*新测试目的地/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /测试站 A.*测试站 C/ })).toHaveCount(0);
  expect(calls).toBe(2);
  if (testInfo.project.name === "mobile-chromium") {
    await page.setViewportSize({ width: 375, height: 812 });
  }
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 812, height: 375 });
  await expectNoHorizontalOverflow(page);
});
