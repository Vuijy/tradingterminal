# Architecture

```
browser (React + TanStack Query)
   |  /api/v1/...  (Vite dev proxy, or VITE_API_BASE_URL in prod)
   v
FastAPI  app/api/routes/*          thin HTTP layer, validation, status codes
   |
   v
services  app/services/*           business logic, caching, combining sources
   |
   v
providers app/services/providers/* one class per external source (yfinance, EDGAR, FRED)
   |
   v
external APIs / libraries
```

## Principles

- **Providers are swappable.** Routes depend on the abstract interface in
  `providers/base.py` via FastAPI dependencies, never on a concrete vendor class.
  Tests inject a fake provider; no test touches the network.
- **Schemas are vendor-neutral.** Everything the API returns is a Pydantic model in
  `app/models/` with a `source` field. Vendor field names stop at the provider.
- **Cache before you scale.** All free sources rate-limit. Add an in-memory TTL cache
  in the service layer first, persist to SQLite (`app/db/`) when data must survive restarts.
- **Config is centralised** in `app/config.py` (pydantic-settings) and read from `.env`.
- **The frontend is a shell of panels.** Each panel owns one query. New data domains
  (fundamentals, news, macro, relationships) are new panels plus new API routes.

## Planned modules

| Module | Backend | Frontend |
|---|---|---|
| Market data | `providers/yfinance_provider.py` (done), history endpoint | Quote panel (done), price chart |
| Fundamentals | `providers/edgar_provider.py`, ticker->CIK map, companyfacts parsing | Statements panel |
| Macro | `providers/fred_provider.py`, series registry | Macro dashboard panel |
| News | `yfinance` news in the yfinance provider | News panel |
| Relationships | filing text extraction, `Relationship` ORM model | Supply-chain graph panel |

## Data model sketch (future)

- `Company(cik, ticker, name, sic, exchange)`
- `Relationship(from_cik, to_cik, type: supplier|customer|competitor|partner, source_doc, confidence)`
- `FactCache(cik, concept, period, value, fetched_at)`
- `SeriesCache(series_id, date, value, fetched_at)`
