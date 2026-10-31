from __future__ import annotations

import logging
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TOKEN = "integration-access-token-never-log"
CLIENT_ID = "integration-client-id-never-log"
CLIENT_SECRET = "integration-client-secret-never-log"


def _settings(*, configured: bool) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "env": "test",
        "allowed_origins": ("http://localhost:4173",),
    }
    if configured:
        values.update(
            transport_fare_provider="amadeus",
            transport_amadeus_env="test",
            transport_amadeus_client_id=CLIENT_ID,
            transport_amadeus_client_secret=CLIENT_SECRET,
        )
    return Settings(**values)


def _fare_query() -> dict[str, object]:
    return {
        "origin": {"display_name": "private-origin-sentinel", "place_id": "SHA"},
        "destination": {"display_name": "private-destination-sentinel", "place_id": "HGH"},
        "mode": "flight",
        "travel_date": "2026-11-10",
        "passenger_count": 2,
    }


def _offer() -> dict[str, object]:
    return {
        "itineraries": [
            {
                "segments": [
                    {
                        "departure": {"iataCode": "SHA", "at": "2026-11-10T08:00:00"},
                        "arrival": {"iataCode": "HGH", "at": "2026-11-10T09:10:00"},
                        "carrierCode": "MU",
                        "number": "1234",
                    }
                ]
            }
        ],
        "price": {"currency": "CNY", "total": "355.34"},
        "travelerPricings": [
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "177.67"}},
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "177.67"}},
        ],
        "numberOfBookableSeats": 3,
    }


def _token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": TOKEN, "token_type": "Bearer", "expires_in": 300},
    )


def test_default_transport_api_is_unconfigured_and_never_uses_network() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("unconfigured transport must not issue a request")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        app = create_app(_settings(configured=False), transport_amadeus_client=client)
        assert app.state.transport_service.fare_provider is None
        with TestClient(app) as test_client:
            response = test_client.post("/api/transport/fares/search", json=_fare_query())

    assert response.status_code == 200
    assert response.json()["state"] == "unconfigured"
    assert response.json()["items"] == []
    assert calls == []


def test_configured_amadeus_provider_is_wired_through_api_with_mock_transport(caplog) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert str(request.url) == "https://test.api.amadeus.com/v1/security/oauth2/token"
            form = parse_qs(request.content.decode())
            assert form["grant_type"] == ["client_credentials"]
            assert form["client_id"] == [CLIENT_ID]
            assert form["client_secret"] == [CLIENT_SECRET]
            return _token_response()

        assert str(request.url).split("?")[0] == (
            "https://test.api.amadeus.com/v2/shopping/flight-offers"
        )
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert dict(request.url.params) == {
            "originLocationCode": "SHA",
            "destinationLocationCode": "HGH",
            "departureDate": "2026-11-10",
            "adults": "2",
            "currencyCode": "CNY",
            "max": "20",
        }
        return httpx.Response(200, json={"data": [_offer()]})

    caplog.set_level(logging.INFO, logger="app.transport")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        app = create_app(_settings(configured=True), transport_amadeus_client=client)
        with TestClient(app) as test_client:
            response = test_client.post("/api/transport/fares/search", json=_fare_query())

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "partial"
    assert body["request_id"] == response.headers["x-request-id"]
    assert len(requests) == 2
    offer = body["items"][0]
    assert offer["mode"] == "flight"
    assert offer["price_fen"] == 35534
    assert offer["price_basis"] == "party_total"
    assert offer["price_scope"] == "entire_journey"
    assert offer["remaining_seats"] == 3
    assert offer["passenger_count"] == 2
    assert offer["service_number"] == "MU1234"
    assert offer["source_id"] == "amadeus.flight-offers"
    assert body["sources"][0]["source_id"] == "amadeus.flight-offers"
    assert "price_scope" not in offer["missing_fields"]
    assert "private-origin-sentinel" not in caplog.text
    assert "private-destination-sentinel" not in caplog.text
    assert CLIENT_SECRET not in caplog.text
    assert TOKEN not in caplog.text


def test_amadeus_rate_limit_is_returned_as_a_stable_public_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(429, text="private upstream body")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        app = create_app(_settings(configured=True), transport_amadeus_client=client)
        with TestClient(app) as test_client:
            response = test_client.post("/api/transport/fares/search", json=_fare_query())

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "rate_limited"
    assert body["items"] == []
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["retryable"] is True
    assert body["request_id"] == body["error"]["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]
    assert "private upstream body" not in response.text
    assert "private-origin-sentinel" not in response.text
    assert "private-destination-sentinel" not in response.text


def test_flyai_train_is_wired_independently_of_flights(caplog):
    import json
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.modules.transport.providers.flyai import CliOutput

    day = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date().isoformat()
    key = "synthetic-train-integration-key"
    calls = []

    class TrainExecutor:
        def run(self, query, **kwargs):
            calls.append(query)
            assert kwargs["key"] == key
            body = {
                "status": 0,
                "systemMessage": "铁路提示",
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
                                            "depDateTime": day + " 08:00:00",
                                            "arrDateTime": day + " 09:00:00",
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
            return CliOutput(0, json.dumps(body).encode(), 200, 1, True)

    settings = Settings(
        _env_file=None, env="test", transport_train_provider="flyai", transport_flyai_api_key=key
    )
    with TestClient(create_app(settings, transport_flyai_executor=TrainExecutor())) as client:
        response = client.post(
            "/api/transport/fares/search",
            json={
                "origin": {"display_name": "上海"},
                "destination": {"display_name": "杭州"},
                "mode": "rail",
                "travel_date": day,
                "passenger_count": 2,
                "child_count": 0,
            },
        )
        flight = client.post("/api/transport/fares/search", json=_fare_query())
    body = response.json()
    assert response.status_code == 200 and body["state"] == "partial"
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["items"][0]["price_fen"] is None
    assert body["items"][0]["passenger_count"] is None
    assert body["items"][0]["segments"][0]["seat_class"] == "二等座"
    assert body["platform_hint"] == "铁路提示"
    assert body["sources"][0]["source_id"] == "flyai.search-train"
    assert flight.json()["state"] == "unconfigured" and len(calls) == 1
    assert key not in caplog.text + response.text
