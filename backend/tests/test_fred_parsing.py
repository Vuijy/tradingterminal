import datetime as dt

from app.models.macro import MacroObservation, MacroSeries
from app.services.macro import summarize
from app.services.macro_registry import SERIES_BY_ID
from app.services.providers.fred_provider import parse_fred_api, parse_fred_csv


def test_parse_csv_skips_missing_values() -> None:
    text = "observation_date,DGS10\n2026-10-13,4.10\n2026-10-14,.\n2026-10-15,5.10\n"
    obs = parse_fred_csv(text)
    assert [(o.date.isoformat(), o.value) for o in obs] == [
        ("2026-10-13", 4.1),
        ("2026-10-15", 5.1),
    ]


def test_parse_csv_empty() -> None:
    assert parse_fred_csv("") == []


def test_parse_api_payload() -> None:
    payload = {
        "observations": [
            {"date": "2026-01-01", "value": "3.5"},
            {"date": "2026-01-02", "value": "."},
        ]
    }
    obs = parse_fred_api(payload)
    assert len(obs) == 1 and obs[0].value == 3.5


def test_summarize_handles_missing_series() -> None:
    summary = summarize(SERIES_BY_ID["DGS10"], None)
    assert summary.latest_value is None
    assert summary.title == "US 10Y Treasury"


def test_summarize_change_and_yoy() -> None:
    today = dt.date(2026, 10, 18)
    series = MacroSeries(
        series_id="UNRATE",
        title="x",
        source="t",
        observations=[
            MacroObservation(date=today - dt.timedelta(days=370), value=4.0),
            MacroObservation(date=today - dt.timedelta(days=30), value=4.2),
            MacroObservation(date=today, value=4.4),
        ],
    )
    s = summarize(SERIES_BY_ID["UNRATE"], series)
    assert s.latest_value == 4.4
    assert round(s.change, 6) == 0.2
    assert round(s.yoy_pct, 6) == 10.0
