import type { components, paths } from "../../shared/api-contracts";

export type FareQuery = components["schemas"]["FareQuery"];
export type FareResult = components["schemas"]["FareResult"];
export type FareOffer = components["schemas"]["FareOffer"];
export type RouteQuery = components["schemas"]["RouteQuery"];
export type RouteResult = components["schemas"]["RouteResult"];
export type RouteOption = components["schemas"]["RouteOption"];
export type PlaceRef = components["schemas"]["PlaceRef"];
export type RouteMode = RouteQuery["mode"];
export type TransportPublicError = components["schemas"]["PublicError"];
export type FareResponse =
  paths["/api/transport/fares/search"]["post"]["responses"][200]["content"]["application/json"];
export type RouteResponse =
  paths["/api/transport/routes/search"]["post"]["responses"][200]["content"]["application/json"];

export type TransportErrorCode = TransportPublicError["code"] | "TRANSPORT_RESPONSE_INVALID";

export class TransportApiError extends Error {
  readonly code: TransportErrorCode;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly status: number;

  constructor(
    message: string,
    options: {
      code: TransportErrorCode;
      requestId?: string | null;
      retryable?: boolean;
      status: number;
    },
  ) {
    super(message);
    this.name = "TransportApiError";
    this.code = options.code;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status;
  }
}

function isPublicError(value: unknown): value is TransportPublicError {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<TransportPublicError>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.retryable === "boolean"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isResultEnvelope(value: unknown): value is { state: string; request_id: string; items: unknown[]; sources: unknown[]; message: string; queried_at: string } {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.state === "string" &&
    typeof candidate.request_id === "string" &&
    typeof candidate.queried_at === "string" &&
    typeof candidate.message === "string" &&
    Array.isArray(candidate.items) &&
    Array.isArray(candidate.sources)
  );
}

function hasValidSources(value: Record<string, unknown>): boolean {
  return (value.sources as unknown[]).every((source) =>
    isRecord(source) && typeof source.source_id === "string" &&
    typeof source.display_name === "string" && typeof source.retrieved_at === "string",
  );
}

function isFareResponse(value: unknown): value is FareResponse {
  if (!isResultEnvelope(value) || !hasValidSources(value)) return false;
  return value.items.every((offer) =>
    isRecord(offer) && typeof offer.offer_id === "string" &&
    typeof offer.source_id === "string" && ["flight", "rail"].includes(String(offer.mode)) &&
    typeof offer.travel_date === "string" && Array.isArray(offer.segments) &&
    typeof offer.origin_name === "string" && typeof offer.destination_name === "string" &&
    typeof offer.price_basis === "string" && typeof offer.evidence_state === "string",
  );
}

function isRouteResponse(value: unknown): value is RouteResponse {
  if (!isResultEnvelope(value) || !hasValidSources(value)) return false;
  return value.items.every((route) =>
    isRecord(route) && typeof route.route_id === "string" &&
    typeof route.source_id === "string" && ["transit", "walking", "taxi"].includes(String(route.mode)) &&
    typeof route.origin_name === "string" && typeof route.destination_name === "string" &&
    typeof route.duration_basis === "string" && typeof route.fare_basis === "string" &&
    typeof route.evidence_state === "string" && Array.isArray(route.steps),
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new TransportApiError("交通服务返回了无法读取的响应。", {
      code: "TRANSPORT_RESPONSE_INVALID",
      requestId: response.headers.get("x-request-id"),
      status: response.status,
    });
  }
}

function responseError(response: Response, body: unknown): TransportApiError {
  const publicError = isPublicError(body) ? body : undefined;
  return new TransportApiError(publicError?.message ?? "交通服务请求失败。", {
    code: publicError?.code ?? "TRANSPORT_RESPONSE_INVALID",
    requestId: publicError?.request_id ?? response.headers.get("x-request-id"),
    retryable: publicError?.retryable ?? false,
    status: response.status,
  });
}

async function postTransport<T>(
  path: string,
  query: unknown,
  fetchImpl: typeof fetch,
): Promise<T> {
  const response = await fetchImpl(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
  });
  const body = await readJson(response);

  if (!response.ok) throw responseError(response, body);
  const valid = path === "/api/transport/fares/search" ? isFareResponse(body) : isRouteResponse(body);
  if (!valid) {
    throw new TransportApiError("交通服务返回了无法识别的结果。", {
      code: "TRANSPORT_RESPONSE_INVALID",
      requestId: response.headers.get("x-request-id"),
      status: response.status,
    });
  }
  return body as T;
}

export function fetchTransportFares(
  query: FareQuery,
  fetchImpl: typeof fetch = fetch,
): Promise<FareResponse> {
  return postTransport<FareResponse>("/api/transport/fares/search", query, fetchImpl);
}

export function fetchTransportRoute(
  query: RouteQuery,
  fetchImpl: typeof fetch = fetch,
): Promise<RouteResponse> {
  return postTransport<RouteResponse>("/api/transport/routes/search", query, fetchImpl);
}
