import type { components } from "../../shared/api-contracts";

export type Place = components["schemas"]["Place"];
type PlaceResultSchema = components["schemas"]["PlaceResult"];
export type PlaceResult = PlaceResultSchema & Required<Pick<PlaceResultSchema,
  "items" | "sources" | "queried_at" | "message" | "has_more"
>>;
export type PlaceQuery = components["schemas"]["PlaceQuery"];
export type PlaceCategory = PlaceResult["category"];
export type StaticMapQuery = components["schemas"]["StaticMapQuery"];

const STATES = new Set([
  "live", "partial", "empty", "unconfigured", "no_coverage", "rate_limited",
  "unavailable", "policy_unavailable",
]);

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export class PlacesApiError extends Error {}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (record(body) && typeof body.message === "string") return body.message;
  } catch { /* A non-JSON upstream error has no public message. */ }
  return "地点与地图服务暂不可用，请稍后重试。";
}

export async function searchPlaces(
  category: PlaceCategory, query: PlaceQuery, signal?: AbortSignal,
): Promise<PlaceResult> {
  const response = await fetch(`/api/${category}/search`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query), signal,
  });
  if (!response.ok) throw new PlacesApiError(await errorMessage(response));
  const data: unknown = await response.json();
  if (!record(data) || !STATES.has(String(data.state)) || !Array.isArray(data.items) ||
    !Array.isArray(data.sources) || data.city_id !== query.city_id || data.category !== category ||
    data.page !== (query.page ?? 1) || typeof data.has_more !== "boolean" ||
    typeof data.message !== "string" || typeof data.request_id !== "string" ||
    typeof data.queried_at !== "string" || !Number.isFinite(Date.parse(data.queried_at)) ||
    !data.items.every((item: unknown) => record(item) && typeof item.id === "string" &&
      typeof item.name === "string" &&
      ["address", "category", "telephone"].every((key) => item[key] == null || typeof item[key] === "string") &&
      (item.location === null || (record(item.location) && item.location.coordinate_system === "GCJ02" &&
        typeof item.location.longitude === "number" && Number.isFinite(item.location.longitude) &&
        Math.abs(item.location.longitude) <= 180 && typeof item.location.latitude === "number" &&
        Number.isFinite(item.location.latitude) && Math.abs(item.location.latitude) <= 90))) ||
    !data.sources.every((source: unknown) => record(source) && typeof source.display_name === "string") ||
    (!["live", "partial"].includes(String(data.state)) && data.items.length > 0) ||
    (data.state === "live" && data.items.length === 0)
  ) throw new PlacesApiError("地点服务返回了无法识别的结果，请重试。");
  return data as PlaceResult;
}

export async function fetchStaticMap(query: StaticMapQuery, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch("/api/maps/static", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query), signal,
  });
  if (!response.ok) throw new PlacesApiError(await errorMessage(response));
  if (!/^image\/(png|jpeg|gif)(;|$)/.test(response.headers.get("content-type") ?? "")) {
    throw new PlacesApiError("地图暂不可用，地点文字资料仍可查看。");
  }
  return response.blob();
}
