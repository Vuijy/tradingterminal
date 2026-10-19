import pytest

from app.services.entity_resolution import EntityResolver, Registrant, normalize

REGISTRANTS = [  # market-cap order, like company_tickers.json
    Registrant(320193, "AAPL", "Apple Inc."),
    Registrant(1045810, "NVDA", "NVIDIA CORP"),
    Registrant(789019, "MSFT", "MICROSOFT CORP"),
    Registrant(1652044, "GOOGL", "Alphabet Inc."),
    Registrant(1652044, "GOOG", "Alphabet Inc."),
    Registrant(2488, "AMD", "ADVANCED MICRO DEVICES INC"),
    Registrant(37996, "F", "FORD MOTOR CO"),
    Registrant(1047127, "AMKR", "AMKOR TECHNOLOGY, INC."),
    Registrant(4127, "SWKS", "SKYWORKS SOLUTIONS, INC."),
    Registrant(1418121, "APLE", "Apple Hospitality REIT, Inc."),
    Registrant(1134982, "AAPI", "Apple iSports Group, Inc."),
    Registrant(1046179, "TSM", "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD"),
    Registrant(1769628, "CRWV", "CoreWeave, Inc."),
    Registrant(1587523, "KN", "Knowles Corp"),
    Registrant(1819994, "RKLB", "Rocket Lab Corp"),
    Registrant(1838359, "RKLX", "Rocket Lab X Holdings"),
]


@pytest.fixture
def resolver() -> EntityResolver:
    return EntityResolver(REGISTRANTS)


def test_normalize_strips_legal_forms() -> None:
    assert normalize("Apple Inc.") == "apple"
    assert normalize("AMKOR TECHNOLOGY, INC.") == "amkor technology"
    assert normalize("The Coca-Cola Company") == "coca cola"
    assert normalize("Alphabet Inc.'s") == "alphabet"


@pytest.mark.parametrize(
    ("mention", "ticker"),
    [
        ("Apple Inc.", "AAPL"),
        ("Apple", "AAPL"),  # alias beats the REIT and iSports collisions
        ("NVIDIA Corporation", "NVDA"),
        ("Nvidia", "NVDA"),
        ("Google", "GOOGL"),
        ("Amkor Technology, Inc.", "AMKR"),
        ("Knowles", "KN"),  # unique prefix of 'Knowles Corp'
        ("Skyworks Solutions", "SWKS"),
        ("TSMC", "TSM"),
        ("CoreWeave", "CRWV"),
        ("Ford Motor Company's", "F"),
    ],
)
def test_resolves_known_names(resolver: EntityResolver, mention: str, ticker: str) -> None:
    res = resolver.resolve(mention)
    assert res is not None and res.ticker == ticker, (mention, res)


@pytest.mark.parametrize(
    "mention",
    ["Customer A", "the Company", "Asia Pacific", "iPhone", "Windows", "Rocket", "", "Inc."],
)
def test_rejects_non_companies_and_ambiguity(resolver: EntityResolver, mention: str) -> None:
    assert resolver.resolve(mention) is None


def test_known_non_filer_keeps_name_without_link(resolver: EntityResolver) -> None:
    res = resolver.resolve("Samsung Electronics")
    assert res is not None and res.cik is None and res.name == "Samsung Electronics"


def test_lookup_helpers(resolver: EntityResolver) -> None:
    assert resolver.by_ticker("aapl").cik == 320193
    assert resolver.by_cik(37996).ticker == "F"
