import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./auth-context";
import { LoginDialog } from "./LoginDialog";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Probe() {
  const auth = useAuth();
  return <div>
    <span>{auth.identity.identity_type}:{auth.identity.owner_id ?? "none"}</span>
    <button onClick={() => void auth.login({ username: "traveler1", password: "secret" })}>sign in</button>
    <button onClick={() => void auth.logout()}>sign out</button>
  </div>;
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("AuthProvider", () => {
  it("waits for the current session and updates identity on login/logout", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ identity_type: "guest", owner_id: null, display_name: null }))
      .mockResolvedValueOnce(jsonResponse({ identity_type: "account", owner_id: "user-1", display_name: "旅行用户1" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthProvider><Probe /></AuthProvider>);

    expect(screen.getByText("正在恢复工作区…")).toBeVisible();
    expect(await screen.findByText("guest:none")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "sign in" }));
    await waitFor(() => expect(screen.getByText("account:user-1")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "sign out" }));
    await waitFor(() => expect(screen.getByText("guest:none")).toBeVisible());
  });

  it("continues as guest when the authentication service cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("network detail")));
    render(<AuthProvider><><Probe /><LoginDialog /></></AuthProvider>);

    expect(await screen.findByText("guest:none")).toBeVisible();
    expect(screen.getByText("guest:none").closest("div")).toBeInTheDocument();
    expect(screen.getByText("登录服务暂不可用，当前以游客身份使用")).toBeVisible();
  });
});
