from fastapi.testclient import TestClient


def test_company_profile_found(client: TestClient) -> None:
    res = client.get("/api/v1/companies/aapl")
    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["source"] == "fake"


def test_company_profile_unknown(client: TestClient) -> None:
    res = client.get("/api/v1/companies/ZZZZ")
    assert res.status_code == 404
    assert "ZZZZ" in res.json()["detail"]


def test_company_ticker_validation(client: TestClient) -> None:
    res = client.get("/api/v1/companies/not%20a%20ticker")
    assert res.status_code == 422


def test_quote_found(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/quote")
    assert res.status_code == 200
    body = res.json()
    assert body["price"] == 190.0
    assert round(body["change_pct"], 4) == round(2.0 / 188.0 * 100, 4)


def test_history_default_params(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/history")
    assert res.status_code == 200
    body = res.json()
    assert body["range"] == "6mo"
    assert body["interval"] == "1d"
    assert len(body["candles"]) == 5
    assert body["candles"][0]["close"] == 100.5


def test_history_rejects_bad_combination(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/history", params={"range": "1y", "interval": "1m"})
    assert res.status_code == 422
    assert "1m" in res.json()["detail"]


def test_history_rejects_unknown_interval(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/history", params={"interval": "7h"})
    assert res.status_code == 422


def test_history_unknown_ticker(client: TestClient) -> None:
    assert client.get("/api/v1/companies/ZZZZ/history").status_code == 404


def test_news(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/news", params={"limit": 2})
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["publisher"] == "Fake Wire"


def test_fundamentals_found(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/fundamentals")
    assert res.status_code == 200
    body = res.json()
    assert body["cik"] == 320193
    assert body["annual"][0]["period"] == "FY2025"
    assert body["annual"][0]["values"]["revenue"] == 416_161_000_000.0


def test_fundamentals_not_a_filer(client: TestClient) -> None:
    res = client.get("/api/v1/companies/SAP.DE/fundamentals")
    assert res.status_code == 404
    assert "EDGAR" in res.json()["detail"]


def test_filings_filtered_by_form(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/filings", params={"forms": "10-K"})
    assert res.status_code == 200
    forms = [f["form"] for f in res.json()["filings"]]
    assert forms == ["10-K"]


def test_filings_all_forms(client: TestClient) -> None:
    res = client.get("/api/v1/companies/AAPL/filings", params={"forms": ""})
    assert res.status_code == 200
    assert len(res.json()["filings"]) == 2
