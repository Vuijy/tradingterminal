"""SEC EDGAR Full-Text Search (EFTS) client.

The JSON API behind https://www.sec.gov/edgar/search/. Verified behaviour is written up
in docs/research/sec-full-text-search.md; the parts that matter here:

- GET https://efts.sec.gov/LATEST/search-index with a User-Agent, gzip accepted.
- `q`: each "quoted phrase" is an exact phrase; all phrases must occur in the document
  (no proximity). `forms=10-K` includes 10-K/A. Date filters need BOTH startdt and enddt.
- Pages are 100 hits, offset via `from`; `hits.total.value` is capped at 10 000.
- One filing yields several hits (primary document plus every exhibit); `sequence == 1`
  is the primary document. Errors can arrive as HTTP 200 JSON with `errorType`/`error`.
- Tickers almost never appear in filing text: search names, read tickers from hits.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.cache import cache
from app.services.errors import UpstreamError

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SEARCH_TTL = 24 * 3600
PAGE_SIZE = 100

_DISPLAY_RE = re.compile(
    r"^(?P<name>.*?)\s{2,}(?:\((?P<tickers>[^()]*)\)\s{2,})?\(CIK\s+(?P<cik>\d+)\)\s*$"
)


@dataclass(frozen=True)
class SearchHit:
    cik: int
    entity_name: str
    ticker: str | None
    form: str
    file_type: str | None
    file_date: dt.date | None
    period_ending: dt.date | None
    accession: str
    filename: str
    sequence: int | None
    score: float

    @property
    def primary_doc_url(self) -> str:
        return f"https://www.sec.gov/Archives/edgar/data/{self.cik}/{self.accession.replace('-', '')}/{self.filename}"

    @property
    def is_primary(self) -> bool:
        return self.sequence == 1


def parse_display_name(value: str) -> tuple[str, str | None, int | None]:
    """'Apple Inc.  (AAPL)  (CIK 0000320193)' -> ('Apple Inc.', 'AAPL', 320193)."""
    m = _DISPLAY_RE.match(value or "")
    if not m:
        return (value or "").strip(), None, None
    tickers = (m.group("tickers") or "").split(",")
    ticker = tickers[0].strip() or None if tickers else None
    return m.group("name").strip(), ticker, int(m.group("cik"))


def _date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def parse_hits(payload: dict[str, Any]) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for raw in payload.get("hits", {}).get("hits", []):
        src = raw.get("_source") or {}
        raw_id = str(raw.get("_id") or "")
        accession, _, filename = raw_id.partition(":")
        ciks = src.get("ciks") or []
        names = src.get("display_names") or []
        # The registrant is listed last on ownership forms; for 10-K there is one entry.
        cik: int | None = None
        name, ticker = "", None
        for i in range(len(ciks)):
            n, t, c = parse_display_name(names[i] if i < len(names) else "")
            if c is None:
                try:
                    c = int(ciks[i])
                except (TypeError, ValueError):
                    continue
            cik, name, ticker = c, n, t
        if cik is None or not accession:
            continue
        hits.append(
            SearchHit(
                cik=cik,
                entity_name=name,
                ticker=ticker,
                form=str(src.get("form") or ""),
                file_type=src.get("file_type"),
                file_date=_date(src.get("file_date")),
                period_ending=_date(src.get("period_ending")),
                accession=accession,
                filename=filename,
                sequence=src.get("sequence") if isinstance(src.get("sequence"), int) else None,
                score=float(raw.get("_score") or 0.0),
            )
        )
    return hits


def total_hits(payload: dict[str, Any]) -> int:
    total = payload.get("hits", {}).get("total") or {}
    return int(total.get("value") or 0) if isinstance(total, dict) else int(total or 0)


class EdgarFullTextSearch:
    name = "sec-efts"

    def __init__(self, user_agent: str, timeout: float = 30.0) -> None:
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._timeout = timeout

    async def search(
        self,
        query: str,
        *,
        forms: str = "10-K",
        start: dt.date | None = None,
        end: dt.date | None = None,
        offset: int = 0,
    ) -> tuple[list[SearchHit], int]:
        """One page (100 hits) of results plus the (capped) total."""
        start_s = (start or dt.date(2001, 1, 1)).isoformat()
        end_s = (end or dt.date(2099, 12, 31)).isoformat()
        key = f"efts:{forms}:{start_s}:{end_s}:{offset}:{query}"
        payload = await cache.get_or_set(
            key, SEARCH_TTL, lambda: self._get(query, forms, start_s, end_s, offset), persist=True
        )
        return parse_hits(payload), total_hits(payload)

    async def _get(self, query: str, forms: str, start: str, end: str, offset: int) -> dict:
        params = {
            "q": query,
            "forms": forms,
            "dateRange": "custom",
            "startdt": start,
            "enddt": end,
            "from": str(offset),
        }
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as client:
                response = await client.get(EFTS_URL, params=params)
        except httpx.HTTPError as exc:
            raise UpstreamError(self.name, str(exc)) from exc
        if response.status_code == 403:
            raise UpstreamError(
                self.name, "rejected (403): set SEC_EDGAR_USER_AGENT to 'App you@x.com'"
            )
        if response.status_code >= 400:
            raise UpstreamError(self.name, f"HTTP {response.status_code}")
        payload = response.json()
        if "errorType" in payload or "error" in payload:
            raise UpstreamError(
                self.name, str(payload.get("errorMessage") or payload.get("error"))[:200]
            )
        return payload
