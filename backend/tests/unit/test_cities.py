from fastapi.testclient import TestClient

from app.core.cities import get_cities, get_city
from app.core.contracts import EvidenceState
from app.main import app

EXPECTED_CITIES = {
    "shanghai": ("上海", 31.222222, 121.458056, "上海市"),
    "suzhou": ("苏州", 31.304077, 120.595380, "江苏省"),
    "wuxi": ("无锡", 31.568873, 120.288573, "江苏省"),
    "jiaxing": ("嘉兴", 30.752198, 120.749997, "浙江省"),
    "hangzhou": ("杭州", 30.293650, 120.161419, "浙江省"),
}


def test_registry_contains_only_the_five_ordered_pilot_cities() -> None:
    cities = get_cities()

    assert [city.id for city in cities] == list(EXPECTED_CITIES)
    assert all(city.is_pilot for city in cities)
    for city in cities:
        name, latitude, longitude, province = EXPECTED_CITIES[city.id]
        assert city.name == name
        assert city.province == province
        assert city.center.latitude == latitude
        assert city.center.longitude == longitude
        assert city.center.coordinate_system == "WGS84"
        assert city.center.evidence_state is EvidenceState.VERIFIED
        assert city.center.verified_at.tzinfo is not None
        assert city.center.sources
        assert all(source.source_id.startswith("nga.geonames.") for source in city.center.sources)


def test_city_lookup_returns_an_isolated_record() -> None:
    first = get_city("shanghai")
    second = get_city("shanghai")

    assert first is not None and second is not None
    first.name = "modified"
    assert second.name == "上海"
    assert get_city("unknown-city") is None


def test_foundation_city_list_api_returns_the_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/foundation/cities")

    assert response.status_code == 200
    body = response.json()
    assert [city["id"] for city in body] == list(EXPECTED_CITIES)
    assert body[0]["center"]["coordinate_system"] == "WGS84"
    assert body[0]["center"]["sources"][0]["source_id"].startswith("nga.geonames.")


def test_foundation_city_detail_api_returns_city() -> None:
    client = TestClient(app)

    response = client.get("/api/foundation/cities/hangzhou")

    assert response.status_code == 200
    assert response.json()["name"] == "杭州"


def test_foundation_city_detail_api_returns_stable_not_found_code() -> None:
    client = TestClient(app)

    response = client.get("/api/foundation/cities/not-a-city")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["retryable"] is False
    assert body["request_id"]

