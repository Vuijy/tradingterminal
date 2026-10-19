import datetime as dt

from fastapi.testclient import TestClient

from app.api.deps import get_relationship_service
from app.models.relationships import RelationshipGraph
from app.services.entity_resolution import Registrant, Resolution
from app.services.relationship_extraction import (
    KIND_ANON,
    KIND_COMPETITOR,
    KIND_CUSTOMER,
    KIND_SUPPLIER,
    Mention,
)
from app.services.relationships import FilingRef, assemble_graph, name_variants, search_templates

APPLE = Registrant(320193, "AAPL", "Apple Inc.")
OWN = FilingRef(
    320193,
    "Apple Inc.",
    "AAPL",
    "10-K",
    dt.date(2025, 10, 31),
    "0000320193-25-000079",
    "https://sec/aapl",
)
SWKS = FilingRef(
    4127,
    "SKYWORKS SOLUTIONS, INC.",
    "SWKS",
    "10-K",
    dt.date(2025, 11, 7),
    "0000004127-25-000085",
    "https://sec/swks",
)
CRWV = FilingRef(
    1769628,
    "CoreWeave, Inc.",
    "CRWV",
    "10-K",
    dt.date(2026, 3, 2),
    "0001769628-26-000104",
    "https://sec/crwv",
)


def test_name_variants_and_templates() -> None:
    assert name_variants("NVIDIA CORP") == ["NVIDIA CORP", "NVIDIA"]
    assert name_variants("Apple Inc.") == ["Apple Inc.", "Apple"]
    assert name_variants("Amkor Technology, Inc.") == ["Amkor Technology, Inc.", "Amkor Technology"]
    queries = [q for q, _, _ in search_templates(name_variants("Apple Inc."))]
    assert '"Apple accounted for"' in queries and '"Apple Inc. accounted for"' in queries
    assert '"competitors include Apple"' in queries


def test_assemble_graph_directions_and_merging() -> None:
    own = [
        (
            OWN,
            Mention(KIND_SUPPLIER, "Foxconn", "We rely on Foxconn.", 10, "supplier_from", 0.8),
            Resolution(None, None, "Foxconn", 0.9, "alias-nonfiler"),
        ),
        (
            OWN,
            Mention(
                KIND_COMPETITOR, "Samsung", "We compete with Samsung.", 20, "compete_with", 0.75
            ),
            Resolution(None, None, "Samsung", 0.9, "alias-nonfiler"),
        ),
        (
            OWN,
            Mention(
                KIND_ANON,
                None,
                "one customer represented 12% of receivables",
                30,
                "customer_pct",
                0.5,
                percent=12.0,
                basis="receivables",
                label="one customer",
            ),
            None,
        ),
        (
            OWN,
            Mention(KIND_CUSTOMER, "Apple", "Apple sells to Apple", 40, "customer_list", 0.6),
            Resolution(320193, "AAPL", "Apple Inc.", 0.95, "alias"),
        ),  # self reference, dropped
    ]
    reverse = [
        (
            SWKS,
            Mention(
                KIND_CUSTOMER,
                "Apple",
                "Apple accounted for 67% of net revenue.",
                0,
                "customer_through",
                0.95,
                percent=67.0,
                basis="revenue",
                section="Item 8",
            ),
        ),
        (
            SWKS,
            Mention(
                KIND_CUSTOMER,
                "Apple Inc",
                "Our key customers include Apple Inc.",
                1,
                "customer_list",
                0.6,
            ),
        ),
        (CRWV, Mention(KIND_SUPPLIER, "NVIDIA", "all GPUs are NVIDIA GPUs", 0, "supply_cue", 0.5)),
    ]
    graph = assemble_graph(APPLE, own, reverse, ["a", "b"], "complete")
    assert graph.ticker == "AAPL" and graph.status == "complete"

    suppliers = {s.name: s for s in graph.suppliers}
    assert suppliers["Skyworks Solutions, Inc."].revenue_share_pct == 67.0
    assert suppliers["Skyworks Solutions, Inc."].ticker == "SWKS"
    assert len(suppliers["Skyworks Solutions, Inc."].evidence) == 2
    assert suppliers["Skyworks Solutions, Inc."].confidence > 0.95
    assert suppliers["Foxconn"].ticker is None and suppliers["Foxconn"].cik is None

    assert [c.name for c in graph.customers] == ["CoreWeave, Inc."]
    assert graph.customers[0].evidence[0].method == "full_text_search"
    assert [c.name for c in graph.competitors] == ["Samsung"]
    assert graph.anonymous_customers[0].label == "one customer"
    assert graph.anonymous_customers[0].percent is None  # receivables share is not a revenue share
    assert graph.analyzed_filings == ["a", "b"]


class FakeRelationshipService:
    name = "fake"

    async def get_graph(
        self, ticker: str, *, deep: bool, refresh: bool = False
    ) -> RelationshipGraph | None:
        if ticker.upper() != "AAPL":
            return None
        return assemble_graph(APPLE, [], [], ["x"], "complete" if deep else "own_filing_only")


def test_relationships_route(client: TestClient) -> None:
    client.app.dependency_overrides[get_relationship_service] = lambda: FakeRelationshipService()  # type: ignore[attr-defined]
    res = client.get("/api/v1/companies/AAPL/relationships")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "own_filing_only" and body["cik"] == 320193
    assert (
        client.get("/api/v1/companies/AAPL/relationships", params={"deep": "true"}).json()["status"]
        == "complete"
    )
    assert client.get("/api/v1/companies/SAP.DE/relationships").status_code == 404
