import type { components, paths } from "../../shared/api-contracts";

export type AssistantRequest = components["schemas"]["ChatRequest"];
export type AssistantResponse =
  paths["/api/assistant/chat"]["post"]["responses"][200]["content"]["application/json"];
export type AssistantPublicError = components["schemas"]["PublicError"];
export type AssistantErrorCode = AssistantPublicError["code"] | "ASSISTANT_RESPONSE_INVALID";

export class AssistantApiError extends Error {
  readonly code: AssistantErrorCode;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly status: number;

  constructor(message: string, options: {
    code: AssistantErrorCode;
    requestId?: string | null;
    retryable?: boolean;
    status: number;
  }) {
    super(message);
    this.name = "AssistantApiError";
    this.code = options.code;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPublicError(value: unknown): value is AssistantPublicError {
  return isRecord(value) && typeof value.code === "string" &&
    typeof value.message === "string" && typeof value.retryable === "boolean";
}

function isSource(value: unknown): boolean {
  return isRecord(value) && typeof value.source_id === "string" &&
    typeof value.display_name === "string" && typeof value.retrieved_at === "string";
}

function isCandidatePatch(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const keys = new Set([
    "destination", "start_date", "end_date", "travelers", "budget_fen",
    "interests", "pace", "transport_mode",
  ]);
  return Object.keys(value).every((key) => keys.has(key));
}

function isAssistantResponse(value: unknown): value is AssistantResponse {
  if (!isRecord(value) || !Array.isArray(value.sources)) return false;
  const states = ["live", "unconfigured", "rate_limited", "unavailable", "policy_unavailable"];
  if (!states.includes(String(value.state)) || typeof value.request_id !== "string" ||
      typeof value.message !== "string" || typeof value.reply !== "string") return false;
  if (!value.sources.every(isSource)) return false;
  if (value.candidate_patch !== undefined && value.candidate_patch !== null &&
      !isCandidatePatch(value.candidate_patch)) return false;
  if (value.error !== undefined && value.error !== null && !isPublicError(value.error)) return false;
  return value.state === "live" ? value.reply.length > 0 : Boolean(value.error);
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new AssistantApiError("AI 助手返回了无法读取的响应。", {
      code: "ASSISTANT_RESPONSE_INVALID",
      requestId: response.headers.get("x-request-id"),
      status: response.status,
    });
  }
}

export async function sendAssistantMessage(
  request: Omit<AssistantRequest, "include_trip_context"> & { include_trip_context?: boolean },
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<AssistantResponse> {
  const response = await fetchImpl("/api/assistant/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, include_trip_context: request.include_trip_context ?? false }),
    signal,
  });
  const body = await readJson(response);
  if (!response.ok) {
    const error = isPublicError(body) ? body : undefined;
    throw new AssistantApiError(error?.message ?? "AI 助手请求失败。", {
      code: error?.code ?? "ASSISTANT_RESPONSE_INVALID",
      requestId: error?.request_id ?? response.headers.get("x-request-id"),
      retryable: error?.retryable,
      status: response.status,
    });
  }
  if (!isAssistantResponse(body)) {
    throw new AssistantApiError("AI 助手返回了无法识别的结果。", {
      code: "ASSISTANT_RESPONSE_INVALID",
      requestId: response.headers.get("x-request-id"),
      status: response.status,
    });
  }
  return body;
}
