import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantApiError, sendAssistantMessage } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("assistant API client", () => {
  it("posts the typed message to the same-origin endpoint and returns the response", async () => {
    const responseBody = {
      state: "unconfigured",
      request_id: "request-1",
      message: "AI 助手尚未配置。",
      reply: "",
      candidate_patch: null,
      sources: [],
      error: { code: "UNCONFIGURED", message: "AI 助手尚未配置。", retryable: false, request_id: "request-1" },
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(responseBody), {
      status: 200,
      headers: { "content-type": "application/json", "x-request-id": "request-1" },
    }));

    const result = await sendAssistantMessage({ message: "你好" }, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("/api/assistant/chat", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "你好", include_trip_context: false }),
    }));
    expect(result.state).toBe("unconfigured");
  });

  it("forwards abort signal", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      state: "unconfigured", request_id: "r", message: "未配置", reply: "", sources: [],
      error: { code: "UNCONFIGURED", message: "未配置", retryable: false },
    }), { status: 200 }));

    await sendAssistantMessage({ message: "你好" }, fetchMock, controller.signal);

    expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal);
  });

  it("maps public API errors without exposing arbitrary response text", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      code: "RATE_LIMITED", message: "请求暂受额度限制。", retryable: true, request_id: "r-2",
    }), { status: 429 }));

    await expect(sendAssistantMessage({ message: "你好" }, fetchMock)).rejects.toMatchObject({
      name: "AssistantApiError", code: "RATE_LIMITED", requestId: "r-2", retryable: true, status: 429,
    });
  });

  it("rejects malformed success payloads and invalid JSON", async () => {
    const malformed = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}", { status: 200 }));
    await expect(sendAssistantMessage({ message: "你好" }, malformed)).rejects.toBeInstanceOf(AssistantApiError);
    const badJson = vi.fn<typeof fetch>().mockResolvedValue(new Response("<html>private</html>", { status: 200 }));
    await expect(sendAssistantMessage({ message: "你好" }, badJson)).rejects.toThrow("无法读取");
  });
});
