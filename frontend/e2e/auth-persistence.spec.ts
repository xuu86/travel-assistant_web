import { expect, test } from "@playwright/test";

test.use({ trace: "off", screenshot: "off", video: "off" });

async function stubAuth(page: import("@playwright/test").Page) {
  let owner: string | null = null;
  await page.route("**/api/v1/auth/session", (route) => route.fulfill({
    json: owner
      ? { identity_type: "account", owner_id: owner, display_name: owner }
      : { identity_type: "guest", owner_id: null, display_name: null },
  }));
  await page.route("**/api/v1/auth/login", async (route) => {
    const body = route.request().postDataJSON() as { username: string; password: string };
    if (body.username !== "alpha" && body.username !== "beta") {
      await route.fulfill({ status: 401, json: { code: "UNAUTHORIZED", message: "用户名或密码不正确。", retryable: false } });
      return;
    }
    if (body.password !== "fixture-password") {
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
    await route.fulfill({
      status: 204,
      headers: { "set-cookie": "travel_session=; Max-Age=0; HttpOnly; Path=/; SameSite=Lax" },
    });
  });
  await page.route("**/api/**", async (route) => {
    if (route.request().url().includes("/api/v1/auth/")) return route.fallback();
    await route.fulfill({ status: 503, json: { code: "UNCONFIGURED", message: "未配置", retryable: false } });
  });
}

async function signIn(page: import("@playwright/test").Page, username: "alpha" | "beta") {
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill("fixture-password");
  await page.getByRole("dialog").getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByText(username === "alpha" ? "owner-a" : "owner-b").first()).toBeVisible();
}

test("logout and re-login restores one account while another remains isolated", async ({ page }) => {
  await stubAuth(page);
  await page.goto("/");
  await signIn(page, "alpha");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  await page.getByLabel("笔记标题").fill("返程安排");
  await page.getByLabel("笔记内容").fill("周日下午到车站");
  await page.getByRole("button", { name: "保存笔记" }).click();
  await expect(page.getByText("返程安排")).toBeVisible();
  await expect(page.locator(".workspace-save-status")).toHaveText("操作保存在本机");

  await page.reload();
  await expect(page.getByText("返程安排")).toBeVisible();

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByText("游客模式")).toBeVisible();
  await signIn(page, "alpha");
  await expect(page.getByText("返程安排")).toBeVisible();

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByText("游客模式")).toBeVisible();
  await signIn(page, "beta");
  await expect(page.getByRole("combobox", { name: "目的城市" })).toBeVisible();
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("shanghai");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  await expect(page.getByText("返程安排")).toHaveCount(0);
});

test("failed login keeps the guest workspace draft", async ({ page }) => {
  await stubAuth(page);
  await page.goto("/");
  await page.getByRole("combobox", { name: "目的城市" }).selectOption("hangzhou");
  await page.getByRole("button", { name: "开始规划" }).click();
  await page.getByRole("button", { name: "行程", exact: true }).click();
  await page.getByLabel("安排名称").fill("西湖散步");
  await page.getByLabel("备注").fill("上午出发");

  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByLabel("用户名").fill("alpha");
  await page.getByLabel("密码").fill("wrong-password");
  await page.getByRole("dialog").getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("用户名或密码不正确。");
  await expect(page.getByLabel("安排名称")).toHaveValue("西湖散步");
  await expect(page.getByLabel("备注")).toHaveValue("上午出发");
});
