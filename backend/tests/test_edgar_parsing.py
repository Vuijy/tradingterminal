"""Unit tests for the companyfacts parser, using a tiny synthetic filing history."""

from app.services.edgar_parsing import build_financials, parse_filings


def _fact(start, end, val, filed, form, fy, fp):
    return {
        "start": start,
        "end": end,
        "val": val,
        "filed": filed,
        "form": form,
        "fy": fy,
        "fp": fp,
    }


def _instant(end, val, filed, form, fy, fp):
    return {"end": end, "val": val, "filed": filed, "form": form, "fy": fy, "fp": fp}


FACTS = {
    "entityName": "Test Corp",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        # FY2023 as originally filed, then restated in the FY2024 10-K
                        _fact("2023-01-01", "2023-12-31", 1000, "2024-02-15", "10-K", 2023, "FY"),
                        _fact("2023-01-01", "2023-12-31", 1010, "2025-02-15", "10-K", 2024, "FY"),
                        _fact("2024-01-01", "2024-12-31", 1200, "2025-02-15", "10-K", 2024, "FY"),
                        # FY2024 quarters (+ a six-month year-to-date figure to be ignored)
                        _fact("2024-01-01", "2024-03-31", 250, "2024-05-01", "10-Q", 2024, "Q1"),
                        _fact("2024-04-01", "2024-06-30", 300, "2024-08-01", "10-Q", 2024, "Q2"),
                        _fact("2024-01-01", "2024-06-30", 550, "2024-08-01", "10-Q", 2024, "Q2"),
                        _fact("2024-07-01", "2024-09-30", 320, "2024-11-01", "10-Q", 2024, "Q3"),
                        # Current-year quarter with no 10-K yet; plus its prior-year comparative
                        _fact("2025-01-01", "2025-03-31", 280, "2025-05-01", "10-Q", 2025, "Q1"),
                        _fact("2024-01-01", "2024-03-31", 250, "2025-05-01", "10-Q", 2025, "Q1"),
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        _fact("2024-01-01", "2024-12-31", 100, "2025-02-15", "10-K", 2024, "FY"),
                        _fact("2024-01-01", "2024-03-31", 20, "2024-05-01", "10-Q", 2024, "Q1"),
                        _fact("2024-04-01", "2024-06-30", 25, "2024-08-01", "10-Q", 2024, "Q2"),
                        _fact("2024-07-01", "2024-09-30", 30, "2024-11-01", "10-Q", 2024, "Q3"),
                    ]
                }
            },
            "CostOfRevenue": {
                "units": {
                    "USD": [
                        _fact("2024-01-01", "2024-12-31", 700, "2025-02-15", "10-K", 2024, "FY")
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        _instant("2023-12-31", 5000, "2024-02-15", "10-K", 2023, "FY"),
                        _instant("2024-12-31", 6000, "2025-02-15", "10-K", 2024, "FY"),
                        _instant("2024-03-31", 5100, "2024-05-01", "10-Q", 2024, "Q1"),
                    ]
                }
            },
        }
    },
}


def test_annual_periods_pick_latest_restatement() -> None:
    fin = build_financials("TEST", 1, "Test Corp", FACTS, source="t")
    assert [p.period for p in fin.annual] == ["FY2024", "FY2023"]
    assert fin.annual[0].values["revenue"] == 1200
    assert fin.annual[1].values["revenue"] == 1010  # restated value wins
    assert fin.annual[0].filed.isoformat() == "2025-02-15"
    assert fin.annual[1].filed.isoformat() == "2024-02-15"  # original filing kept as metadata


def test_balance_sheet_attached_by_end_date() -> None:
    fin = build_financials("TEST", 1, "Test Corp", FACTS, source="t")
    assert fin.annual[0].values["total_assets"] == 6000
    assert fin.annual[1].values["total_assets"] == 5000


def test_gross_profit_is_derived_when_missing() -> None:
    fin = build_financials("TEST", 1, "Test Corp", FACTS, source="t")
    assert fin.annual[0].values["gross_profit"] == 500


def test_quarters_labelled_and_q4_derived() -> None:
    fin = build_financials("TEST", 1, "Test Corp", FACTS, source="t")
    by_label = {p.period: p for p in fin.quarterly}
    assert set(by_label) == {"Q1 FY2025", "Q4 FY2024", "Q3 FY2024", "Q2 FY2024", "Q1 FY2024"}
    assert by_label["Q1 FY2024"].values["revenue"] == 250
    assert by_label["Q1 FY2024"].values["total_assets"] == 5100
    q4 = by_label["Q4 FY2024"]
    assert q4.derived is True
    assert q4.values["revenue"] == 1200 - (250 + 300 + 320)
    assert q4.values["net_income"] == 100 - (20 + 25 + 30)
    assert q4.values["total_assets"] == 6000
    assert q4.start.isoformat() == "2024-10-01"
    # The current-year quarter has no 10-K to anchor it; filing metadata places it.
    assert by_label["Q1 FY2025"].values["revenue"] == 280
    assert fin.quarterly[0].period == "Q1 FY2025"  # newest first


def test_year_to_date_durations_are_ignored() -> None:
    fin = build_financials("TEST", 1, "Test Corp", FACTS, source="t")
    assert all(p.values["revenue"] != 550 for p in fin.quarterly)


def test_parse_filings_filters_and_links() -> None:
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-25-000001", "0000000001-25-000002"],
                "filingDate": ["2025-02-15", "2025-01-10"],
                "reportDate": ["2024-12-31", ""],
                "form": ["10-K", "8-K"],
                "primaryDocument": ["tc-10k.htm", "tc-8k.htm"],
                "primaryDocDescription": ["10-K", ""],
            }
        }
    }
    filings = parse_filings(1, submissions, {"10-K"}, limit=10)
    assert len(filings) == 1
    assert filings[0].form == "10-K"
    assert filings[0].report_date.isoformat() == "2024-12-31"
    assert (
        filings[0].url == "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/tc-10k.htm"
    )
    assert len(parse_filings(1, submissions, None, limit=1)) == 1
