from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.contracts import ErrorCode, EvidenceState, ResultState, SourceRef
from app.core.errors import ServiceError, to_public_error
from app.core.places import (
    Place,
    PlaceCategory,
    PlaceLocation,
    PlaceQuery,
    PlaceResult,
    StaticMapQuery,
)

_BASE = "https://restapi.amap.com"
_CITIES = {
    "shanghai": ("310000", "上海市"),
    "suzhou": ("320500", "苏州市"),
    "wuxi": ("320200", "无锡市"),
    "jiaxing": ("330400", "嘉兴市"),
    "hangzhou": ("330100", "杭州市"),
}
_TYPES = {"hotels": "100000", "activities": "080000", "attractions": "110000"}
_MESSAGES = {
    ErrorCode.UNCONFIGURED: "高德地点与地图服务尚未配置。",
    ErrorCode.RATE_LIMITED: "高德服务额度已用尽或请求过于频繁，请稍后重试。",
    ErrorCode.POLICY_UNAVAILABLE: "高德服务权限暂不可用，请检查服务配置。",
    ErrorCode.PROVIDER_UNAVAILABLE: "高德服务暂不可用，请稍后重试。",
    ErrorCode.NO_COVERAGE: "高德暂未返回该城市的位置。",
}
_STATES = {
    ErrorCode.UNCONFIGURED: ResultState.UNCONFIGURED,
    ErrorCode.RATE_LIMITED: ResultState.RATE_LIMITED,
    ErrorCode.POLICY_UNAVAILABLE: ResultState.POLICY_UNAVAILABLE,
    ErrorCode.PROVIDER_UNAVAILABLE: ResultState.UNAVAILABLE,
    ErrorCode.NO_COVERAGE: ResultState.NO_COVERAGE,
}


class _RedactAmapKey(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "restapi.amap.com" in message:
            record.msg = re.sub(r"([?&](?:key|sig)=)[^&\s\"']+", r"\1[REDACTED]", message)
            record.args = ()
        return True


# httpx logs full request URLs at INFO, including Web-service query credentials.
logging.getLogger("httpx").addFilter(_RedactAmapKey())


def _text(value: object, maximum: int) -> str | None:
    return value.strip()[:maximum] if isinstance(value, str) and value.strip() else None


def _location(value: object) -> PlaceLocation | None:
    if not isinstance(value, str):
        return None
    try:
        lng, lat = value.split(",")
        return PlaceLocation(longitude=float(lng), latitude=float(lat))
    except ValueError, ValidationError:
        return None


def _in_city(adcode: object, city_code: str) -> bool:
    prefix = city_code[:2] if city_code == "310000" else city_code[:4]
    return isinstance(adcode, str) and adcode.startswith(prefix)


class AmapService:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client

    def _get(self, path: str, params: dict[str, str], *, image: bool = False) -> tuple[bytes, str]:
        if not self.settings.amap_configured:
            raise ServiceError(ErrorCode.UNCONFIGURED)
        key = self.settings.amap_api_key
        assert key is not None
        parameters = {**params, "key": key.get_secret_value().strip()}
        owned_client = self.client is None
        client = self.client or httpx.Client()
        try:
            with client.stream(
                "GET",
                _BASE + path,
                params=parameters,
                timeout=self.settings.amap_timeout_seconds,
                follow_redirects=False,
            ) as response:
                if response.status_code == 429:
                    raise ServiceError(ErrorCode.RATE_LIMITED)
                if response.status_code in {401, 403}:
                    raise ServiceError(ErrorCode.POLICY_UNAVAILABLE)
                if response.status_code != 200:
                    raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
                limit = 2 * 1024 * 1024 if image else 512 * 1024
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", "").split(";")[0]
        except httpx.HTTPError:
            raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE) from None
        finally:
            if owned_client:
                client.close()

    @staticmethod
    def _json(body: bytes) -> dict:
        try:
            data = json.loads(body)
        except ValueError, UnicodeDecodeError:
            raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE) from None
        if not isinstance(data, dict):
            raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
        if str(data.get("status")) != "1":
            code = str(data.get("infocode", ""))
            if code in {"10003", "10004", "10014", "10019", "10020", "10021", "10029", "10044"}:
                raise ServiceError(ErrorCode.RATE_LIMITED)
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
                raise ServiceError(ErrorCode.POLICY_UNAVAILABLE)
            raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
        return data

    def search(
        self, query: PlaceQuery, category: PlaceCategory, *, request_id: UUID
    ) -> PlaceResult:
        try:
            city_code, _ = _CITIES[query.city_id]
            params = {
                "region": city_code,
                "city_limit": "true",
                "keywords": query.keywords,
                "page_size": "10",
                "page_num": str(query.page),
                "show_fields": "business",
                "output": "JSON",
            }
            if category in _TYPES:
                params["types"] = _TYPES[category]
            elif not query.keywords:
                params["types"] = "110000"
            data = self._json(self._get("/v5/place/text", params)[0])
            rows = data.get("pois")
            if not isinstance(rows, list):
                raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
            items: list[Place] = []
            seen: set[str] = set()
            incomplete = False
            for row in rows[:10]:
                if not isinstance(row, dict):
                    incomplete = True
                    continue
                name, poi_id = _text(row.get("name"), 240), _text(row.get("id"), 160)
                if not name or not poi_id or not _in_city(row.get("adcode"), city_code):
                    incomplete = True
                    continue
                if poi_id in seen:
                    continue
                seen.add(poi_id)
                items.append(
                    Place(
                        id=poi_id,
                        name=name,
                        address=_text(row.get("address"), 500),
                        category=_text(row.get("type"), 300),
                        telephone=_text(row["business"].get("tel"), 200)
                        if isinstance(row.get("business"), dict) else None,
                        location=_location(row.get("location")),
                    )
                )
            if rows and not items:
                raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
            now = datetime.now(UTC)
            return PlaceResult(
                state=(ResultState.PARTIAL if incomplete else ResultState.LIVE)
                if items
                else ResultState.EMPTY,
                items=items,
                city_id=query.city_id,
                category=category,
                page=query.page,
                has_more=query.page < 100 and len(rows) >= 10,
                sources=[
                    SourceRef(
                        source_id="amap.place",
                        display_name="高德地图地点搜索",
                        url="https://lbs.amap.com/api/webservice/guide/api/search",
                        retrieved_at=now,
                        evidence_state=EvidenceState.VERIFIED,
                        attribution="地点资料来自高德地图；不代表实时房价、余房或活动档期。",
                    )
                ],
                request_id=request_id,
                queried_at=now,
                message="仅展示地点资料；报价、库存、活动档期、开放与预约情况需另行核实。"
                if items
                else "该城市未查询到符合条件的地点，请调整关键词。",
            )
        except ServiceError as exc:
            return PlaceResult(
                state=_STATES[exc.code],
                city_id=query.city_id,
                category=category,
                page=query.page,
                request_id=request_id,
                message=_MESSAGES[exc.code],
                error=to_public_error(exc, request_id=request_id),
            )

    def static_map(self, query: StaticMapQuery) -> tuple[bytes, str]:
        location = query.location
        if location is None:
            city_code, name = _CITIES[query.city_id]
            data = self._json(
                self._get(
                    "/v3/geocode/geo",
                    {
                        "address": name,
                        "city": city_code,
                        "output": "JSON",
                    },
                )[0]
            )
            rows = data.get("geocodes")
            if not isinstance(rows, list):
                raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
            location = next(
                (
                    point
                    for row in rows
                    if isinstance(row, dict)
                    and _in_city(row.get("adcode"), city_code)
                    and (point := _location(row.get("location"))) is not None
                ),
                None,
            )
            if location is None:
                raise ServiceError(ErrorCode.NO_COVERAGE)
        position = f"{location.longitude:.6f},{location.latitude:.6f}"
        body, content_type = self._get(
            "/v3/staticmap",
            {
                "location": position,
                "zoom": str(query.zoom),
                "size": "750*400",
                "scale": "1",
                "markers": f"mid,0xB13D22,A:{position}",
            },
            image=True,
        )
        signatures = {
            "image/png": body.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": body.startswith(b"\xff\xd8\xff"),
            "image/gif": body.startswith((b"GIF87a", b"GIF89a")),
        }
        if content_type in signatures and signatures[content_type]:
            return body, content_type
        self._json(body)  # Map authorization/quota failures are often JSON with HTTP 200.
        raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)
