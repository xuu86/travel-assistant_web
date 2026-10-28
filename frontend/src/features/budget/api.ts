import type { components, paths } from "../../shared/api-contracts";

export type BudgetSnapshot = components["schemas"]["BudgetSnapshot"];
export type BudgetSummary = components["schemas"]["BudgetSummary"];
export type CostItem = components["schemas"]["CostItem"];
export type BudgetPublicError = components["schemas"]["PublicError"];
export type BudgetResponse =
  paths["/api/budget/calculate"]["post"]["responses"][200]["content"]["application/json"];

export class BudgetApiError extends Error {
  readonly requestId: string | null;

  constructor(message: string, requestId: string | null = null) {
    super(message);
    this.name = "BudgetApiError";
    this.requestId = requestId;
  }
}

function isPublicError(value: unknown): value is BudgetPublicError {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<BudgetPublicError>;
  return typeof candidate.message === "string" && typeof candidate.code === "string";
}

export async function calculateBudget(
  snapshot: BudgetSnapshot,
  fetchImpl: typeof fetch = fetch,
): Promise<BudgetResponse> {
  const response = await fetchImpl("/api/budget/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(snapshot),
  });

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new BudgetApiError("预算服务返回了无法读取的响应。", response.headers.get("x-request-id"));
  }

  if (!response.ok) {
    const error = isPublicError(body) ? body : undefined;
    throw new BudgetApiError(
      error?.message ?? "预算计算失败，请检查输入后重试。",
      error?.request_id ?? response.headers.get("x-request-id"),
    );
  }
  return body as BudgetResponse;
}
