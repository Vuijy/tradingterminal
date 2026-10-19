"""SEC EDGAR: fundamentals and filings for US-listed companies.

Free, no key. The SEC requires a descriptive User-Agent with contact details
(`SEC_EDGAR_USER_AGENT`) and asks for at most 10 requests per second. The three
endpoints used here are all cached; `companyfacts` is a few MB per company.
"""

from typing import Any

import httpx

from app.models.fundamentals import FilingList, Financials
from app.services.cache import cache
from app.services.edgar_parsing import build_financials, parse_filings
from app.services.errors import UpstreamError
from app.services.providers.base import FundamentalsProvider

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

TICKER_TABLE_TTL = 24 * 3600
FACTS_TTL = 6 * 3600
SUBMISSIONS_TTL = 3600


def _norm(ticker: str) -> str:
    # Yahoo writes BRK-B, the SEC table writes BRK-B too but older entries use dots.
    return ticker.strip().upper().replace(".", "-")


class EdgarProvider(FundamentalsProvider):
    name = "sec-edgar"

    def __init__(self, user_agent: str, timeout: float = 30.0) -> None:
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._timeout = timeout

    async def ticker_table(self) -> dict[str, tuple[int, str]]:
        """ticker -> (cik, title) in the SEC's market-cap order (tuples become lists via JSON)."""
        return await cache.get_or_set(
            "edgar:tickers", TICKER_TABLE_TTL, self._fetch_ticker_table, persist=True
        )

    async def resolve_cik(self, ticker: str) -> tuple[int, str] | None:
        hit = (await self.ticker_table()).get(_norm(ticker))
        return (int(hit[0]), str(hit[1])) if hit else None

    async def latest_filing(self, cik: int, forms: tuple[str, ...] = ("10-K",)) -> dict | None:
        """Most recent filing of one of `forms` as {accession, form, filed, url, name}."""
        subs = await cache.get_or_set(
            f"edgar:submissions:{cik}",
            SUBMISSIONS_TTL,
            lambda: self._get_json(SUBMISSIONS_URL.format(cik=cik)),
            persist=True,
        )
        if not subs:
            return None
        recent = subs.get("filings", {}).get("recent", {})
        rows = zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("primaryDocument", []),
            strict=False,
        )
        for accession, form, filed, doc in rows:
            if form in forms and doc:
                return {
                    "accession": accession,
                    "form": form,
                    "filed": filed,
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{accession.replace('-', '')}/{doc}"
                    ),
                    "name": subs.get("name") or "",
                }
        return None

    async def get_financials(self, ticker: str) -> Financials | None:
        hit = await self.resolve_cik(ticker)
        if hit is None:
            return None
        cik, name = hit
        facts = await cache.get_or_set(
            f"edgar:facts:{cik}",
            FACTS_TTL,
            lambda: self._get_json(FACTS_URL.format(cik=cik)),
            persist=True,
        )
        if facts is None:
            return None
        return build_financials(
            ticker.upper(), cik, facts.get("entityName") or name, facts, source=self.name
        )

    async def get_filings(
        self, ticker: str, forms: set[str] | None, limit: int
    ) -> FilingList | None:
        hit = await self.resolve_cik(ticker)
        if hit is None:
            return None
        cik, name = hit
        subs = await cache.get_or_set(
            f"edgar:submissions:{cik}",
            SUBMISSIONS_TTL,
            lambda: self._get_json(SUBMISSIONS_URL.format(cik=cik)),
            persist=True,
        )
        if subs is None:
            return None
        return FilingList(
            ticker=ticker.upper(),
            cik=cik,
            entity_name=subs.get("name") or name,
            filings=parse_filings(cik, subs, forms, limit),
            source=self.name,
        )

    async def _fetch_ticker_table(self) -> dict[str, tuple[int, str]]:
        data = await self._get_json(TICKERS_URL)
        if not data:
            raise UpstreamError(self.name, "ticker table unavailable")
        table: dict[str, tuple[int, str]] = {}
        for row in data.values():
            try:
                table[_norm(row["ticker"])] = (int(row["cik_str"]), str(row.get("title") or ""))
            except (KeyError, TypeError, ValueError):
                continue
        return table

    async def _get_json(self, url: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout, follow_redirects=True
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            raise UpstreamError(self.name, str(exc)) from exc
        if response.status_code == 404:
            return None
        if response.status_code == 403:
            raise UpstreamError(
                self.name,
                "request rejected (403). Set SEC_EDGAR_USER_AGENT to 'AppName you@example.com'.",
            )
        if response.status_code >= 400:
            raise UpstreamError(self.name, f"HTTP {response.status_code} for {url}")
        return response.json()
