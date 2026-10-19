from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["provider"] == "fake"
    assert "version" in body


def test_openapi_served(client: TestClient) -> None:
    assert client.get("/api/v1/openapi.json").status_code == 200
