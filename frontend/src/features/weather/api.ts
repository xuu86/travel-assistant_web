import type { components, paths } from "../../shared/api-contracts";

export type WeatherQuery = components["schemas"]["WeatherQuery"];
export type WeatherResult = components["schemas"]["WeatherResult"];
export type WeatherPublicError = components["schemas"]["PublicError"];
export type ForecastResponse =
  paths["/api/weather/forecast"]["post"]["responses"][200]["content"]["application/json"];

export type WeatherErrorCode = WeatherPublicError["code"] | "WEATHER_RESPONSE_INVALID";

export class WeatherApiError extends Error {
  readonly code: WeatherErrorCode;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly status: number;

  constructor(
    message: string,
    options: {
      code: WeatherErrorCode;
      requestId?: string | null;
      retryable?: boolean;
      status: number;
    },
  ) {
    super(message);
    this.name = "WeatherApiError";
    this.code = options.code;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.status = options.status;
  }
}

function isPublicError(value: unknown): value is WeatherPublicError {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<WeatherPublicError>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.retryable === "boolean"
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new WeatherApiError("天气服务返回了无法读取的响应。", {
      code: "WEATHER_RESPONSE_INVALID",
      requestId: response.headers.get("x-request-id"),
      status: response.status,
    });
  }
}

export async function fetchWeatherForecast(
  query: WeatherQuery,
  fetchImpl: typeof fetch = fetch,
): Promise<ForecastResponse> {
  const response = await fetchImpl("/api/weather/forecast", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
  });
  const body = await readJson(response);

  if (!response.ok) {
    const publicError = isPublicError(body) ? body : undefined;
    throw new WeatherApiError(publicError?.message ?? "天气服务请求失败。", {
      code: publicError?.code ?? "WEATHER_RESPONSE_INVALID",
      requestId: publicError?.request_id ?? response.headers.get("x-request-id"),
      retryable: publicError?.retryable ?? false,
      status: response.status,
    });
  }

  return body as ForecastResponse;
}

export type WeatherRequestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: ForecastResponse }
  | { status: "error"; error: WeatherApiError };
