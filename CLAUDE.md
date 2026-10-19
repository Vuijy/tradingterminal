# CLAUDE.md — Trading Terminal

> Scope note: `..\CLAUDE.md` (in the parent Downloads folder) describes an unrelated
> Polymarket bot project. It does not apply to anything inside this repository.

## What this is

A web-based "mini Bloomberg terminal" for investors and stock traders. Type a ticker,
get a dashboard: TradingView-style price chart, quote, profile, SEC fundamentals and
filings, news, macro dashboard, and a supply-chain graph (suppliers, customers,
competitors) mined from SEC filings.

## Status and direction (read first when resuming)

- **Paused 2026-10-19 after the supply-chain milestone.** The owner is happy with the
  build and has stopped adding features broadly; the next step is choosing a niche user.
- Full decision log in `docs/DIRECTION.md`. Short version: favoured niches are the
  **small-cap / micro-cap specialist** (data verified available; extraction and XBRL tag
  handling need a calibration pass on small-cap filings first) and the **long-term,
  low-frequency researcher** ("know what you own": look-through exposure, thesis
  tracking, yearly 10-K check-in). Advised against: a risk-tolerance portfolio allocator
  and anything for high-frequency scalpers (free data is delayed; nothing here helps them).
- Do not resume the generic roadmap (ROADMAP.md "still to do" items) until the niche is
  chosen; build only what that user needs.
- Nothing is committed to git; the owner has not asked for commits.

## Data-source plan (agreed, do not substitute paid APIs)

| Domain | Source | Status |
|---|---|---|
| Market data (quotes, history, profiles) | `yfinance` (free Python library) | done |
| News | Yahoo Finance via `yfinance` (`yf.Search(...).news`) | done |
| Fundamentals (statements, filings) | SEC EDGAR APIs (free, needs User-Agent) | done |
| Macro series | FRED (CSV without key, JSON API with free key) | done |
| Relationships | 10-K text + EDGAR full-text search (`efts.sec.gov`) | done |

Details and endpoints: `docs/DATA_SOURCES.md`. Milestone order: `docs/ROADMAP.md`.
OpenBB was evaluated and rejected (same sources, heavy dependency); don't re-propose it.

## Stack and layout

- `backend/` Python 3.12, FastAPI, pydantic-settings, httpx, yfinance, SQLAlchemy + Alembic.
  Entry: `app/main.py`. Routes in `app/api/routes/`, schemas in `app/models/`,
  data sources in `app/services/providers/`, pure parsing in `app/services/edgar_parsing.py`,
  TTL cache in `app/services/cache.py` (+ SQLite second level `persistent_cache.py`).
  Supply chain: `filing_text.py` (HTML->text/sections/sentences, disk cache),
  `relationship_extraction.py` (regex rules; calibrated on real 10-Ks, keep tests green),
  `entity_resolution.py` (names->tickers, alias table), `providers/efts.py` (full-text
  search), `relationships.py` (orchestration, SQLite `mentions`, graph assembly).
- `frontend/` React 19 + TypeScript + Vite, TanStack Query, lightweight-charts 5.
  Panels in `src/components/` (one panel = one query), API client in `src/api/`.
- `docs/` architecture, roadmap, data sources. `scripts/` setup/dev/check helpers.

## Commands (run from repo root; Windows PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # first time
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1     # start both servers
powershell -ExecutionPolicy Bypass -File scripts\check.ps1   # ruff + pytest + eslint + tsc + prettier
```

Backend only: `cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload`
Frontend only: `cd frontend; npm run dev`
Deep link for manual testing: http://localhost:5173/?t=AAPL

Windows gotcha when running the backend from a script or background task: `uvicorn
--reload` runs a reloader plus a `multiprocessing` worker, and reloads are unreliable
when it is not attached to a console. Killing only the reloader leaves the worker alive
with an inherited copy of the port-8000 socket, still serving old code. Use
`powershell -ExecutionPolicy Bypass -File scripts\stop-backend.ps1` to stop the whole
tree, then start uvicorn again (without `--reload` when launched from a background
task). In an interactive window (`scripts\dev.ps1`) Ctrl+C works normally.

Database: SQLAlchemy models in `app/db/models.py`, Alembic migrations in
`backend/alembic/versions/`. Migrations run automatically at startup (`app/db/migrate.py`).
After changing a model, add a migration: `cd backend; alembic revision -m "what changed"`
and fill in upgrade/downgrade by hand (autogenerate also works against the dev SQLite file).
Tests use a throwaway SQLite database (see `tests/conftest.py`).

## Conventions

- Every external source lives behind a provider class (`providers/base.py` interfaces).
  Routes get providers through FastAPI dependencies, never by importing a vendor class.
- Every API payload carries a `source` field naming the provider.
- Wrap every upstream call in `cache.get_or_set(key, ttl, factory)`; all sources rate-limit.
  Raise `UpstreamError` for provider failures; the app maps it to HTTP 502.
- Keep parsing pure (no I/O) so it can be unit-tested on fixtures (see `edgar_parsing.py`).
- Tests never hit the network: override the three `get_*_provider` deps with fakes
  (see `tests/conftest.py`).
- Config only through `app/config.py` + `.env`. Never hardcode keys.
- Formatting: ruff (backend), prettier (frontend). Run `scripts\check.ps1` before finishing a task.
- API is versioned under `/api/v1`. Swagger UI at `/docs`.
- Chart colours and theme tokens live in `frontend/src/styles/global.css` (amber on black,
  green up, red down). Keep new panels on the same palette.
