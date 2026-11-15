import { afterEach, describe, expect, it, vi } from "vitest";
import { getAuthSession, login, logout } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("auth API", () => {
  it("uses same-origin cookies without storing credentials client-side", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      identity_type: "account", owner_id: "user-1", display_name: "旅行用户1",
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await getAuthSession();
    await login({ username: "traveler1", password: "private-password" });
    await logout();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/session", "/api/v1/auth/login", "/api/v1/auth/logout",
    ]);
    expect(fetchMock.mock.calls.every(([, init]) => init?.credentials === "same-origin")).toBe(true);
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(JSON.stringify({
      username: "traveler1", password: "private-password",
    }));
    expect(localStorage.length).toBe(0);
  });

  it("maps public auth failures without exposing submitted credentials", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      code: "UNAUTHORIZED", message: "用户名或密码不正确。", retryable: false,
    }), { status: 401, headers: { "content-type": "application/json" } })));

    await expect(login({ username: "traveler1", password: "private-password" }))
      .rejects.toMatchObject({ status: 401, code: "UNAUTHORIZED", message: "用户名或密码不正确。" });
  });
});
