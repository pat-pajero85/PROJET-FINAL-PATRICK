from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import main


@pytest.fixture(scope="session")
def test_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    test_database = tmp_path_factory.mktemp("api") / "gtfs_test.sqlite"
    shutil.copy2(main.DATABASE, test_database)
    return test_database


@pytest.fixture
def client(test_database: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "DATABASE", test_database)
    monkeypatch.setattr(main, "API_KEY", None)
    with TestClient(main.app) as test_client:
        yield test_client


def stop_payload(stop_id: str = "API-TEST-001") -> dict[str, object]:
    return {
        "stop_id": stop_id,
        "stop_name": "Arret API",
        "stop_lat": 47.2184,
        "stop_lon": -1.5536,
        "location_type": 0,
        "wheelchair_boarding": 1,
        "coordinate_status": "within_pdl_bbox",
    }


def test_system_and_openapi_endpoints(client: TestClient) -> None:
    health = client.get("/health")
    openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert openapi.status_code == 200
    assert "/api/v1/stops" in openapi.json()["paths"]


def test_catalogue_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/routes?limit=1").status_code == 200
    assert client.get("/api/v1/agencies").status_code == 200


def test_analytics_query_validation(client: TestClient) -> None:
    response = client.get(
        "/api/v1/analytics/departures-by-stop-day",
        params={"service_date": "2026-01-01"},
    )

    assert response.status_code == 422


def test_stops_filters_and_validation(client: TestClient) -> None:
    response = client.get(
        "/api/v1/stops",
        params={"coordinate_status": "within_pdl_bbox", "limit": 2},
    )

    assert response.status_code == 200
    assert len(response.json()) <= 2
    assert all(item["coordinate_status"] == "within_pdl_bbox" for item in response.json())
    assert client.get("/api/v1/stops?limit=0").status_code == 422
    assert client.get("/api/v1/stops/STOP-DOES-NOT-EXIST").status_code == 404


def test_stop_crud_isolated_from_reference_database(client: TestClient) -> None:
    created = client.post("/api/v1/stops", json=stop_payload())
    assert created.status_code == 201
    assert created.json()["stop_id"] == "API-TEST-001"

    patched = client.patch(
        "/api/v1/stops/API-TEST-001",
        json={"stop_name": "Arret API modifie"},
    )
    assert patched.status_code == 200
    assert patched.json()["stop_name"] == "Arret API modifie"

    replacement_payload = stop_payload()
    replacement_payload.pop("stop_id")
    replacement_payload["stop_name"] = "Arret API remplace"
    replaced = client.put(
        "/api/v1/stops/API-TEST-001",
        json=replacement_payload,
    )
    assert replaced.status_code == 200
    assert replaced.json()["stop_name"] == "Arret API remplace"

    deleted = client.delete("/api/v1/stops/API-TEST-001")
    assert deleted.status_code == 204
    assert client.get("/api/v1/stops/API-TEST-001").status_code == 404


def test_write_endpoints_require_api_key_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "API_KEY", "test-secret")

    response = client.post("/api/v1/stops", json=stop_payload("API-TEST-002"))

    assert response.status_code == 401