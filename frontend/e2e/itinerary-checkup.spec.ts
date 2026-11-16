import { expect, test } from "@playwright/test";

test.use({ trace: "off", screenshot: "off", video: "off" });

test("checkup explains missing data and source navigation does not change locked plans", async ({ page }) => {
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({
    json: { identity_type: "guest", owner_id: null, display_name: null },
  }));
  await page.route("**/api/**", async (route) => {
    if (route.request().url().includes("/api/v1/auth/")) return route.fallback();
    await route.fulfill({ status: 503, json: { code: "UNCONFIGURED", message: "fixture", retryable: false } });
  });
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "行程", exact: true }).click();
  await page.getByLabel("安排名称").fill("锁定的博物馆行程");
  await page.getByRole("button", { name: "添加到行程" }).click();
  await page.getByRole("button", { name: "锁定", exact: true }).click();
  await page.getByRole("button", { name: "查看行程体检" }).click();

  await expect(page.getByRole("heading", { name: "行程体检" })).toBeVisible();
  await expect(page.getByText("综合分：数据不足")).toBeVisible();
  await expect(page.getByText("数据不足").first()).toBeVisible();
  await expect(page.getByText(/只读分析/)).toBeVisible();
  const item = page.getByRole("article").filter({ hasText: "锁定的博物馆行程" });
  await expect(item).toContainText("已锁定");

  const sourceSuggestion = page.locator(".itinerary-checkup__suggestions li").filter({ hasText: "行程安排内容待核实" });
  await expect(sourceSuggestion).toBeVisible();
  await sourceSuggestion.getByRole("button", { name: "查看来源" }).click();
  await expect(item).toBeFocused();
  await expect(item).toContainText("已锁定");
  await expect(page.getByRole("heading", { name: "锁定的博物馆行程" })).toBeVisible();

  if (page.viewportSize()?.width === 375) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  }
});
