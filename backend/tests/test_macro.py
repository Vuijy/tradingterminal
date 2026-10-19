from fastapi.testclient import TestClient

from app.services.macro_registry import MACRO_SERIES


def test_dashboard_lists_every_curated_series(client: TestClient) -> None:
    res = client.get("/api/v1/macro/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert [s["series_id"] for s in body] == [m.series_id for m in MACRO_SERIES]
    first = body[0]
    assert first["latest_value"] == 5.0
    assert first["previous_value"] == 4.5
    assert round(first["change"], 6) == 0.5
    assert round(first["yoy_pct"], 6) == 25.0


def test_series_found(client: TestClient) -> None:
    res = client.get("/api/v1/macro/series/dgs10")
    assert res.status_code == 200
    body = res.json()
    assert body["series_id"] == "DGS10"
    assert len(body["observations"]) == 3


def test_series_start_filter(client: TestClient) -> None:
    res = client.get("/api/v1/macro/series/DGS10", params={"start": "2100-01-01"})
    assert res.status_code == 200
    assert res.json()["observations"] == []


def test_series_unknown(client: TestClient) -> None:
    assert client.get("/api/v1/macro/series/NOPE").status_code == 404


def test_series_id_validation(client: TestClient) -> None:
    assert client.get("/api/v1/macro/series/bad%20id").status_code == 422
