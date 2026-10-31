from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.modules.transport.contracts import FareQuery, validate_fare_booking_url
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.providers.flyai import (
    CliOutput,
    FlyAITrainFareProvider,
    map_train_result,
)

NOW = datetime(2026, 10, 31, tzinfo=UTC)
KEY = "synthetic-flyai-key-never-log"


def query(**updates):
    return FareQuery.model_validate(
        {
            "origin": {"display_name": "上海"},
            "destination": {"display_name": "杭州"},
            "mode": "rail",
            "travel_date": "2026-11-01",
            "passenger_count": 3,
            "child_count": 1,
            **updates,
        }
    )


def payload():
    return {
        "status": 0,
        "data": {
            "itemList": [
                {
                    "journeys": [
                        {
                            "segments": [
                                {
                                    "transportType": "火车",
                                    "depCityName": "上海",
                                    "depStationName": "上海虹桥",
                                    "arrCityName": "杭州",
                                    "arrStationName": "杭州东",
                                    "depDateTime": "2026-11-01 08:00:00",
                                    "arrDateTime": "2026-11-01 09:00:00",
                                    "marketingTransportNo": "G-TEST",
                                    "seatClassName": "二等座",
                                }
                            ]
                        }
                    ],
                    "jumpUrl": "https://www.fliggy.com/train?fixture=1",
                }
            ]
        },
    }


class Executor:
    def __init__(self, body=None, *, status=200, exit_code=0, authenticated=True, count=1):
        self.calls = []
        self.output = CliOutput(
            exit_code,
            json.dumps(payload() if body is None else body, ensure_ascii=False).encode(),
            status,
            count,
            authenticated,
        )

    def run(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.output


def provider(executor, key=KEY):
    return FlyAITrainFareProvider(api_key=SecretStr(key), executor=executor, now=lambda: NOW)


def mapped(body=None):
    return map_train_result(
        payload() if body is None else body, query(), request_id=uuid4(), now=NOW
    )


def test_direct_mapping_preserves_stations_seat_and_unknown_facts():
    result = mapped()
    assert result.state == "partial"
    item = result.items[0]
    assert item.departure_at == datetime(2026, 11, 1, 0, tzinfo=UTC)
    assert item.departure_timezone == "Asia/Shanghai"
    assert item.segments[0].seat_class == "二等座"
    assert item.origin_name == "上海虹桥"
    assert item.booking_url == "https://www.fliggy.com/train?fixture=1"
    assert item.price_fen is None and item.passenger_count is None
    assert item.remaining_seats is None and item.availability == "unknown"
    assert item.price_basis == item.price_scope == "unknown"
    assert "price_fen" in item.missing_fields
    assert item.source_id == result.sources[0].source_id


@pytest.mark.parametrize("price", [0, 123, "123.45", "¥123", {"amount": 100}])
def test_unconfirmed_price_semantics_never_become_a_yuan_amount(price):
    body = payload()
    body["data"]["itemList"][0]["adultPrice"] = price
    assert mapped(body).items[0].price_fen is None


def test_transfer_across_midnight_keeps_both_segments_without_a_through_number():
    body = payload()
    item = body["data"]["itemList"][0]
    legs = item["journeys"][0]["segments"]
    second = copy.deepcopy(legs[0])
    legs[0].update(
        arrCityName="苏州",
        arrStationName="苏州北",
        depDateTime="2026-11-01 23:00:00",
        arrDateTime="2026-11-01 23:45:00",
    )
    second.update(
        depCityName="苏州",
        depStationName="苏州北",
        depDateTime="2026-11-02 00:10:00",
        arrDateTime="2026-11-02 01:00:00",
    )
    legs.append(second)
    offer = mapped(body).items[0]
    assert len(offer.segments) == 2 and offer.service_number is None
    assert offer.arrival_at == datetime(2026, 11, 1, 17, tzinfo=UTC)


@pytest.mark.parametrize(
    "field,value",
    [
        ("transportType", "飞机"),
        ("depCityName", "北京"),
        ("depDateTime", "2026-11-02 08:00:00"),
        ("arrDateTime", "2026-11-01 07:00:00"),
    ],
)
def test_wrong_mode_date_endpoint_or_time_order_rejected(field, value):
    body = payload()
    body["data"]["itemList"][0]["journeys"][0]["segments"][0][field] = value
    with pytest.raises(ValueError):
        mapped(body)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://www.fliggy.com/",
        "https://fliggy.com.evil.test/",
        "https://user@fliggy.com/",
        "https://fliggy.com:444/",
        "https://fliggy.com/\\evil",
        "https://fliggy.com/ bad",
    ],
)
def test_untrusted_jump_links_removed(url):
    with pytest.raises(ValueError):
        validate_fare_booking_url(url)
    body = payload()
    body["data"]["itemList"][0]["jumpUrl"] = url
    assert mapped(body).items[0].booking_url is None


def test_empty_results_and_platform_hint():
    result = mapped({"status": 0, "data": {"itemList": []}, "systemMessage": "<b>平台提示</b>"})
    assert result.state == "empty" and result.items == []
    assert result.platform_hint == "<b>平台提示</b>"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": True},
        {"status": 1},
        {"status": 0, "data": {}},
        {"status": 0, "data": {"itemList": [None]}},
    ],
)
def test_malformed_business_response_unavailable(body):
    executor = Executor(body)
    with pytest.raises(TransportProviderError) as exc:
        provider(executor).search_fares(query(), request_id=uuid4())
    assert exc.value.status == "unavailable"


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "policy_unavailable"),
        (403, "policy_unavailable"),
        (429, "rate_limited"),
        (500, "unavailable"),
        (302, "unavailable"),
    ],
)
def test_http_failures_are_safe_states(status, expected):
    with pytest.raises(TransportProviderError) as exc:
        provider(Executor(status=status)).search_fares(query(), request_id=uuid4())
    assert exc.value.status == expected
    assert KEY not in str(exc.value)


@pytest.mark.parametrize("options", [{"exit_code": 1}, {"authenticated": False}, {"count": 2}])
def test_failed_cli_or_untrusted_audit_rejected(options):
    with pytest.raises(TransportProviderError):
        provider(Executor(**options)).search_fares(query(), request_id=uuid4())


@pytest.mark.parametrize(
    "updates",
    [
        {"mode": "flight"},
        {"travel_date": "2026-10-31"},
        {"origin": {"display_name": "上海\n--debug"}},
    ],
)
def test_ineligible_queries_do_not_launch_cli(updates):
    executor = Executor()
    with pytest.raises(TransportProviderError):
        provider(executor).search_fares(query(**updates), request_id=uuid4())
    assert executor.calls == []


def test_blank_key_never_uses_cli_trial_fallback():
    executor = Executor()
    with pytest.raises(TransportProviderError) as exc:
        provider(executor, key=" ").search_fares(query(), request_id=uuid4())
    assert exc.value.status == "unconfigured" and not executor.calls


def test_secret_echo_and_oversized_stdout_rejected():
    executor = Executor({"status": 0, "systemMessage": KEY, "data": {"itemList": []}})
    with pytest.raises(TransportProviderError):
        provider(executor).search_fares(query(), request_id=uuid4())
    executor.output = CliOutput(0, b"x" * (1024 * 1024 + 1), 200, 1, True)
    with pytest.raises(TransportProviderError):
        provider(executor).search_fares(query(), request_id=uuid4())


def test_config_accepts_official_key_alias_and_requires_explicit_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_TRANSPORT_FLYAI_API_KEY", raising=False)
    monkeypatch.delenv("FLYAI_API_KEY", raising=False)
    config = tmp_path / "test.env"
    config.write_text("FLYAI_API_KEY=" + KEY + "\nAPP_TRANSPORT_TRAIN_PROVIDER=flyai\n")
    settings = Settings(_env_file=config)
    assert settings.transport_flyai_configured
    assert settings.transport_flyai_api_key.get_secret_value() == KEY
    assert KEY not in settings.model_dump_json()
    assert not Settings(_env_file=None, transport_train_provider="flyai").transport_flyai_configured
    assert not Settings(_env_file=None, transport_flyai_api_key=KEY).transport_flyai_configured
    assert not Settings(
        _env_file=None, transport_train_provider="", transport_flyai_api_key=""
    ).transport_flyai_configured


@pytest.mark.parametrize(
    "updates",
    [
        {"transport_flyai_timeout_seconds": 46},
        {"transport_flyai_timeout_seconds": float("nan")},
        {"transport_train_provider": "other"},
        {"transport_flyai_max_response_bytes": 1024 * 1024 + 1},
    ],
)
def test_config_rejects_invalid_boundaries(updates):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **updates)


@pytest.mark.parametrize("value", ["2026-11-01", "not a timestamp", "2026-11-01 25:00:00"])
def test_invalid_arrival_times_remain_unknown(value):
    body = payload()
    body["data"]["itemList"][0]["journeys"][0]["segments"][0]["arrDateTime"] = value
    offer = mapped(body).items[0]
    assert offer.arrival_at is None and "arrival_at" in offer.missing_fields
