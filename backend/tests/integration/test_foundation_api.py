from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_foundation_city_list_api_returns_registered_city_contracts() -> None:
    response = client.get("/api/foundation/cities")

    assert response.status_code == 200
    body = response.json()
    assert [city["id"] for city in body] == [
        "shanghai",
        "suzhou",
        "wuxi",
        "jiaxing",
        "hangzhou",
    ]
    assert body[0]["center"]["coordinate_system"] == "WGS84"
    assert body[0]["center"]["sources"][0]["source_id"] == "nga.geonames.ufi.-1924465"
    assert "coverage" not in body[0]


def test_foundation_city_detail_api_returns_matching_city() -> None:
    response = client.get("/api/foundation/cities/hangzhou")

    assert response.status_code == 200
    assert response.json()["id"] == "hangzhou"
    assert response.json()["name"] == "杭州"


def test_foundation_city_detail_api_uses_public_error_for_unknown_city() -> None:
    response = client.get("/api/foundation/cities/not-a-city")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["retryable"] is False
    assert body["request_id"]
    assert "traceback" not in response.text.lower()


def test_openapi_documents_all_public_errors_with_shared_contract() -> None:
    schema = client.get("/openapi.json").json()

    assert "CityRecord" in schema["components"]["schemas"]
    assert "PublicError" in schema["components"]["schemas"]
    list_responses = schema["paths"]["/api/foundation/cities"]["get"]["responses"]
    detail_responses = schema["paths"]["/api/foundation/cities/{city_id}"]["get"]["responses"]
    assert list_responses["422"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PublicError"
    )
    assert detail_responses["404"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PublicError"
    )
    assert detail_responses["422"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PublicError"
    )
