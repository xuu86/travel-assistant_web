from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import SecretStr, ValidationError

from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    FareOffer,
    FareQuery,
    FareResult,
    FareSegment,
    validate_fare_booking_url,
)
from app.modules.transport.providers.base import TransportProviderError

CLI_VERSION = "1.0.16"
CLI_SHA256 = "194a66eb84094f3d8ee20fac0a2d6cae10a405cd59ac100b7e7880ebc97297da"
_ROOT = Path(__file__).resolve().parents[5]
_BUNDLE = _ROOT / ".tools/flyai/dist/flyai-bundle.cjs"
_GUARD = Path(__file__).with_name("flyai_runner.cjs")
_ZONE = ZoneInfo("Asia/Shanghai")
_SLOTS = threading.BoundedSemaphore(2)
_ENV_NAMES = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "HOME",
    "APPDATA",
    "LOCALAPPDATA",
    "LANG",
    "LC_ALL",
}


@dataclass(frozen=True)
class CliOutput:
    exit_code: int
    stdout: bytes
    http_status: int | None
    request_count: int
    authenticated: bool


class CliExecutor(Protocol):
    def run(self, query: FareQuery, *, key: str, timeout: float, limit: int) -> CliOutput: ...


class FlyAICommand:
    """Bounded subprocess runner. Neither key nor query appears in argv or logs."""

    def __init__(self, node_path: str = "node") -> None:
        self.node_path = node_path

    def run(self, query: FareQuery, *, key: str, timeout: float, limit: int) -> CliOutput:
        node = shutil.which(self.node_path)
        if node is None or not _BUNDLE.is_file():
            raise TransportProviderError("unconfigured")
        if hashlib.sha256(_BUNDLE.read_bytes()).hexdigest() != CLI_SHA256:
            raise TransportProviderError("unavailable")
        env = {name: value for name, value in os.environ.items() if name.upper() in _ENV_NAMES}
        env.update(
            FLYAI_API_KEY=key,
            FLYAI_APP_TIMEOUT_MS=str(int(timeout * 1000)),
            FLYAI_APP_MAX_RESPONSE_BYTES=str(limit),
        )
        payload = json.dumps(
            {
                "origin": query.origin.display_name.strip(),
                "destination": query.destination.display_name.strip(),
                "date": query.travel_date.isoformat(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        if len(payload) > 4096:
            raise TransportProviderError("no_coverage")
        if not _SLOTS.acquire(blocking=False):
            raise TransportProviderError("rate_limited")
        try:
            return self._execute(node, env, payload, key, timeout, limit)
        finally:
            _SLOTS.release()

    @staticmethod
    def _execute(
        node: str, env: dict[str, str], payload: bytes, key: str, timeout: float, limit: int
    ) -> CliOutput:
        process = None
        readers: list[threading.Thread] = []
        chunks: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()
        try:
            process = subprocess.Popen(
                [node, str(_GUARD)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=False,
                cwd=_ROOT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            def drain(name: str, stream, cap: int) -> None:
                try:
                    while block := stream.read(8192):
                        if len(chunks[name]) + len(block) > cap:
                            overflow.set()
                            process.kill()
                            break
                        chunks[name].extend(block)
                except OSError:
                    overflow.set()
                finally:
                    stream.close()

            for name, stream, cap in (
                ("stdout", process.stdout, limit),
                ("stderr", process.stderr, 64 * 1024),
            ):
                thread = threading.Thread(target=drain, args=(name, stream, cap), daemon=True)
                thread.start()
                readers.append(thread)
            process.stdin.write(payload)
            process.stdin.close()
            process.wait(timeout=timeout + 5)
        except OSError, subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
                process.wait(timeout=5)
            raise TransportProviderError("unavailable") from None
        finally:
            for reader in readers:
                reader.join(timeout=5)
        if overflow.is_set() or any(reader.is_alive() for reader in readers):
            raise TransportProviderError("unavailable")
        stdout, stderr = bytes(chunks["stdout"]), bytes(chunks["stderr"])
        if key.encode() in stdout or key.encode() in stderr:
            raise TransportProviderError("unavailable")
        try:
            lines = stderr.decode("utf-8").splitlines()
            audits = [
                json.loads(line.removeprefix("FLYAI_APP_AUDIT="))
                for line in lines
                if line.startswith("FLYAI_APP_AUDIT=")
            ]
            if len(audits) != 1 or not isinstance(audits[0], dict):
                raise ValueError("Missing network audit.")
            audit = audits[0]
            return CliOutput(
                exit_code=process.returncode,
                stdout=stdout,
                http_status=audit.get("http_status"),
                request_count=audit.get("fetch_count", 0),
                authenticated=audit.get("authorization_matches") is True,
            )
        except ValueError, UnicodeError:
            raise TransportProviderError("unavailable") from None


class FlyAITrainFareProvider:
    provider_id = "flyai.search-train"

    def __init__(
        self,
        *,
        api_key: SecretStr,
        node_path: str = "node",
        timeout_seconds: float = 45,
        max_response_bytes: int = 1024 * 1024,
        executor: CliExecutor | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._key = api_key
        self._executor = executor if executor is not None else FlyAICommand(node_path)
        self._timeout = timeout_seconds
        self._limit = max_response_bytes
        self._now = now or (lambda: datetime.now(UTC))

    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult:
        if query.mode != "rail":
            raise TransportProviderError("no_coverage")
        key = self._key.get_secret_value().strip()
        if not key:
            raise TransportProviderError("unconfigured")
        if query.travel_date <= self._now().astimezone(_ZONE).date():
            raise TransportProviderError("no_coverage")
        if any(
            char in name
            for name in (query.origin.display_name, query.destination.display_name)
            for char in ("\x00", "\r", "\n")
        ):
            raise TransportProviderError("no_coverage")
        output = self._executor.run(query, key=key, timeout=self._timeout, limit=self._limit)
        if output.request_count != 1 or not output.authenticated:
            raise TransportProviderError("unavailable")
        if output.http_status in (401, 403):
            raise TransportProviderError("policy_unavailable")
        if output.http_status == 429:
            raise TransportProviderError("rate_limited")
        if output.http_status != 200 or output.exit_code != 0 or len(output.stdout) > self._limit:
            raise TransportProviderError("unavailable")
        if key.encode() in output.stdout:
            raise TransportProviderError("unavailable")
        try:
            payload = json.loads(output.stdout)
            return map_train_result(payload, query, request_id=request_id, now=self._now())
        except ValueError, TypeError, KeyError, ValidationError:
            raise TransportProviderError("unavailable") from None


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        return None
    return value.strip()


def _time(value: object) -> datetime | None:
    if (
        not isinstance(value, str)
        or not 19 <= len(value) <= 40
        or value[10] not in " T"
        or value[13] != ":"
        or value[16] != ":"
    ):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=parsed.tzinfo or _ZONE).astimezone(UTC)
    except ValueError:
        return None


def _segment(raw: dict, index: int) -> FareSegment:
    kind = raw.get("transportType")
    if not isinstance(kind, str) or kind.casefold() not in {
        "train",
        "rail",
        "railway",
        "火车",
        "铁路",
        "高铁",
        "动车",
    }:
        raise ValueError("Unsupported transport type.")
    return FareSegment(
        segment_id=f"leg-{index}",
        origin_name=_text(raw.get("depStationName"), 240),
        destination_name=_text(raw.get("arrStationName"), 240),
        departure_at=_time(raw.get("depDateTime")),
        arrival_at=_time(raw.get("arrDateTime")),
        departure_timezone="Asia/Shanghai",
        arrival_timezone="Asia/Shanghai",
        service_number=_text(raw.get("marketingTransportNo"), 80),
        seat_class=_text(raw.get("seatClassName"), 120),
    )


def _offer(item: dict, index: int, query: FareQuery) -> FareOffer:
    journeys = item.get("journeys")
    if not isinstance(journeys, list) or not journeys or len(journeys) > 10:
        raise ValueError("Invalid journeys.")
    raw_segments = []
    for journey in journeys:
        segments = journey.get("segments") if isinstance(journey, dict) else None
        if not isinstance(segments, list) or not segments:
            raise ValueError("Invalid journey segments.")
        raw_segments.extend(segments)
    if len(raw_segments) > 30 or not all(isinstance(raw, dict) for raw in raw_segments):
        raise ValueError("Invalid segment count.")
    first_raw, last_raw = raw_segments[0], raw_segments[-1]
    if query.origin.display_name.strip() not in {
        first_raw.get("depCityName"),
        first_raw.get("depStationName"),
    } or query.destination.display_name.strip() not in {
        last_raw.get("arrCityName"),
        last_raw.get("arrStationName"),
    }:
        raise ValueError("Unmatched endpoints.")
    legs = [_segment(raw, n) for n, raw in enumerate(raw_segments)]
    first, last = legs[0], legs[-1]
    if not first.origin_name or not last.destination_name:
        raise ValueError("Missing stations.")
    departure_date = _text(first_raw.get("depDateTime"), 40)
    if departure_date is None or date.fromisoformat(departure_date[:10]) != query.travel_date:
        raise ValueError("Unmatched departure date.")
    for previous, current in zip(legs, legs[1:], strict=False):
        if previous.arrival_at and current.departure_at:
            if current.departure_at < previous.arrival_at:
                raise ValueError("Unordered itinerary.")
    missing = [
        "price_fen",
        "price_basis",
        "price_scope",
        "passenger_count",
        "remaining_seats",
        "availability",
        "included_charges",
    ]
    if len(legs) == 1 and first.service_number is None:
        missing.append("service_number")
    if first.departure_at is None:
        missing.append("departure_at")
    if last.arrival_at is None:
        missing.append("arrival_at")
    try:
        booking_url = validate_fare_booking_url(_text(item.get("jumpUrl"), 4096))
    except ValueError:
        booking_url = None
    return FareOffer(
        offer_id=f"flyai-{index}",
        source_id=FlyAITrainFareProvider.provider_id,
        mode="rail",
        travel_date=query.travel_date,
        segments=legs,
        service_number=first.service_number if len(legs) == 1 else None,
        origin_name=first.origin_name,
        destination_name=last.destination_name,
        departure_at=first.departure_at,
        arrival_at=last.arrival_at,
        departure_timezone=first.departure_timezone,
        arrival_timezone=last.arrival_timezone,
        price_basis="unknown",
        price_scope="unknown",
        evidence_state=EvidenceState.VERIFIED,
        missing_fields=missing,
        booking_url=booking_url,
    )


def map_train_result(
    payload: object, query: FareQuery, *, request_id: UUID, now: datetime
) -> FareResult:
    if not isinstance(payload, dict) or type(payload.get("status")) is not int:
        raise ValueError("Invalid business response.")
    if payload["status"] != 0:
        raise ValueError("Unknown business failure.")
    data = payload.get("data")
    raw_items = data.get("itemList") if isinstance(data, dict) else None
    if not isinstance(raw_items, list) or len(raw_items) > 10:
        raise ValueError("Invalid result list.")
    items = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        try:
            items.append(_offer(raw, index, query))
        except ValueError, TypeError, ValidationError:
            continue
    if raw_items and not items:
        raise ValueError("No valid railway result.")
    hint = _text(payload.get("systemMessage"), 2000) or _text(data.get("systemMessage"), 2000)
    return FareResult(
        state=ResultState.PARTIAL if items else ResultState.EMPTY,
        items=items,
        sources=[
            SourceRef(
                source_id=FlyAITrainFareProvider.provider_id,
                display_name="飞猪 FlyAI 铁路查询",
                url="https://flyai.open.fliggy.com/",
                retrieved_at=now,
                attribution="基于飞猪 FlyAI 实时搜索；非按人数报价，班次与席位以供应商详情为准。",
                evidence_state=EvidenceState.VERIFIED,
            )
        ],
        queried_at=now,
        request_id=request_id,
        platform_hint=hint,
    )
