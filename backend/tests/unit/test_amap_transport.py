from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.transport.contracts import RouteQuery
from app.modules.transport.providers.amap import AmapRouteProvider, _RequestBudget
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.runtime import create_transport_service


def query(mode="walking", **changes):
    return RouteQuery.model_validate(
        {
            "origin": {"display_name": "人民广场"},
            "destination": {"display_name": "外滩"},
            "mode": mode,
            "city_id": "shanghai",
            **changes,
        }
    )


def client_for(*, ambiguous=False, status=None, missing=False):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "restapi.amap.com"
        if status:
            return httpx.Response(status)
        params = request.url.params
        path = request.url.path
        data = {"status": "1", "infocode": "10000"}
        if path == "/v5/place/text":
            location = "121.49,31.241" if params["keywords"] == "外滩" else "121.4737,31.2304"
            data["pois"] = [{"name": params["keywords"], "location": location, "adcode": "310101"}]
            if ambiguous:
                data["pois"].append(dict(data["pois"][0]))
        elif path == "/v3/assistant/coordinate/convert":
            data["locations"] = "121.4737,31.2304"
            assert params["coordsys"] == "gps"
        else:
            path_data = {} if missing else {"distance": "1250", "duration": "900"}
            path_data["steps"] = [{"instruction": "沿道路步行", "distance": "1250"}]
            if "transit" in path:
                data["route"] = {
                    "transits": [
                        {
                            **path_data,
                            "cost": "2.00",
                            "segments": [
                                {
                                    "bus": {
                                        "buslines": [
                                            {
                                                "name": "地铁2号线",
                                                "type": "地铁线路",
                                                "duration": "300",
                                                "distance": "1000",
                                            }
                                        ]
                                    }
                                }
                            ],
                        }
                    ]
                }
            else:
                data["route"] = {"paths": [path_data], "taxi_cost": "18.50"}
        return httpx.Response(200, json=data)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def provider(client):
    return AmapRouteProvider(
        Settings(_env_file=None, amap_api_key="synthetic-amap-key"), client=client
    )


@pytest.mark.parametrize("mode", ["walking", "taxi", "transit"])
def test_real_route_fields_and_estimate_semantics(mode):
    client, calls = client_for()
    result = provider(client).search_route(query(mode), request_id=uuid4())
    item = result.items[0]
    assert item.mode == mode and item.distance_m == 1250 and item.duration_seconds == 900
    assert item.duration_basis == "typical_estimate"
    assert item.geometry_points is None  # GCJ02 is never relabelled as WGS84.
    assert "geometry_points" in item.missing_fields
    assert len(calls) == 3
    if mode == "transit":
        assert item.steps[0].step_mode == "subway" and item.fare_amount_fen == 200
    elif mode == "taxi":
        assert item.fare_amount_fen == 1850 and item.fare_evidence_state == "estimate"
        assert item.fare_basis == "meter_estimate"
    else:
        assert item.fare_amount_fen is None


def test_wgs84_input_uses_official_conversion_before_direction_query():
    client, calls = client_for()
    place = {"display_name": "GPS起点", "latitude": 31.23, "longitude": 121.47}
    provider(client).search_route(query(origin=place), request_id=uuid4())
    assert calls[0].url.path == "/v3/assistant/coordinate/convert"
    assert list(map(float, calls[-1].url.params["origin"].split(","))) == [121.4737, 31.2304]


def test_ambiguous_places_and_missing_city_stop_before_directions():
    client, calls = client_for(ambiguous=True)
    with pytest.raises(TransportProviderError) as error:
        provider(client).search_route(query(), request_id=uuid4())
    assert error.value.status == "no_coverage" and len(calls) == 1
    client, calls = client_for()
    with pytest.raises(TransportProviderError):
        provider(client).search_route(query(city_id=None), request_id=uuid4())
    assert not calls


@pytest.mark.parametrize(
    "status,expected", [(403, "policy_unavailable"), (429, "rate_limited"), (500, "unavailable")]
)
def test_safe_http_errors(status, expected):
    client, _ = client_for(status=status)
    with pytest.raises(TransportProviderError) as error:
        provider(client).search_route(query(), request_id=uuid4())
    assert error.value.status == expected


def test_absent_numbers_stay_unknown_and_route_activation_is_explicit():
    client, _ = client_for(missing=True)
    result = provider(client).search_route(query(), request_id=uuid4())
    assert result.items[0].distance_m is None
    assert result.items[0].duration_basis == "unknown"
    service = create_transport_service(
        Settings(_env_file=None, amap_api_key="synthetic-key"), amap_client=client
    )
    assert service.search_route(query(), request_id=uuid4()).state == "unconfigured"


def test_query_locations_and_key_are_not_logged(caplog):
    client, _ = client_for()
    with caplog.at_level("INFO", logger="httpx"):
        provider(client).search_route(query(), request_id=uuid4())
    assert "synthetic-amap-key" not in caplog.text
    assert "keywords=" not in caplog.text and "origin=" not in caplog.text


@pytest.mark.parametrize("mode", ["walking", "taxi", "transit"])
def test_application_constructs_route_provider_with_injected_client(mode):
    client, calls = client_for()
    app = create_app(
        Settings(_env_file=None, transport_route_provider="amap", amap_api_key="synthetic-key"),
        amap_client=client,
    )
    response = TestClient(app).post(
        "/api/transport/routes/search", json=query(mode).model_dump(mode="json")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "partial" and len(body["items"]) == 1
    assert body["items"][0]["mode"] == mode and len(calls) == 3
    assert body["request_id"] == response.headers["x-request-id"]


def test_request_count_and_deadline_stop_before_network(monkeypatch):
    client, calls = client_for()
    budget = _RequestBudget(Settings(_env_file=None, amap_api_key="synthetic-key"), client)
    budget.calls = 8
    with pytest.raises(TransportProviderError):
        budget.get("/v5/place/text", {})
    budget.calls = 0
    monkeypatch.setattr(
        "app.modules.transport.providers.amap.time.monotonic", lambda: budget.deadline
    )
    with pytest.raises(TransportProviderError):
        budget.get("/v5/place/text", {})
    assert not calls


@pytest.mark.parametrize("failure", ["timeout", "oversize", "redirect"])
def test_upstream_limits_become_safe_unavailable_state(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-location", request=request)
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com"})
        return httpx.Response(200, content=b" " * (512 * 1024 + 1))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TransportProviderError) as error:
        provider(client).search_route(query(), request_id=uuid4())
    assert error.value.status == "unavailable" and len(calls) == 1


def test_literal_place_match_takes_precedence_over_city_prefix_alias():
    base, calls = client_for()

    def handler(request):
        response = base.send(request)
        if request.url.path == "/v5/place/text":
            data = response.json()
            data["pois"].append(
                {**data["pois"][0], "name": "上海" + request.url.params["keywords"]}
            )
            return httpx.Response(200, json=data)
        return response

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = provider(client).search_route(query(), request_id=uuid4())
    assert len(calls) == 3 and result.items[0].origin_name == "人民广场"


def test_route_ambiguity_api_explains_how_to_refine_input():
    client, _ = client_for(ambiguous=True)
    app = create_app(
        Settings(_env_file=None, transport_route_provider="amap", amap_api_key="synthetic-key"),
        amap_client=client,
    )
    body = (
        TestClient(app)
        .post("/api/transport/routes/search", json=query().model_dump(mode="json"))
        .json()
    )
    assert body["state"] == "no_coverage" and "具体站点" in body["error"]["message"]
