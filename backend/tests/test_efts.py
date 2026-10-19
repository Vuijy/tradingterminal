from app.services.providers.efts import parse_display_name, parse_hits, total_hits


def test_parse_display_name_variants() -> None:
    assert parse_display_name("Apple Inc.  (AAPL)  (CIK 0000320193)") == (
        "Apple Inc.",
        "AAPL",
        320193,
    )
    assert parse_display_name("GOLDMAN SACHS GROUP INC  (GS, GSCE, GS-PA)  (CIK 0000886982)") == (
        "GOLDMAN SACHS GROUP INC",
        "GS",
        886982,
    )
    assert parse_display_name("Muliang Viagoo Technology, Inc.  (CIK 0001499785)") == (
        "Muliang Viagoo Technology, Inc.",
        None,
        1499785,
    )
    assert parse_display_name("garbage") == ("garbage", None, None)


def test_parse_hits_builds_document_url_and_flags_primary() -> None:
    payload = {
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [
                {
                    "_id": "0001047127-24-000012:amkr-20231231.htm",
                    "_score": 9.5,
                    "_source": {
                        "ciks": ["0001047127"],
                        "display_names": ["AMKOR TECHNOLOGY, INC.  (AMKR)  (CIK 0001047127)"],
                        "form": "10-K",
                        "file_type": "10-K",
                        "file_date": "2024-02-16",
                        "period_ending": "2023-12-31",
                        "sequence": 1,
                    },
                },
                {
                    "_id": "0001366868-25-000010:ex10-21.htm",
                    "_score": 3.0,
                    "_source": {
                        "ciks": ["0001366868"],
                        "display_names": ["Globalstar, Inc.  (GSAT)  (CIK 0001366868)"],
                        "form": "10-K",
                        "file_type": "EX-10.21",
                        "file_date": "2025-02-28",
                        "period_ending": None,
                        "sequence": 6,
                    },
                },
            ],
        }
    }
    hits = parse_hits(payload)
    assert total_hits(payload) == 2
    assert len(hits) == 2
    amkor = hits[0]
    assert amkor.cik == 1047127 and amkor.ticker == "AMKR" and amkor.is_primary
    assert amkor.accession == "0001047127-24-000012"
    assert (
        amkor.primary_doc_url
        == "https://www.sec.gov/Archives/edgar/data/1047127/000104712724000012/amkr-20231231.htm"
    )
    assert amkor.file_date is not None and amkor.file_date.isoformat() == "2024-02-16"
    assert not hits[1].is_primary and hits[1].period_ending is None


def test_parse_hits_skips_malformed() -> None:
    assert parse_hits({"hits": {"hits": [{"_id": "", "_source": {}}]}}) == []
    assert total_hits({}) == 0
