import { expect, test } from "@playwright/test";

const completeSummary = {
  trip_id: "current-trip",
  total_budget_fen: 300000,
  paid_total_fen: 100000,
  known_unpaid_total_fen: 150000,
  remaining_to_allocate_fen: 200000,
  expected_balance_fen: 50000,
  minimum_over_budget_fen: null,
  budget_state: "within_budget",
  completeness: "complete",
  reserve_fen: null,
  reserve_reminder: true,
  request_id: "budget-e2e-request",
};

async function enterWorkspace(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();
}

test("budget workflow reports reserve reminder and quote source accurately", async ({ page }) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/api/budget/calculate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ status: 200, json: completeSummary });
  });

  await enterWorkspace(page);
  await page.getByRole("button", { name: "预算" }).click();
  await expect(page.getByRole("heading", { name: "旅行预算" })).toBeVisible();
  await page.getByRole("textbox", { name: "整趟总预算（元）" }).fill("3000");
  await page.getByRole("combobox", { name: "类别" }).selectOption("住宿");
  await page.getByRole("checkbox", { name: "这是我补填的未报价费用" }).check();
  await page.getByRole("textbox", { name: "费用项 1 已支付（元）" }).fill("1000");
  await page.getByRole("textbox", { name: "费用项 1 预计待支付（元）" }).fill("1500");
  await page.getByRole("button", { name: "计算预算" }).click();

  await expect(page.getByRole("status")).toHaveText("预计在预算内");
  await expect(page.locator(".budget-source-warning")).toContainText("用户填写，非平台报价");
  await expect(page.locator(".budget-reminder")).toContainText("尚未设置预留金");
  expect(requestBody?.total_budget_fen).toBe(300000);
  expect((requestBody?.cost_items as Array<Record<string, unknown>>)[0]).toMatchObject({
    paid_fen: 100000,
    unpaid_estimate_fen: 150000,
    evidence_state: "user_provided",
  });
});

test("budget form remains within a 375px viewport and supports keyboard use", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await enterWorkspace(page);
  await page.getByRole("button", { name: "预算" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "旅行预算" })).toBeVisible();

  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  await expect(page.getByRole("textbox", { name: "整趟总预算（元）" })).toBeVisible();
  await expect(page.getByRole("button", { name: "计算预算" })).toBeVisible();
});

test("shows a minimum known overspend without hiding missing costs", async ({ page }) => {
  await page.route("**/api/budget/calculate", async (route) => {
    await route.fulfill({
      status: 200,
      json: {
        ...completeSummary,
        paid_total_fen: null,
        known_unpaid_total_fen: 350000,
        remaining_to_allocate_fen: null,
        expected_balance_fen: null,
        minimum_over_budget_fen: 50000,
        budget_state: "over_budget",
        completeness: "needs_review",
        reserve_reminder: false,
      },
    });
  });

  await enterWorkspace(page);
  await page.getByRole("button", { name: "预算" }).click();
  await page.getByRole("textbox", { name: "整趟总预算（元）" }).fill("3000");
  await page.getByRole("textbox", { name: "费用项 1 已支付（元）" }).fill("3500");
  await page.getByRole("button", { name: "计算预算" }).click();

  await expect(page.getByRole("status")).toHaveText("已知费用至少超出");
  await expect(page.getByRole("alert")).toContainText("至少超出");
  await expect(page.getByText(/已知小计不代表最终支出/)).toBeVisible();
});
