from __future__ import annotations

import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

KEY = "fixture-amap-server-key"
PNG = b"\x89PNG\r\n\x1a\nfixture"


def poi(**updates) -> dict:
    return {
        "id": "B001",
        "name": "测试地点",
        "adcode": "310101",
        "address": "上海市测试路",
        "type": "风景名胜;公园",
        "location": "121.47,31.23",
        "business": {"tel": "021-12345678"},
        **updates,
    }


def client_for(handler, *, key=KEY) -> TestClient:
    settings = Settings(_env_file=None, amap_api_key=key)
    upstream = httpx.Client(transport=httpx.MockTransport(handler))
    return TestClient(create_app(settings, amap_client=upstream))


@pytest.mark.parametrize(
    "category,types",
    [
        ("hotels", "100000"),
        ("activities", "080000"),
        ("attractions", "110000"),
        ("maps", "110000"),
    ],
)
def test_registered_searches_are_city_limited_and_share_server_key(category, types, caplog):
    def handler(request):
        assert str(request.url).startswith("https://restapi.amap.com/v5/place/text?")
        assert request.url.params["key"] == KEY
        assert request.url.params["region"] == "310000"
        assert request.url.params["city_limit"] == "true"
        assert request.url.params["types"] == types
        assert request.url.params["page_size"] == "10"
        return httpx.Response(200, json={"status": "1", "count": "1", "pois": [poi()]})

    caplog.set_level(logging.INFO, logger="httpx")
    with client_for(handler) as client:
        response = client.post(f"/api/{category}/search", json={"city_id": "shanghai"})
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "live"
    assert data["category"] == category
    assert data["items"][0]["location"] == {
        "longitude": 121.47,
        "latitude": 31.23,
        "coordinate_system": "GCJ02",
    }
    assert data["items"][0]["telephone"] == "021-12345678"
    assert "price" not in data["items"][0]
    assert KEY not in response.text
    assert KEY not in caplog.text
    assert data["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("category", ["hotels", "activities", "attractions", "maps"])
def test_unconfigured_never_calls_amap(category):
    def handler(request):
        pytest.fail("Missing credentials must not call the supplier")

    with client_for(handler, key=None) as client:
        response = client.post(f"/api/{category}/search", json={"city_id": "shanghai"})
        assert response.json()["state"] == "unconfigured"
        assert response.json()["items"] == []


@pytest.mark.parametrize(
    "infocode,state",
    [
        ("10001", "policy_unavailable"),
        ("10009", "policy_unavailable"),
        ("10003", "rate_limited"),
        ("10014", "rate_limited"),
        ("20000", "unavailable"),
    ],
)
def test_supplier_application_errors_do_not_become_empty_results(infocode, state):
    def handler(request):
        return httpx.Response(200, json={"status": "0", "infocode": infocode, "info": KEY})

    with client_for(handler) as client:
        response = client.post("/api/hotels/search", json={"city_id": "shanghai"})
    assert response.json()["state"] == state
    assert KEY not in response.text


@pytest.mark.parametrize(
    "status,state",
    [
        (429, "rate_limited"),
        (403, "policy_unavailable"),
        (500, "unavailable"),
        (302, "unavailable"),
    ],
)
def test_supplier_http_errors(status, state):
    with client_for(lambda _: httpx.Response(status)) as client:
        result = client.post("/api/activities/search", json={"city_id": "shanghai"}).json()
    assert result["state"] == state


@pytest.mark.parametrize(
    "body", [b"not json", b"[]", b'{"status":"1"}', pytest.param(b"x" * 524_289, id="oversized")]
)
def test_malformed_and_oversized_payloads_are_unavailable(body):
    with client_for(lambda _: httpx.Response(200, content=body)) as client:
        result = client.post("/api/attractions/search", json={"city_id": "shanghai"}).json()
    assert result["state"] == "unavailable"


def test_missing_coordinates_retained_but_out_of_city_and_invalid_rows_removed():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    poi(location=[], address=[], business=[]),
                    poi(id="B002", adcode="330100"),
                    {},
                ],
            },
        )

    with client_for(handler) as client:
        result = client.post("/api/attractions/search", json={"city_id": "shanghai"}).json()
    assert result["state"] == "partial"
    assert len(result["items"]) == 1
    assert result["items"][0]["location"] is None
    assert result["items"][0]["address"] is None
    assert result["items"][0]["telephone"] is None


def test_v5_page_count_is_not_treated_as_total_count():
    def handler(request):
        assert request.url.params["page_num"] == "2"
        assert request.url.params["keywords"] == "公园"
        assert "types" not in request.url.params
        return httpx.Response(
            200,
            json={
                "status": "1",
                "count": "10",
                "pois": [poi(id=f"B{i}") for i in range(10)],
            },
        )

    with client_for(handler) as client:
        result = client.post(
            "/api/maps/search",
            json={
                "city_id": "shanghai",
                "keywords": " 公园 ",
                "page": 2,
            },
        ).json()
    assert result["has_more"] is True
    assert len(result["items"]) == 10


def test_successful_empty_results():
    with client_for(lambda _: httpx.Response(200, json={"status": "1", "pois": []})) as client:
        result = client.post("/api/hotels/search", json={"city_id": "shanghai"}).json()
    assert result["state"] == "empty"
    assert result["has_more"] is False


@pytest.mark.parametrize(
    "query",
    [
        {"city_id": "beijing"},
        {"city_id": "shanghai", "page": 0},
        {"city_id": "shanghai", "page": 101},
        {"city_id": "shanghai", "keywords": "x" * 101},
        {"city_id": "shanghai", "keywords": "a\nb"},
        {"city_id": "shanghai", "url": "https://untrusted.example"},
    ],
)
def test_invalid_queries_rejected_without_network(query):
    with client_for(lambda _: pytest.fail("Validation should run before network")) as client:
        response = client.post("/api/hotels/search", json=query)
    assert response.status_code == 422


def test_static_map_proxy_keeps_key_private_and_coordinates_gcj02():
    def handler(request):
        assert request.url.path == "/v3/staticmap"
        assert request.url.params["key"] == KEY
        assert request.url.params["location"] == "121.470000,31.230000"
        assert request.url.params["zoom"] == "15"
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    with client_for(handler) as client:
        response = client.post(
            "/api/maps/static",
            json={
                "city_id": "shanghai",
                "zoom": 15,
                "location": {"longitude": 121.47, "latitude": 31.23, "coordinate_system": "GCJ02"},
            },
        )
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert "no-store" in response.headers["cache-control"]
    assert KEY not in str(response.headers)


def test_city_map_geocodes_city_instead_of_relabeling_wgs84_center():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/v3/geocode/geo":
            assert request.url.params["city"] == "330100"
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "geocodes": [
                        {
                            "adcode": "330100",
                            "location": "120.17,30.25",
                        }
                    ],
                },
            )
        assert request.url.params["location"] == "120.170000,30.250000"
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    with client_for(handler) as client:
        response = client.post("/api/maps/static", json={"city_id": "hangzhou"})
    assert response.status_code == 200
    assert calls == ["/v3/geocode/geo", "/v3/staticmap"]


@pytest.mark.parametrize(
    "body,mime",
    [
        (b"<script>bad</script>", "image/png"),
        (PNG, "text/html"),
        pytest.param(b"x" * (2 * 1024 * 1024 + 1), "image/png", id="oversized"),
        (b'{"status":"0","infocode":"10001"}', "application/json"),
    ],
)
def test_map_errors_and_non_images_not_returned_as_images(body, mime):
    with client_for(
        lambda _: httpx.Response(
            200,
            content=body,
            headers={
                "content-type": mime,
            },
        )
    ) as client:
        response = client.post(
            "/api/maps/static",
            json={
                "city_id": "shanghai",
                "location": {"longitude": 121.47, "latitude": 31.23},
            },
        )
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/json"
    assert KEY not in response.text


@pytest.mark.parametrize(
    "location,zoom",
    [
        ({"longitude": 121.47, "latitude": 31.23, "coordinate_system": "WGS84"}, 13),
        ({"longitude": 181, "latitude": 31.23}, 13),
        ({"longitude": 121.47, "latitude": 31.23}, 19),
    ],
)
def test_map_coordinate_system_and_zoom_validation(location, zoom):
    with client_for(lambda _: pytest.fail("Invalid point must not call provider")) as client:
        response = client.post(
            "/api/maps/static",
            json={
                "city_id": "shanghai",
                "location": location,
                "zoom": zoom,
            },
        )
    assert response.status_code == 422


def test_amap_env_alias_blank_and_secrets(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"AMAP_API_KEY={KEY}\n", encoding="utf-8")
    settings = Settings(_env_file=env)
    assert settings.amap_configured
    assert KEY not in repr(settings)
    assert KEY not in settings.model_dump_json()
    assert not Settings(_env_file=None, amap_api_key="   ").amap_configured
