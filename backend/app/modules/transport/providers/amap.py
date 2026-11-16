from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.amap import AmapService, _location, _text
from app.core.contracts import ErrorCode, EvidenceState, ResultState, SourceRef
from app.core.errors import ServiceError
from app.modules.transport.contracts import (
    PlaceRef,
    RouteOption,
    RouteQuery,
    RouteResult,
    RouteStep,
)
from app.modules.transport.providers.base import TransportProviderError


def _number(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


class AmapRouteProvider:
    """Server-side directions; never relabel GCJ-02 geometry as WGS84."""

    def __init__(self, service: AmapService) -> None:
        self.service = service

    def _get(self, path: str, params: dict[str, str]) -> dict:
        return self.service._json(self.service._get(path, {**params, "output": "JSON"})[0])

    def _resolve(self, place: PlaceRef, *, need_city: bool) -> tuple[str, str | None]:
        if place.latitude is not None and place.longitude is not None:
            data = self._get(
                "/v3/assistant/coordinate/convert",
                {
                    "locations": f"{place.longitude},{place.latitude}",
                    "coordsys": "gps",
                },
            )
            point = _location(data.get("locations"))
            if point is None:
                raise TransportProviderError("unavailable")
            position = f"{point.longitude},{point.latitude}"
            city = None
            if need_city:
                reverse = self._get("/v3/geocode/regeo", {"location": position})
                component = reverse.get("regeocode", {}).get("addressComponent", {})
                city = _text(component.get("citycode"), 20)
            return position, city
        data = self._get("/v3/geocode/geo", {"address": place.display_name})
        rows = data.get("geocodes")
        if not isinstance(rows, list):
            raise TransportProviderError("unavailable")
        # Ambiguous or missing addresses must not silently select another place.
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise TransportProviderError("no_coverage")
        point = _location(rows[0].get("location"))
        if point is None:
            raise TransportProviderError("no_coverage")
        return f"{point.longitude},{point.latitude}", _text(rows[0].get("citycode"), 20)

    @staticmethod
    def _steps(path: dict, mode: str) -> list[RouteStep]:
        steps: list[RouteStep] = []

        def add(row: object, step_mode: str, instruction: str | None = None) -> None:
            if not isinstance(row, dict):
                return
            text = instruction or _text(row.get("instruction"), 1000)
            distance, duration = _number(row.get("distance")), _number(row.get("duration"))
            if text is not None or distance is not None or duration is not None:
                steps.append(
                    RouteStep(
                        instruction=text,
                        step_mode=step_mode,
                        distance_m=distance,
                        duration_seconds=duration,
                    )
                )

        if mode != "transit":
            for row in path.get("steps", []):
                add(row, "walking" if mode == "walking" else "driving")
        else:
            for segment in path.get("segments", []):
                walking = segment.get("walking")
                if isinstance(walking, dict):
                    for row in walking.get("steps", []):
                        add(row, "walking")
                bus = segment.get("bus")
                if isinstance(bus, dict):
                    lines = bus.get("buslines", [])
                    # Alternatives are not sequential legs: only use the selected first line.
                    if lines and isinstance(lines[0], dict):
                        line = lines[0]
                        name = _text(line.get("name"), 300)
                        departure = line.get("departure_stop", {})
                        arrival = line.get("arrival_stop", {})
                        start = _text(departure.get("name"), 240)
                        end = _text(arrival.get("name"), 240)
                        instruction = " · ".join(x for x in (name, start, end) if x) or None
                        add(
                            line,
                            "subway" if "地铁" in str(line.get("type", "")) else "bus",
                            instruction,
                        )
                railway = segment.get("railway")
                if isinstance(railway, dict):
                    add(railway, "rail", _text(railway.get("name"), 1000))
        return steps

    def search_route(self, query: RouteQuery, *, request_id: UUID) -> RouteResult:
        try:
            origin, city = self._resolve(query.origin, need_city=query.mode == "transit")
            destination, cityd = self._resolve(
                query.destination,
                need_city=query.mode == "transit",
            )
            params = {"origin": origin, "destination": destination}
            endpoint = {"walking": "walking", "taxi": "driving", "transit": "transit/integrated"}
            if query.mode == "transit":
                if not city or not cityd:
                    raise TransportProviderError("no_coverage")
                params.update(city=city, cityd=cityd, extensions="all")
                if query.depart_at is not None:
                    departure = query.depart_at.astimezone(ZoneInfo("Asia/Shanghai"))
                    params.update(
                        date=departure.strftime("%Y-%m-%d"),
                        time=departure.strftime("%H:%M"),
                    )
            data = self._get("/v3/direction/" + endpoint[query.mode], params)
            route = data.get("route")
            if not isinstance(route, dict):
                raise TransportProviderError("unavailable")
            rows = route.get("transits" if query.mode == "transit" else "paths")
            if not isinstance(rows, list):
                raise TransportProviderError("unavailable")
            items = []
            for index, row in enumerate(rows[:5]):
                if not isinstance(row, dict):
                    raise TransportProviderError("unavailable")
                distance, duration = _number(row.get("distance")), _number(row.get("duration"))
                steps = self._steps(row, query.mode)
                missing = ["geometry_points", "fare_amount_fen", "fare_basis"]
                if distance is None:
                    missing.append("distance_m")
                if duration is None:
                    missing.extend(["duration_seconds", "duration_basis"])
                if not steps:
                    missing.append("steps")
                items.append(
                    RouteOption(
                        route_id=f"amap.{query.mode}.{index}",
                        source_id="amap.directions",
                        mode=query.mode,
                        origin_name=query.origin.display_name,
                        destination_name=query.destination.display_name,
                        distance_m=distance,
                        duration_seconds=duration,
                        duration_basis="typical_estimate" if duration is not None else "unknown",
                        steps=steps,
                        fare_basis="unknown",
                        fare_evidence_state=EvidenceState.UNKNOWN,
                        evidence_state=EvidenceState.ESTIMATE,
                        missing_fields=missing,
                    )
                )
            now = datetime.now(UTC)
            return RouteResult(
                state=ResultState.PARTIAL if items else ResultState.EMPTY,
                items=items,
                sources=[
                    SourceRef(
                        source_id="amap.directions",
                        display_name="高德地图路线规划",
                        url="https://lbs.amap.com/api/webservice/guide/api/direction",
                        retrieved_at=now,
                        evidence_state=EvidenceState.ESTIMATE,
                        attribution="路线及用时为规划参考，非实时到站或保证到达；不提供费用。",
                    )
                ],
                queried_at=now,
                request_id=request_id,
            )
        except ServiceError as exc:
            statuses = {
                ErrorCode.UNCONFIGURED: "unconfigured",
                ErrorCode.NO_COVERAGE: "no_coverage",
                ErrorCode.RATE_LIMITED: "rate_limited",
                ErrorCode.POLICY_UNAVAILABLE: "policy_unavailable",
            }
            raise TransportProviderError(statuses.get(exc.code, "unavailable")) from None
