import { expect, test } from "@playwright/test";

const cities = [
  ["shanghai", "上海"], ["suzhou", "苏州"], ["wuxi", "无锡"], ["jiaxing", "嘉兴"], ["hangzhou", "杭州"],
] as const;

test("destination setup gates tools, preserves drafts, confirms reset, and resets on reload", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const moduleCalls: string[] = [];
  await page.route("**/api/**", async (route) => {
    moduleCalls.push(route.request().url());
    await route.fulfill({ status: 503, json: { code: "PROVIDER_UNAVAILABLE", message: "未配置", retryable: true } });
  });
  await page.goto("/");
  await expect(page.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
  await expect(page.getByRole("navigation", { name: "旅行工具" })).toHaveCount(0);
  for (const [id, name] of cities) {
    await page.getByRole("combobox", { name: "目的城市" }).selectOption(id);
    await expect(page.getByRole("combobox", { name: "目的城市" })).toHaveValue(id);
    expect(name).not.toBe("");
  }
  expect(moduleCalls).toEqual([]);

  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.locator(".workspace-destination")).toHaveText("杭州");
  await page.getByRole("button", { name: "预算" }).click();
  await expect(page.locator(".budget-destination")).toHaveText("目的地：杭州");
  await page.getByLabel("整趟总预算（元）").fill("6000");
  await page.getByRole("button", { name: "交通" }).click();
  await expect(page.getByRole("textbox", { name: /起点/ })).toHaveValue("当前位置");
  await expect(page.getByRole("textbox", { name: /目的地/ })).toHaveValue("杭州");
  await page.getByRole("button", { name: "预算" }).click();
  await expect(page.getByLabel("整趟总预算（元）")).toHaveValue("6000");

  await page.getByRole("button", { name: "更换目的地" }).click();
  await page.getByLabel("新目的城市").selectOption("suzhou");
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.locator(".workspace-destination")).toHaveText("杭州");
  await expect(page.getByLabel("整趟总预算（元）")).toHaveValue("6000");

  await page.getByRole("button", { name: "更换目的地" }).click();
  await page.getByLabel("新目的城市").selectOption("suzhou");
  await page.getByRole("button", { name: "确认更换" }).click();
  await expect(page.locator(".workspace-destination")).toHaveText("苏州");
  await expect(page.getByRole("heading", { name: "从一座城市，开始规划一段旅程。" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "先选好目的地与出发地" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
  await expect(page.getByRole("navigation", { name: "旅行工具" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
});
