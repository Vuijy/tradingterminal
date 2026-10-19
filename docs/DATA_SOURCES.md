# Data sources

All sources are free. Each one is wrapped in a provider class under
`backend/app/services/providers/` so the rest of the app never touches vendor payloads
directly, every record carries a `source` field, and every call goes through the
in-process TTL cache (`app/services/cache.py`).

| Domain | Source | Access | Key needed | Status |
|---|---|---|---|---|
| Market data (profile, quote, OHLCV history) | Yahoo Finance via `yfinance` | Python library | No | Done |
| News | Yahoo Finance via `yfinance` | Python library | No | Done |
| Fundamentals (statements, filings) | SEC EDGAR | REST JSON (`data.sec.gov`) | No, but a User-Agent naming the app and a contact is required | Done |
| Macro (rates, inflation, labour, growth) | FRED (St. Louis Fed) | CSV (no key) or REST JSON (key) | Optional | Done |
| Supply-chain relationships | SEC 10-K text + EDGAR full-text search | HTML documents + JSON search API | No (same User-Agent rule) | Done |

## 1. Market data and news: yfinance

- Library: https://github.com/ranaroussi/yfinance (installed: 1.7)
- Profile and quote come from `Ticker.info` (one request, cached 5 min).
- History uses `Ticker.history(period, interval, auto_adjust=False)`; `Close` is
  split-adjusted but not dividend-adjusted, matching what TradingView shows by default.
  Yahoo's limits, enforced in `app/services/market.py`: 1m bars for 7 days,
  2m-30m bars for 60 days, 1h bars for 730 days, daily and coarser for everything.
- News: `Ticker.get_news()` has been returning empty lists with recent library versions,
  so the provider falls back to `yf.Search(ticker, news_count=n).news`, which works.
- Caveats: unofficial scraper, no SLA, bursts get rate-limited (HTTP 429 shows up as
  empty data / 404 from our API). Cache TTLs: info 5 min, intraday bars 60 s, daily
  bars 5 min, news 5 min.

## 2. Fundamentals: SEC EDGAR

- Docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Endpoints used (`providers/edgar_provider.py`):
  - `https://www.sec.gov/files/company_tickers.json` ticker -> CIK (cached 24 h).
  - `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` every XBRL fact a
    company ever reported (3-5 MB, cached 6 h).
  - `https://data.sec.gov/submissions/CIK##########.json` filing index (cached 1 h).
- Rules: send a `User-Agent` such as `TradingTerminal you@example.com`
  (`SEC_EDGAR_USER_AGENT` in `.env`), stay under 10 requests per second. CIKs are
  zero-padded to 10 digits in URLs.
- Parsing (`app/services/edgar_parsing.py`): facts are keyed by their own period
  (start, end), not by the filing's `fy`/`fp`, because a 10-K also carries the two
  prior years as comparatives. The most recently filed value for a period wins
  (restatements), ~1-year durations become annual rows, ~90-day durations become
  quarters, Q4 is derived as FY minus Q1-Q3, balance-sheet instants attach by end date.
- Only US-listed filers. Foreign issuers (20-F/40-F) have sparse XBRL; non-US tickers
  such as `SAP.DE` return 404 from `/fundamentals`.

## 3. Macro: FRED

- Docs: https://fred.stlouisfed.org/docs/api/fred/
- Without a key the provider reads the public chart download
  `https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES&cosd=YYYY-MM-DD`,
  the same endpoint pandas-datareader uses. Missing values arrive as `.`.
- With `FRED_API_KEY` set it switches to `api.stlouisfed.org/fred/series/observations`
  plus `/fred/series` for titles and units. (Written but not exercised yet: no key was
  available during development.)
- The dashboard series live in `app/services/macro_registry.py`: DGS10, DGS2, T10Y2Y,
  FEDFUNDS, MORTGAGE30US, CPIAUCSL, T10YIE, UNRATE, PAYEMS, GDPC1, VIXCLS, DTWEXBGS,
  DCOILWTICO. Any other FRED id works with `/macro/series/{id}`.
- Limits: 120 requests per minute on the API. Series are cached 1 h, the dashboard 15 min.

## Considered and not used

- **OpenBB Platform** (https://github.com/OpenBB-finance/OpenBB, Apache-2.0). A well
  maintained aggregator that fronts yfinance, FRED, SEC and many paid vendors behind
  one Python API. Not adopted: it wraps the same free sources we call directly, pulls in
  a large dependency tree, and adds a layer between us and the raw payloads. Worth a
  second look only if the terminal later needs many paid providers at once.
- Paid market-data APIs (Polygon, FMP, Finnhub, Alpha Vantage): out of scope by design.

## 5. Supply-chain relationships: SEC filing text + EDGAR full-text search

There is no free structured feed of supplier/customer links, so they are mined from
10-K text. Two endpoints beyond the ones above:

- Primary documents: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}`
  (1-10 MB of inline-XBRL HTML; converted to text with the standard library in well
  under a second; cached as text under `backend/data/filings/`).
- EDGAR full-text search: `https://efts.sec.gov/LATEST/search-index?q=...&forms=10-K&startdt=&enddt=`,
  the JSON API behind https://www.sec.gov/edgar/search/. Verified behaviour (parameters,
  response shape, quirks such as the 100-hit pages and the need for both date bounds)
  is documented in `docs/research/sec-full-text-search.md`. It only reports that a
  document contains the phrases, so every hit is confirmed by reading the document.

Implementation: `app/services/filing_text.py` (HTML to text, sections, sentences),
`app/services/relationship_extraction.py` (regex rules for customers with revenue share,
anonymous customers, suppliers, competitors, partners; and target-focused classification
of other filers' sentences), `app/services/entity_resolution.py` (names to tickers),
`app/services/providers/efts.py` (search client), `app/services/relationships.py`
(orchestration, SQLite storage, graph assembly). Coverage is limited to SEC registrants;
foreign companies appear as unlinked names when a filer mentions them.
