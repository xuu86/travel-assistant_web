import { expect, test } from "@playwright/test";

test("planning, budget and itinerary work without secure-context randomUUID", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, "randomUUID", { configurable: true, value: undefined });
  });
  await page.route("**/api/**", (route) => route.fulfill({
    status: 503, json: { code: "PROVIDER_UNAVAILABLE", message: "未配置", retryable: true },
  }));
  await page.goto("/");
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe("undefined");
  await page.getByRole("combobox", { name: "目的城市", exact: true }).selectOption("hangzhou");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByRole("navigation", { name: "旅行工具" })).toBeVisible();
  await expect(page.locator(".workspace-destination")).toHaveText("杭州");

  await page.getByRole("button", { name: "预算", exact: true }).click();
  await page.getByRole("button", { name: "添加费用" }).click();
  await expect(page.getByRole("textbox", { name: "费用项 2 已支付（元）" })).toBeVisible();
  await page.getByRole("button", { name: "删除费用项 1", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "类别", exact: true })).toHaveCount(1);

  await page.getByRole("button", { name: "行程", exact: true }).click();
  await page.getByLabel("安排名称").fill("外滩散步");
  await page.getByRole("button", { name: "添加到行程" }).click();
  await page.getByLabel("安排名称").fill("西湖散步");
  await page.getByRole("button", { name: "添加到行程" }).click();
  await expect(page.getByRole("heading", { name: "外滩散步", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "西湖散步", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
