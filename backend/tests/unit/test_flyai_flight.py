from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.transport.contracts import FareQuery
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.providers.flyai_flight import FlyAIFlightFareProvider, map_flight_result
from app.modules.transport.runtime import create_transport_service
from tests.unit.test_flyai_provider import Executor

NOW = datetime(2026, 11, 12, tzinfo=UTC)


def query(**changes):
    return FareQuery.model_validate(
        {
            "origin": {"display_name": "上海", "place_id": "PVG"},
            "destination": {"display_name": "北京", "place_id": "PEK"},
            "mode": "flight",
            "travel_date": "2026-11-14",
            "passenger_count": 2,
            "child_count": 1,
            **changes,
        }
    )


def payload():
    return {
        "status": 0,
        "data": {
            "itemList": [
                {
                    "adultPrice": "¥400.0",
                    "journeys": [
                        {
                            "segments": [
                                {
                                    "transportType": "飞机",
                                    "depStationCode": "PVG",
                                    "arrStationCode": "PEK",
                                    "depStationName": "浦东国际机场",
                                    "arrStationName": "首都国际机场",
                                    "depDateTime": "2026-11-14 08:00:00",
                                    "arrDateTime": "2026-11-14 10:00:00",
                                    "marketingTransportNo": "TEST123",
                                    "seatClassName": "经济舱",
                                }
                            ]
                        }
                    ],
                }
            ]
        },
        "systemMessage": "synthetic hint",
    }


def test_maps_airports_and_times_without_inventing_party_or_child_price():
    result = map_flight_result(payload(), query(), request_id=uuid4(), now=NOW)
    item = result.items[0]
    assert result.state == "partial" and item.mode == "flight"
    assert item.departure_at == datetime(2026, 11, 14, tzinfo=UTC)
    assert item.price_fen is None and item.passenger_count is None
    assert item.availability == "unknown" and item.segments[0].seat_class == "经济舱"
    assert result.platform_hint == "synthetic hint"


@pytest.mark.parametrize(
    "field,value",
    [("depStationCode", "SHA"), ("depDateTime", "2026-11-15 08:00:00"), ("transportType", "火车")],
)
def test_rejects_wrong_airport_day_or_transport(field, value):
    body = payload()
    body["data"]["itemList"][0]["journeys"][0]["segments"][0][field] = value
    with pytest.raises(ValueError):
        map_flight_result(body, query(), request_id=uuid4(), now=NOW)


def test_no_query_without_explicit_flight_provider_and_key():
    settings = Settings(
        _env_file=None, transport_train_provider="flyai", transport_flyai_api_key="synthetic-key"
    )
    executor = Executor(payload())
    service = create_transport_service(settings, flyai_executor=executor)
    assert service.search_fares(query(), request_id=uuid4()).state == "unconfigured"
    assert executor.calls == []


def test_explicit_flight_provider_and_permissions():
    executor = Executor(payload(), status=403)
    provider = FlyAIFlightFareProvider(
        api_key=SecretStr("synthetic-key"), executor=executor, now=lambda: NOW
    )
    with pytest.raises(TransportProviderError) as error:
        provider.search_fares(query(), request_id=uuid4())
    assert error.value.status == "policy_unavailable"
    assert executor.calls[0][0].mode == "flight"


def test_no_airport_code_rejected_before_executor():
    executor = Executor(payload())
    provider = FlyAIFlightFareProvider(
        api_key=SecretStr("synthetic-key"), executor=executor, now=lambda: NOW
    )
    with pytest.raises(TransportProviderError) as error:
        provider.search_fares(query(origin={"display_name": "上海"}), request_id=uuid4())
    assert error.value.status == "no_coverage" and not executor.calls


@pytest.mark.parametrize("invalid", ["disconnected", "unordered", "arrival-before-departure"])
def test_rejects_invalid_connecting_itinerary(invalid):
    body = payload()
    rows = body["data"]["itemList"][0]["journeys"][0]["segments"]
    rows[0]["arrStationCode"] = "SHA"
    second = dict(
        rows[0],
        depStationCode="SHA",
        arrStationCode="PEK",
        depDateTime="2026-11-14 11:00:00",
        arrDateTime="2026-11-14 13:00:00",
    )
    rows.append(second)
    if invalid == "disconnected":
        second["depStationCode"] = "CAN"
    elif invalid == "unordered":
        second["depDateTime"] = "2026-11-14 09:00:00"
    else:
        second["arrDateTime"] = "2026-11-14 10:30:00"
    with pytest.raises(ValueError):
        map_flight_result(body, query(), request_id=uuid4(), now=NOW)


def test_unknown_airport_timezone_keeps_naive_times_unknown():
    body = payload()
    body["data"]["itemList"][0]["journeys"][0]["segments"][0]["depStationCode"] = "ZZZ"
    result = map_flight_result(
        body, query(origin={"display_name": "机场", "place_id": "ZZZ"}), request_id=uuid4(), now=NOW
    )
    assert result.items[0].departure_at is None
    assert result.items[0].departure_timezone is None
    assert "departure_at" in result.items[0].missing_fields


def test_flight_only_configuration_does_not_enable_rail():
    executor = Executor(payload())
    service = create_transport_service(
        Settings(
            _env_file=None, transport_fare_provider="flyai", transport_flyai_api_key="synthetic-key"
        ),
        flyai_executor=executor,
    )
    assert service.search_fares(query(mode="rail"), request_id=uuid4()).state == "unconfigured"
    assert not executor.calls
