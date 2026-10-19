# Trading Terminal

A web-based mini Bloomberg terminal for investors and stock traders. Type a ticker and
get everything about the company in one dark, keyboard-first screen: a TradingView-style
price chart, live quote, company profile, SEC financial statements and filings, news,
and a macro dashboard. Next up: the supply chain around a company, who supplies it, who
buys from it, who competes with it.

## Status

Working today, all on free data:

- **Price chart**: candlesticks + volume from Yahoo Finance, ranges 1D to MAX, crosshair
  legend with OHLC, change and volume. Built on TradingView's open-source `lightweight-charts`.
- **Quote and profile** for any Yahoo-listed ticker (US and international).
- **Fundamentals** from SEC EDGAR: annual and quarterly income statement, cash flow and
  balance sheet items, derived Q4, margins, YoY growth, plus a filings list (10-K, 10-Q, 8-K).
- **News** per ticker from Yahoo Finance, with clickable related tickers.
- **Macro** dashboard from FRED: Treasury yields, curve spread, Fed funds, mortgage rate,
  CPI, breakevens, unemployment, payrolls, GDP, VIX, USD index, WTI, each with a chart.
- **Supply chain** graph mined from SEC filings: who supplies the company, who buys from
  it (with revenue shares where disclosed), competitors and partners, each backed by the
  exact sentence and a link to the 10-K it came from. Combines the company's own 10-K with
  an EDGAR full-text search for every filer that names it.
- Tests, linting, type checking, Docker Compose, CI workflow, VS Code config.

See [docs/ROADMAP.md](docs/ROADMAP.md) for what comes next.

## Data sources (all free)

| Domain | Source | Notes |
|---|---|---|
| Market data: quotes, price history, profiles | **yfinance** (Yahoo Finance) | Python library, no key |
| News | **Yahoo Finance** via `yfinance` | No key |
| Fundamentals: financial statements, filings | **SEC EDGAR** | REST API, no key, requires a User-Agent with contact info |
| Macro: rates, inflation, labour, growth | **FRED** (St. Louis Fed) | CSV without a key, JSON API with a free key |

Endpoints, limits and gotchas for each are in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
OpenBB was evaluated and deliberately not used; the reasoning is in the same document.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, pydantic-settings, httpx, SQLAlchemy 2 (scaffold), pandas, yfinance |
| Frontend | React 19, TypeScript, Vite 7, TanStack Query, lightweight-charts 5 |
| Tooling | ruff, pytest, ESLint, Prettier, Docker Compose, GitHub Actions |
| Storage | In-process TTL cache with a SQLite second level for slow payloads; Alembic migrations run at startup; Postgres-ready via `DATABASE_URL` |

## Repository layout

```
tradingterminal/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI app factory, error handlers
│   │   ├── config.py                settings from .env
│   │   ├── api/
│   │   │   ├── router.py            mounts all routes under /api/v1
│   │   │   ├── deps.py              dependency injection for the three providers
│   │   │   └── routes/              health.py, companies.py, macro.py
│   │   ├── models/                  Pydantic response schemas (company, fundamentals, macro)
│   │   ├── services/
│   │   │   ├── cache.py             TTL cache with single-flight
│   │   │   ├── market.py            history range/interval rules
│   │   │   ├── edgar_parsing.py     companyfacts -> statements (pure functions)
│   │   │   ├── macro.py             dashboard summaries
│   │   │   ├── macro_registry.py    curated FRED series
│   │   │   └── providers/           base.py, yfinance_provider.py, edgar_provider.py, fred_provider.py
│   │   └── db/                      SQLAlchemy engine/session scaffold
│   ├── tests/                       pytest, fake providers, parser unit tests; no network
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  terminal layout, ?t=TICKER deep links
│   │   ├── api/                     typed fetch client + types
│   │   ├── components/              PriceChart, LineChart, Fundamentals/News/Macro panels, ...
│   │   ├── lib/format.ts            number/date formatting
│   │   └── styles/global.css        terminal theme
│   ├── vite.config.ts               dev proxy /api -> backend
│   └── package.json
├── docs/                            ARCHITECTURE.md, ROADMAP.md, DATA_SOURCES.md
├── scripts/                         setup / dev / check (PowerShell + bash)
├── .vscode/                         interpreter, formatters, debug configs
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
└── CLAUDE.md                        notes for AI-assisted development
```

## Prerequisites

- Python 3.12+
- Node.js 20.19+ (24 recommended) and npm
- Git
- Docker Desktop (optional, only for the Compose workflow)

## Quick start (Windows PowerShell)

```powershell
git clone <repo-url> tradingterminal
cd tradingterminal
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # venv, pip, npm, .env
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1     # opens two windows
```

Then open http://localhost:5173 and type a ticker. The API docs live at
http://127.0.0.1:8000/docs. A view is linkable: http://localhost:5173/?t=NVDA

Manual equivalent, in two terminals:

```powershell
# terminal 1
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload

# terminal 2
cd frontend
npm install
npm run dev
```

## Quick start (macOS / Linux)

```bash
bash scripts/setup.sh
bash scripts/dev.sh
```

## Docker

```bash
docker compose up --build
```

Backend on http://localhost:8000, frontend on http://localhost:5173, both with hot reload.

## Using the terminal

1. Type a ticker in the command bar (`AAPL`, `NVDA`, `SAP.DE`, `7203.T`) and press Enter.
   Press `/` anywhere to focus the bar.
2. **Function codes** (Bloomberg style): `AAPL FA` loads Apple and jumps to Fundamentals;
   a code on its own (`CN`) applies to the current company. Codes: `GP` chart, `Q` quote,
   `DES` profile, `FA` fundamentals, `CN` news, `SPLC` supply chain, `ECO` macro,
   `W` watchlist, `HELP` for the list.
3. **Price**: pick a range (1D, 5D, 1M, 3M, 6M, YTD, 1Y, 5Y, MAX); intraday ranges
   refresh every minute. Hover for OHLC, change and volume; scroll to zoom, drag to pan.
4. **Watchlist**: add or remove symbols, click one to load it; quotes refresh every 30 s
   and the list is remembered in the browser.
5. **Fundamentals**: Annual / Quarterly tabs show statements with the newest period on
   the right; `*` marks a derived Q4. The Filings tab links straight to the SEC documents.
   Only US filers have EDGAR data.
6. **News**: filter headlines by keyword; click a related ticker chip to jump to that company.
7. **Macro**: click a tile to chart that series; 1Y / 5Y / MAX on the right.
8. **Supply chain**: the company's own 10-K is read first (seconds); the full-text search
   across other filers follows and takes up to a minute the first time, then is cached
   for a week. Click a node for the evidence sentences and filing links, "open" to
   re-centre on that company, "Rescan" to rebuild. US-listed companies only.

## Configuration

Copy `.env.example` to `.env` at the repo root. Everything has a working default.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Reported by `/health` |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` | Where uvicorn listens |
| `API_PREFIX` | `/api/v1` | API mount point |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed browser origins |
| `DATABASE_URL` | SQLite under `backend/data/` | SQLAlchemy URL (not used yet) |
| `SEC_EDGAR_USER_AGENT` | generic placeholder | The SEC asks for `AppName you@example.com` |
| `FRED_API_KEY` | empty | Optional; switches FRED from CSV to the JSON API |
| `VITE_API_BASE_URL` | empty | Frontend API base; empty uses the dev proxy |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness, version, active provider |
| GET | `/api/v1/companies/{ticker}` | Company profile |
| GET | `/api/v1/companies/{ticker}/quote` | Latest price snapshot with day/52-week ranges |
| GET | `/api/v1/quotes?tickers=AAPL,MSFT` | Lightweight quotes for up to 30 symbols (watchlist) |
| GET | `/api/v1/companies/{ticker}/history?range=6mo&interval=1d` | OHLCV bars |
| GET | `/api/v1/companies/{ticker}/news?limit=15` | Headlines |
| GET | `/api/v1/companies/{ticker}/fundamentals` | Annual + quarterly statements (SEC) |
| GET | `/api/v1/companies/{ticker}/filings?forms=10-K,10-Q,8-K&limit=20` | Filing index with links |
| GET | `/api/v1/companies/{ticker}/relationships?deep=true` | Suppliers, customers, competitors, partners mined from SEC filings, with evidence sentences |
| GET | `/api/v1/macro/dashboard` | Curated FRED series with change and YoY |
| GET | `/api/v1/macro/series/{id}?start=YYYY-MM-DD` | Observations for any FRED series |

Upstream failures surface as HTTP 502 with the provider name in the message.
Interactive docs: `/docs` (Swagger) and `/redoc`.

## Development

Run everything CI runs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
```

Individually:

```powershell
cd backend;  ruff check .; ruff format .; pytest
cd frontend; npm run lint; npm run typecheck; npm run format; npm run build
```

### Adding a data source

1. Define the response schema in `backend/app/models/`.
2. Add the capability to an interface in `backend/app/services/providers/base.py`
   (or create a new interface).
3. Implement it in a new `providers/<source>_provider.py`. Read keys from `app/config.py`,
   wrap upstream calls in `cache.get_or_set`, raise `UpstreamError` on failures.
4. Expose it in `backend/app/api/routes/`, inject the provider through `deps.py`.
5. Add a fake in `tests/conftest.py` and route tests. Tests must not use the network.
   Put parsing in a pure module and unit-test it against a small fixture.
6. Add the TypeScript type in `frontend/src/api/types.ts`, a client call, and a panel.

## Troubleshooting

- **`scripts\*.ps1` won't run:** PowerShell blocks unsigned scripts by default. Use the
  `-ExecutionPolicy Bypass` form shown above, or run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Frontend shows API OFFLINE:** the backend is not running on port 8000, or
  `VITE_PROXY_TARGET` points elsewhere.
- **404 for a valid ticker, or an empty chart:** Yahoo is rate-limiting or the symbol
  needs a suffix (e.g. `SAP.DE`, `7203.T`). Wait a minute and retry.
- **Fundamentals say "No SEC filings found":** the company does not file with the SEC
  (non-US listing) or the ticker differs from the SEC's (try the class, e.g. `BRK-B`).
- **502 from EDGAR mentioning 403:** set `SEC_EDGAR_USER_AGENT` to `AppName you@example.com`.
- **Port already in use:** change `API_PORT` in `.env` and the proxy target in
  `frontend/vite.config.ts`, or stop the other process.
- **Backend keeps serving old code after a restart (Windows):** uvicorn's reload worker can
  outlive its parent and keep the port. Run `scripts\stop-backend.ps1` to kill the whole
  process tree, then start again.
- **Reset local data:** delete `backend/data/terminal.db`; migrations recreate it on the
  next start. The persistent cache lives there too.
