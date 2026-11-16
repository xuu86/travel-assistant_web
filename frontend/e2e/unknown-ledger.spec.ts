import { expect, test, type Page } from "@playwright/test";

test.use({ trace: "off", screenshot: "off", video: "off" });

async function stubAuth(page: Page) {
  let owner: string | null = null;
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({
    json: owner
      ? { identity_type: "account", owner_id: owner, display_name: owner }
      : { identity_type: "guest", owner_id: null, display_name: null },
  }));
  await page.route("**/api/v1/auth/login", async (route) => {
    const body = route.request().postDataJSON() as { username: string; password: string };
    if (body.password !== "fixture-password" || !["alpha", "beta"].includes(body.username)) {
      await route.fulfill({ status: 401, json: { code: "UNAUTHORIZED", message: "用户名或密码不正确。", retryable: false } });
      return;
    }
    owner = body.username === "alpha" ? "owner-a" : "owner-b";
    await route.fulfill({
      status: 200,
      headers: { "set-cookie": `travel_session=${owner}; HttpOnly; Path=/; SameSite=Lax` },
      json: { identity_type: "account", owner_id: owner, display_name: owner },
    });
  });
  await page.route("**/api/v1/auth/logout", async (route) => {
    owner = null;
    await route.fulfill({ status: 204, headers: { "set-cookie": "travel_session=; Max-Age=0; HttpOnly; Path=/; SameSite=Lax" } });
  });
  await page.route("**/api/**", async (route) => {
    if (route.request().url().includes("/api/v1/auth/")) return route.fallback();
    await route.fulfill({ status: 503, json: { code: "UNCONFIGURED", message: "未配置", retryable: false } });
  });
}

async function signIn(page: Page, username: "alpha" | "beta") {
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill("fixture-password");
  await page.getByRole("dialog").getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByText(username === "alpha" ? "owner-a" : "owner-b").first()).toBeVisible();
}

test("ledger keeps contacted itinerary candidates open across logout and return navigation", async ({ page }) => {
  await stubAuth(page);
  await page.clock.install({ time: new Date("2026-11-16T12:00:00+08:00") });
  await page.goto("/");
  await signIn(page, "alpha");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();

  await page.getByRole("button", { name: "行程", exact: true }).click();
  await page.getByLabel("安排名称").fill("外滩步行");
  await page.getByRole("button", { name: "添加到行程" }).click();
  await expect(page.getByRole("heading", { name: "外滩步行" })).toBeVisible();

  await page.getByRole("button", { name: "待核实", exact: true }).click();
  await expect(page.getByRole("heading", { name: "待核实账本" })).toBeVisible();
  const candidate = page.getByRole("listitem").filter({ hasText: "外滩步行" });
  await expect(candidate).toContainText("用户提供");
  await candidate.getByRole("button", { name: "标记已联系" }).click();
  await expect(candidate).toContainText("已联系，仍待核实");
  await candidate.getByRole("button", { name: "前往复核" }).click();
  await expect(page.getByRole("heading", { name: "旅行行程" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "外滩步行" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "外滩步行" })).toBeFocused();

  await page.getByRole("button", { name: "待核实", exact: true }).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByText("游客模式")).toBeVisible();
  await signIn(page, "alpha");
  await expect(page.getByRole("heading", { name: "待核实账本" })).toBeVisible();
  const restored = page.getByRole("listitem").filter({ hasText: "外滩步行" });
  await expect(restored).toContainText("已联系，仍待核实");

  if (page.viewportSize()?.width === 375) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
  }
});
