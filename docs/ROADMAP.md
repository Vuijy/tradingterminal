# Roadmap

Order follows the agreed data-source plan: market data first, then fundamentals,
then macro, then news, then the relationship graph.

## 0. Scaffold (done)

- FastAPI backend, React/Vite frontend, tests, lint, Docker, docs.
- Company profile + quote via yfinance, wired end to end.

## 1. Market data: yfinance (done)

- OHLCV history endpoint with range/interval validation.
- TradingView-style candlestick + volume chart (`lightweight-charts`), range selector
  1D-MAX, crosshair legend with OHLC, change and volume.
- In-process TTL cache with single-flight around every upstream call.
- Watchlist panel: batch quotes endpoint (`/quotes?tickers=`), 30 s refresh, persisted in
  localStorage, click to load, add/remove symbols. Quote panel shows day and 52-week ranges.
- Still to do: comparison overlay, drawing tools.

## 2. Fundamentals: SEC EDGAR (done)

- Ticker -> CIK resolver with a cached copy of `company_tickers.json`.
- Annual and quarterly statements from companyfacts: revenue, cost of revenue, gross
  profit, R&D, operating income, net income, diluted EPS, operating cash flow, capex,
  total assets, liabilities, equity, cash, long-term debt, shares outstanding.
- Derived Q4, margins and YoY growth in the panel; filings tab (10-K, 10-Q, 8-K) linking
  to the documents.
- Still to do: more concepts (segments, dividends, buybacks), per-share and valuation
  ratios combined with the quote (P/E, P/S, EV/EBITDA), 20-F coverage.

## 3. Macro: FRED (done)

- Series endpoint for any FRED id, dashboard of 13 curated series with change and YoY.
- Macro panel: tiles plus a 1Y/5Y/MAX chart of the selected series.
- Still to do: recession shading, release calendar, yield-curve snapshot view.

## 4. News: Yahoo Finance (done)

- Headlines per ticker with publisher, age and related tickers (clickable).
- Keyword filter box in the panel header.
- Still to do: market-wide feed when no ticker is selected.

## 5. Company relationships (the Bloomberg SPLC-style view) (done)

- Own-filing pass: the company's latest 10-K is converted to text (stdlib parser, disk
  cached under `backend/data/filings/`), split into sections and sentences, and mined
  for named customers with revenue share, anonymous customers ("Customer A, 22%"),
  suppliers ("we purchase memory from ..."), competitors ("our competitors include ...").
- Reverse pass: ~30 phrase templates against EDGAR full-text search find other filers
  that name the company; up to 30 of their 10-Ks are downloaded and the sentences
  classified from the filer's point of view (a supplier disclosing "Apple accounted for
  67% of revenue" becomes a supplier of Apple).
- Names are resolved to tickers with an alias table and conservative matching; every
  mention is stored in SQLite (`mentions`) and the assembled graph cached for a week.
- Graph panel: centre company, suppliers left, customers right, competitors below,
  partners above; click a node for the sentences and filing links, click a ticker to
  re-centre. `SPLC` command code jumps to it.
- Still to do: 20-F filers (foreign companies), quantify supplier dependence over time,
  an LLM-based classifier as an optional upgrade to the regex rules.

## Cross-cutting

- Done: SQLAlchemy models + Alembic migrations run at startup (`app/db/`), used by the
  supply-chain feature; tests run against a throwaway SQLite file.
- Done: keyboard-driven command bar with Bloomberg-style codes (`AAPL FA`, `CN`, `ECO`,
  `SPLC`, `W`, `HELP`), `/` focuses the bar, panels scroll into view and flash.
- Still to do: persist the EDGAR/FRED caches to SQLite so restarts are warm.
- Multi-panel layouts saved per user; several charts side by side.
- Generate the TypeScript API types from the OpenAPI schema.
- Production build: nginx serving `frontend/dist`, uvicorn behind it.
