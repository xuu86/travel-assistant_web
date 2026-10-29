import { expect, test } from "@playwright/test";

const source = {
  source_id: "weather.fixture.e2e",
  display_name: "天气查询",
  url: "https://weather.example/forecast",
  retrieved_at: "2026-10-29T00:00:00Z",
  valid_from: null,
  valid_to: null,
  attribution: "Synthetic fixture",
  evidence_state: "verified",
};

const success = {
  state: "live",
  request_id: "assistant-e2e-success",
  message: "",
  reply: "可以安排一段轻松的行程。<script>window.injected=true</script>",
  candidate_patch: { pace: "relaxed", travelers: 2 },
  sources: [source],
  error: null,
};

const unconfigured = {
  state: "unconfigured",
  request_id: "assistant-e2e-unconfigured",
  message: "AI 助手尚未配置。",
  reply: "",
  candidate_patch: null,
  sources: [],
  error: { code: "UNCONFIGURED", message: "AI 助手尚未配置。", retryable: false },
};

async function enterAssistant(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("hangzhou");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "AI 助手" }).click();
  await expect(page.getByRole("heading", { name: "AI 旅行助手" })).toBeVisible();
}

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const size = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(size.content).toBeLessThanOrEqual(size.viewport);
}

test("assistant displays unconfigured without automatic requests and preserves the prompt", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/assistant/chat", async (route) => {
    calls += 1;
    await route.fulfill({ status: 200, json: unconfigured });
  });
  await enterAssistant(page);
  expect(calls).toBe(0);
  await page.getByLabel("发送给 AI 助手").fill("你好");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText("AI 服务尚未配置，其他旅行工具仍可使用。")).toBeVisible();
  await expect(page.getByLabel("发送给 AI 助手")).toHaveValue("你好");
  expect(calls).toBe(1);
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoHorizontalOverflow(page);
});

test("context stays off by default, selected evidence is explicit, and patches remain previews", async ({ page }) => {
  const requests: unknown[] = [];
  await page.route("**/api/weather/forecast", async (route) => {
    const weather = {
      state: "live",
      items: [{
        date: "2026-11-01", weather_code: 1, temperature_max_c: 20,
        temperature_min_c: 12, precipitation_probability_max_pct: 0,
        precipitation_sum_mm: 0, wind_speed_10m_max_kmh: 5, missing_fields: [],
      }],
      sources: [{ ...source, source_id: "weather.fixture.local", evidence_state: "verified" }],
      queried_at: "2026-10-29T00:00:00Z", request_id: "weather-e2e",
      message: "", coverage: { requested: { start: "2026-11-01", end: "2026-11-01" }, covered: [], missing: [] },
      location: { city_id: "hangzhou", requested_latitude: 30.2, requested_longitude: 120.1, coordinate_system: "WGS84", resolved_latitude: null, resolved_longitude: null, elevation_m: null },
    };
    await route.fulfill({ status: 200, json: weather });
  });
  await page.route("**/api/assistant/chat", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, json: success });
  });
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("hangzhou");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByLabel("开始日期").fill("2026-11-01");
  await page.getByLabel("结束日期").fill("2026-11-01");
  await page.getByRole("button", { name: "查询天气" }).click();
  await expect(page.getByText("预报数据已就绪")).toBeVisible();
  await page.getByRole("button", { name: "AI 助手" }).click();
  await expect(page.getByRole("checkbox", { name: /天气查询/ })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /将当前行程条件用于本次回答/ })).not.toBeChecked();
  await page.getByRole("checkbox", { name: /天气查询/ }).check();
  await page.getByLabel("发送给 AI 助手").fill("按当前信息帮我安排");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByRole("heading", { name: "待确认的条件建议" })).toBeVisible();
  const body = requests[0] as { include_trip_context: boolean; trip_context?: unknown; evidence?: unknown[] };
  expect(body.include_trip_context).toBe(false);
  expect(body.trip_context).toBeUndefined();
  expect(body.evidence).toHaveLength(1);
  expect((body.evidence[0] as { source: { evidence_state: string } }).source.evidence_state).toBe("user_provided");
  await expect(page.getByRole("button", { name: /应用/ })).toHaveCount(0);
  expect(await page.evaluate(() => (window as Window & { injected?: boolean }).injected)).toBeUndefined();
  await expect(page.getByText("天气查询 · 用户提供，未核实")).toBeVisible();
  await expect(page.getByRole("link", { name: "天气查询" })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectNoHorizontalOverflow(page);
});

test("trip context is sent only after explicit opt-in for that turn", async ({ page }) => {
  let body: Record<string, unknown> | undefined;
  await page.route("**/api/assistant/chat", async (route) => {
    body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ status: 200, json: success });
  });
  await enterAssistant(page);
  await page.getByRole("checkbox", { name: /将当前行程条件用于本次回答/ }).check();
  await page.getByLabel("发送给 AI 助手").fill("推荐安排");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText("可以安排一段轻松的行程。<script>window.injected=true</script>")).toBeVisible();
  expect(body?.include_trip_context).toBe(true);
  expect(body?.trip_context).toMatchObject({ destination: "杭州" });
  expect((body?.trip_context as { start_date?: string }).start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect((body?.trip_context as { end_date?: string }).end_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test("provider failures require an explicit user retry and 429 does not retry automatically", async ({ page }) => {
  let calls = 0;
  let mode: "unavailable" | "limited" = "unavailable";
  await page.route("**/api/assistant/chat", async (route) => {
    calls += 1;
    if (mode === "limited") {
      await route.fulfill({
        status: 429,
        json: { code: "RATE_LIMITED", message: "AI 助手暂受额度限制。", retryable: true, request_id: "rate-limit" },
      });
      return;
    }
    await route.fulfill({
      status: 503,
      json: { code: "PROVIDER_UNAVAILABLE", message: "AI 助手暂不可用。", retryable: true, request_id: `r-${calls}` },
    });
  });
  await enterAssistant(page);
  await page.getByLabel("发送给 AI 助手").fill("请建议行程");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByRole("alert")).toContainText("暂不可用");
  expect(calls).toBe(1);

  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByRole("alert")).toContainText("暂不可用");
  expect(calls).toBe(2);

  mode = "limited";
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByRole("alert")).toContainText("额度限制");
  expect(calls).toBe(3);
});

test("changing destination clears the assistant conversation", async ({ page }) => {
  await page.route("**/api/assistant/chat", async (route) => route.fulfill({ status: 200, json: success }));
  await enterAssistant(page);
  await page.getByLabel("发送给 AI 助手").fill("初始问题");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText("可以安排一段轻松的行程。<script>window.injected=true</script>")).toBeVisible();
  await page.getByRole("button", { name: "更换目的地" }).click();
  await page.getByRole("combobox", { name: "新目的城市" }).selectOption("suzhou");
  await page.getByRole("button", { name: "确认更换" }).click();
  await page.getByRole("button", { name: "AI 助手" }).click();
  await expect(page.getByRole("heading", { name: "今天想怎么规划？" })).toBeVisible();
  await expect(page.getByText("初始问题")).toHaveCount(0);
});
