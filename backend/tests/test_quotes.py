from fastapi.testclient import TestClient


def test_batch_quotes_keeps_known_symbols(client: TestClient) -> None:
    res = client.get("/api/v1/quotes", params={"tickers": "aapl, ZZZZ ,AAPL"})
    assert res.status_code == 200
    body = res.json()
    assert [q["ticker"] for q in body] == ["AAPL"]  # unknown dropped, duplicate collapsed
    assert body[0]["price"] == 190.0


def test_batch_quotes_rejects_bad_symbol(client: TestClient) -> None:
    res = client.get("/api/v1/quotes", params={"tickers": "AAPL,not a ticker"})
    assert res.status_code == 422


def test_batch_quotes_rejects_too_many(client: TestClient) -> None:
    many = ",".join(f"T{i}" for i in range(31))
    res = client.get("/api/v1/quotes", params={"tickers": many})
    assert res.status_code == 422


def test_batch_quotes_requires_a_symbol(client: TestClient) -> None:
    assert client.get("/api/v1/quotes", params={"tickers": " , "}).status_code == 422
