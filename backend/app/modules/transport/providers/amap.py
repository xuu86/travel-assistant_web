from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    PlaceRef,
    RouteOption,
    RouteQuery,
    RouteResult,
    RouteStep,
)
from app.modules.transport.providers.base import TransportProviderError

_CITIES = {
    "shanghai": "310000",
    "suzhou": "320500",
    "wuxi": "320200",
    "jiaxing": "330400",
    "hangzhou": "330100",
}
_CITY_NAMES = {
    "shanghai": "上海",
    "suzhou": "苏州",
    "wuxi": "无锡",
    "jiaxing": "嘉兴",
    "hangzhou": "杭州",
}
_PATHS = {
    "walking": "/v3/direction/walking",
    "taxi": "/v3/direction/driving",
    "transit": "/v3/direction/transit/integrated",
}


class _HideTransportQuery(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "restapi.amap.com" in message:
            record.msg = re.sub(
                r"(https://restapi\.amap\.com/[^?\s\"]*)\?[^\s\"]+", r"\1?[REDACTED]", message
            )
            record.args = ()
        return True


logging.getLogger("httpx").addFilter(_HideTransportQuery())


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value)
    return int(text) if re.fullmatch(r"\d{1,10}", text) else None


def _money(value: object) -> int | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,8}(?:\.\d{1,2})?", value):
        return None
    try:
        return int(Decimal(value) * 100)
    except InvalidOperation:
        return None


def _point(value: object) -> str:
    if not isinstance(value, str):
        raise TransportProviderError("unavailable")
    try:
        lng, lat = map(float, value.split(","))
        if (
            not math.isfinite(lng)
            or not math.isfinite(lat)
            or not (-180 <= lng <= 180 and -90 <= lat <= 90)
        ):
            raise ValueError
    except ValueError:
        raise TransportProviderError("unavailable") from None
    return f"{lng:.7f},{lat:.7f}"


class _RequestBudget:
    def __init__(self, settings: Settings, client: httpx.Client):
        self.settings = settings
        self.client = client
        self.deadline = time.monotonic() + 30
        self.calls = 0

    def get(self, path: str, params: dict[str, str]) -> dict:
        self.calls += 1
        remaining = self.deadline - time.monotonic()
        if self.calls > 8 or remaining <= 0:
            raise TransportProviderError("unavailable")
        key = self.settings.amap_api_key
        if not key or not key.get_secret_value().strip():
            raise TransportProviderError("unconfigured")
        try:
            with self.client.stream(
                "GET",
                "https://restapi.amap.com" + path,
                params={**params, "key": key.get_secret_value().strip()},
                timeout=min(remaining, self.settings.amap_timeout_seconds),
                follow_redirects=False,
            ) as response:
                if response.status_code in {401, 403}:
                    raise TransportProviderError("policy_unavailable")
                if response.status_code == 429:
                    raise TransportProviderError("rate_limited")
                if response.status_code != 200:
                    raise TransportProviderError("unavailable")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 512 * 1024 or time.monotonic() >= self.deadline:
                        raise TransportProviderError("unavailable")
            if key.get_secret_value().encode() in body:
                raise TransportProviderError("unavailable")
            data = json.loads(body)
        except httpx.HTTPError, ValueError, UnicodeError:
            raise TransportProviderError("unavailable") from None
        if not isinstance(data, dict):
            raise TransportProviderError("unavailable")
        if str(data.get("status")) != "1":
            code = str(data.get("infocode", ""))
            if code in {"10003", "10004", "10014", "10019", "10020", "10021", "10029", "10044"}:
                raise TransportProviderError("rate_limited")
            if code in {
                "10001",
                "10002",
                "10005",
                "10006",
                "10007",
                "10008",
                "10009",
                "10010",
                "10011",
                "10012",
                "10013",
                "10016",
                "10032",
                "10045",
            }:
                raise TransportProviderError("policy_unavailable")
            if code in {"20000", "20001", "20002", "20003", "30000", "30001", "30002"}:
                raise TransportProviderError("no_coverage")
            raise TransportProviderError("unavailable")
        return data


class AmapRouteProvider:
    provider_id = "amap.direction"

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def _resolve(
        self, place: PlaceRef, city: str | None, budget: _RequestBudget
    ) -> tuple[str, str]:
        if any(ord(char) < 32 for char in place.display_name):
            raise TransportProviderError("no_coverage")
        if place.latitude is not None and place.longitude is not None:
            data = budget.get(
                "/v3/assistant/coordinate/convert",
                {
                    "locations": f"{place.longitude},{place.latitude}",
                    "coordsys": "gps",
                    "output": "JSON",
                },
            )
            return place.display_name, _point(data.get("locations"))
        if city not in _CITIES:
            raise TransportProviderError("no_coverage")
        data = budget.get(
            "/v5/place/text",
            {
                "keywords": place.display_name.strip(),
                "region": _CITIES[city],
                "city_limit": "true",
                "page_size": "10",
                "page_num": "1",
                "output": "JSON",
            },
        )
        pois = data.get("pois")
        if not isinstance(pois, list):
            raise TransportProviderError("unavailable")
        prefix = _CITIES[city][:2] if city == "shanghai" else _CITIES[city][:4]
        candidates = [
            poi
            for poi in pois[:10]
            if isinstance(poi, dict)
            and isinstance(poi.get("name"), str)
            and poi["name"].strip()
            and len(poi["name"]) <= 240
            and isinstance(poi.get("adcode"), str)
            and poi["adcode"].startswith(prefix)
        ]

        def normalized(name):
            return (
                name.strip().removeprefix(_CITY_NAMES[city] + "市").removeprefix(_CITY_NAMES[city])
            )

        literal = [poi for poi in candidates if poi["name"].strip() == place.display_name.strip()]
        exact = literal or [
            poi for poi in candidates if normalized(poi["name"]) == normalized(place.display_name)
        ]
        matches = exact or (candidates if len(candidates) == 1 else [])
        if len(matches) != 1:
            raise TransportProviderError("no_coverage")
        poi = matches[0]
        return poi["name"].strip(), _point(poi.get("location"))

    def search_route(self, query: RouteQuery, *, request_id: UUID) -> RouteResult:
        if query.mode == "transit" and query.city_id not in _CITIES:
            raise TransportProviderError("no_coverage")
        client = self.client or httpx.Client()
        try:
            budget = _RequestBudget(self.settings, client)
            origin_name, origin = self._resolve(query.origin, query.city_id, budget)
            destination_name, destination = self._resolve(query.destination, query.city_id, budget)
            if origin == destination:
                raise TransportProviderError("no_coverage")
            params = {"origin": origin, "destination": destination, "output": "JSON"}
            if query.mode != "walking":
                params["extensions"] = "all"
            if query.mode == "transit":
                params.update(city=_CITIES[query.city_id], cityd=_CITIES[query.city_id])
            data = budget.get(_PATHS[query.mode], params)
            return self._map(data, query, origin_name, destination_name, request_id)
        finally:
            if self.client is None:
                client.close()

    def _map(self, data, query, origin_name, destination_name, request_id):
        route = data.get("route")
        rows = (
            route.get("transits" if query.mode == "transit" else "paths")
            if isinstance(route, dict)
            else None
        )
        if not isinstance(rows, list):
            raise TransportProviderError("unavailable")
        items = []
        for index, row in enumerate(rows[:10]):
            if not isinstance(row, dict):
                continue
            duration, distance = _integer(row.get("duration")), _integer(row.get("distance"))
            steps = _steps(row, query.mode)
            if duration is None and distance is None and not steps:
                continue
            fare = _money(row.get("cost")) if query.mode == "transit" else None
            if query.mode == "taxi" and index == 0:
                fare = _money(route.get("taxi_cost"))
            basis = (
                ("meter_estimate" if query.mode == "taxi" else "per_passenger")
                if fare is not None
                else "unknown"
            )
            evidence = (
                (EvidenceState.ESTIMATE if query.mode == "taxi" else EvidenceState.VERIFIED)
                if fare is not None
                else EvidenceState.UNKNOWN
            )
            missing = ["geometry_points"]
            if distance is None:
                missing.append("distance_m")
            if duration is None:
                missing.extend(["duration_seconds", "duration_basis"])
            if fare is None:
                missing.extend(["fare_amount_fen", "fare_basis"])
            if not steps:
                missing.append("steps")
            try:
                items.append(
                    RouteOption(
                        route_id=f"amap-{query.mode}-{index}",
                        source_id=self.provider_id,
                        mode=query.mode,
                        origin_name=origin_name,
                        destination_name=destination_name,
                        distance_m=distance,
                        duration_seconds=duration,
                        duration_basis="typical_estimate" if duration is not None else "unknown",
                        steps=steps,
                        fare_amount_fen=fare,
                        fare_basis=basis,
                        fare_evidence_state=evidence,
                        evidence_state=EvidenceState.VERIFIED,
                        missing_fields=missing,
                    )
                )
            except ValidationError:
                continue
        if rows and not items:
            raise TransportProviderError("unavailable")
        now = datetime.now(UTC)
        return RouteResult(
            state=ResultState.PARTIAL if items else ResultState.EMPTY,
            items=items,
            sources=[
                SourceRef(
                    source_id=self.provider_id,
                    display_name="高德地图路线规划",
                    url="https://lbs.amap.com/api/webservice/guide/api/direction",
                    retrieved_at=now,
                    evidence_state=EvidenceState.VERIFIED,
                    attribution="路线来自高德地图；耗时为常规估算，不反映指定时刻交通。打车费用为估算。"
                    "原始轨迹为 GCJ-02，未提供可核实的 WGS84 轨迹，故不绘制地图线路。",
                )
            ],
            queried_at=now,
            request_id=request_id,
        )


def _steps(row: dict, mode: str) -> list[RouteStep]:
    entries = []
    if mode == "transit":
        segments = row.get("segments")
        for segment in segments[:100] if isinstance(segments, list) else []:
            if not isinstance(segment, dict):
                continue
            walking = segment.get("walking")
            if isinstance(walking, dict) and isinstance(walking.get("steps"), list):
                entries.extend((step, "walking") for step in walking["steps"][:100])
            bus = segment.get("bus")
            lines = bus.get("buslines") if isinstance(bus, dict) else None
            if isinstance(lines, list) and lines and isinstance(lines[0], dict):
                line = lines[0]
                name = line.get("name")
                instruction = "乘坐" + name if isinstance(name, str) and name else None
                entries.append(
                    (
                        {**line, "instruction": instruction},
                        "subway" if line.get("type") == "地铁线路" else "bus",
                    )
                )
    else:
        steps = row.get("steps")
        entries = (
            [(step, "walking" if mode == "walking" else "driving") for step in steps[:200]]
            if isinstance(steps, list)
            else []
        )
    result = []
    for raw, step_mode in entries[:200]:
        if not isinstance(raw, dict):
            continue
        text = raw.get("instruction")
        instruction = text.strip() if isinstance(text, str) and text.strip() else None
        if instruction and (len(instruction) > 1000 or any(ord(c) < 32 for c in instruction)):
            instruction = None
        distance, duration = _integer(raw.get("distance")), _integer(raw.get("duration"))
        if instruction is None and distance is None and duration is None:
            continue
        result.append(
            RouteStep(
                instruction=instruction,
                step_mode=step_mode,
                distance_m=distance,
                duration_seconds=duration,
            )
        )
    return result
