import { expect, test } from "@playwright/test";

test("starts at destination setup without loading tools and fits the viewport", async ({ page }) => {
  await page.clock.install({ time: new Date("2026-10-27T12:00:00+08:00") });
  await page.goto("/");

  await expect(page).toHaveTitle("行旅 · 智能旅游助手");
  await expect(page.getByRole("heading", { name: "先选好目的地与出发地" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "目的城市" })).toHaveValue("");
  await expect(page.getByRole("navigation", { name: "旅行工具" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "开始规划" })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});


