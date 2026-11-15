import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthProvider";
import { LoginDialog } from "./LoginDialog";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("LoginDialog", () => {
  it("signs in and presents an explicit logout action", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(response({ identity_type: "guest", owner_id: null, display_name: null }))
      .mockResolvedValueOnce(response({ identity_type: "account", owner_id: "user-1", display_name: "旅行用户1" }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthProvider><LoginDialog /></AuthProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "登录" }));
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "traveler1" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "fixture-password" } });
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);

    expect(await screen.findByText("旅行用户1")).toBeVisible();
    expect(screen.getByRole("button", { name: "退出登录" })).toBeVisible();
    expect(fetchMock.mock.calls[1]?.[1]?.body).toContain("fixture-password");
  });

  it("keeps the login form and displays a safe message after failure", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(response({ identity_type: "guest", owner_id: null, display_name: null }))
      .mockResolvedValueOnce(response({ code: "UNAUTHORIZED", message: "用户名或密码不正确。", retryable: false }, 401));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthProvider><LoginDialog /></AuthProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "登录" }));
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "traveler1" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "wrong-password" } });
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("用户名或密码不正确");
    expect(screen.getByLabelText("密码")).toHaveValue("wrong-password");
    await waitFor(() => expect(screen.getByText("游客模式")).toBeVisible());
  });
});
