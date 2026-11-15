import type { components } from "../../shared/api-contracts";

export type AuthIdentity = components["schemas"]["IdentityResponse"];
export type LoginInput = components["schemas"]["LoginRequest"];

export class AuthApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "AuthApiError";
    this.status = status;
    this.code = code;
  }
}

async function readError(response: Response): Promise<AuthApiError> {
  let message = "登录服务暂不可用，请稍后重试。";
  let code: string | null = null;
  try {
    const body = await response.json() as { message?: unknown; code?: unknown };
    if (typeof body.message === "string") message = body.message;
    if (typeof body.code === "string") code = body.code;
  } catch {
    // Keep the public fallback when the response is not JSON.
  }
  return new AuthApiError(message, response.status, code);
}

export async function getAuthSession(signal?: AbortSignal): Promise<AuthIdentity> {
  const response = await fetch("/api/v1/auth/session", {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw await readError(response);
  return await response.json() as AuthIdentity;
}

export async function login(input: LoginInput): Promise<AuthIdentity> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await readError(response);
  return await response.json() as AuthIdentity;
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await readError(response);
}
