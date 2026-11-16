from __future__ import annotations

import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def query(mode="walking", **changes):
    return {
        "origin": {"display_name": "杭州市杭州东站"},
        "destination": {"display_name": "杭州市西湖"},
        "mode": mode,
        **changes,
    }


def settings(configured=True):
    return Settings(
        _env_file=None, env="test", amap_api_key="route-test-key-never-log" if configured else None
    )


def response_for(request, mode="walking"):
    if request.url.path == "/v3/geocode/geo":
        return {"status": "1", "geocodes": [{"location": "120.1,30.2", "citycode": "0571"}]}
    if request.url.path == "/v3/assistant/coordinate/convert":
        assert request.url.params["coordsys"] == "gps"
        return {"status": "1", "locations": "120.106,30.204"}
    if request.url.path == "/v3/geocode/regeo":
        return {"status": "1", "regeocode": {"addressComponent": {"citycode": "0571"}}}
    assert (
        request.url.path
        == "/v3/direction/"
        + {
            "walking": "walking",
            "taxi": "driving",
            "transit": "transit/integrated",
        }[mode]
    )
    path = {
        "distance": "3200",
        "duration": "1800",
        "steps": [
            {
                "instruction": "沿测试路向前",
                "distance": "3200",
                "duration": "1800",
                "polyline": "120.1,30.2;120.2,30.3",
            }
        ],
    }
    if mode == "transit":
        assert request.url.params["city"] == "0571"
        assert request.url.params["cityd"] == "0571"
        path["segments"] = [
            {
                "walking": {"steps": [{"instruction": "步行至测试站"}]},
                "bus": {
                    "buslines": [
                        {
                            "name": "地铁测试线",
                            "type": "地铁线路",
                            "departure_stop": {"name": "测试站 A"},
                            "arrival_stop": {"name": "测试站 B"},
                        },
                        {"name": "备选线路不应作为连续分段"},
                    ]
                },
            }
        ]
    return {
        "status": "1",
        "route": {
            "transits" if mode == "transit" else "paths": [path],
        },
    }


@pytest.mark.parametrize("mode", ["walking", "taxi", "transit"])
def test_amap_routes_registered_and_return_reference_data_without_prices(mode, caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json=response_for(r, mode)),
            )
        ) as client,
        TestClient(create_app(settings(), amap_client=client)) as api,
    ):
        response = api.post("/api/transport/routes/search", json=query(mode))
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "partial"
    route = body["items"][0]
    assert route["mode"] == mode
    assert route["distance_m"] == 3200
    assert route["duration_seconds"] == 1800
    assert route["duration_basis"] == "typical_estimate"
    assert route["evidence_state"] == "estimate"
    assert route["fare_amount_fen"] is None
    assert route["geometry_points"] is None  # GCJ-02 must not be labelled WGS84.
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["sources"][0]["source_id"] == route["source_id"]
    if mode == "transit":
        assert len(route["steps"]) == 2
        assert route["steps"][1]["step_mode"] == "subway"
        assert "测试站 A" in route["steps"][1]["instruction"]
    assert "route-test-key-never-log" not in response.text + caplog.text


def test_wgs84_coordinates_are_converted_and_transit_time_is_local():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_for(request, "transit"))

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        TestClient(
            create_app(settings(), amap_client=client),
        ) as api,
    ):
        response = api.post(
            "/api/transport/routes/search",
            json=query(
                "transit",
                origin={"display_name": "当前位置", "latitude": 30.2, "longitude": 120.1},
                depart_at="2026-11-18T01:30:00Z",
            ),
        )
    assert response.json()["state"] == "partial"
    params = calls[-1].url.params
    assert params["origin"] == "120.106,30.204"
    assert params["date"] == "2026-11-18"
    assert params["time"] == "09:30"


@pytest.mark.parametrize(
    ("data", "state"),
    [
        (
            {"status": "0", "infocode": "10001", "info": "private upstream text"},
            "policy_unavailable",
        ),
        ({"status": "0", "infocode": "10003"}, "rate_limited"),
        ({"status": "1", "geocodes": []}, "no_coverage"),
        ({"status": "1", "geocodes": [{}, {}]}, "no_coverage"),
        ({"unexpected": "payload"}, "unavailable"),
    ],
)
def test_provider_errors_remain_safe_and_no_fake_routes(data, state):
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json=data),
            )
        ) as client,
        TestClient(create_app(settings(), amap_client=client)) as api,
    ):
        response = api.post("/api/transport/routes/search", json=query())
    assert response.json()["state"] == state
    assert response.json()["items"] == []
    assert "private upstream text" not in response.text
    assert "route-test-key-never-log" not in response.text


def test_unconfigured_route_never_calls_network():
    def handler(request):
        pytest.fail("Unconfigured route must not issue a network request")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        TestClient(
            create_app(settings(False), amap_client=client),
        ) as api,
    ):
        assert (
            api.post("/api/transport/routes/search", json=query()).json()["state"] == "unconfigured"
        )


def test_empty_routes_are_not_provider_failure():
    def handler(request):
        data = response_for(request)
        if "route" in data:
            data["route"]["paths"] = []
        return httpx.Response(200, json=data)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        TestClient(
            create_app(settings(), amap_client=client),
        ) as api,
    ):
        body = api.post("/api/transport/routes/search", json=query()).json()
    assert body["state"] == "empty"
    assert body["items"] == []
