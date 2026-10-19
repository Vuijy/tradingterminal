"""FRED (Federal Reserve Bank of St. Louis) macro series.

Two access paths:
  - With `FRED_API_KEY`: the official JSON API, which also returns titles and units.
  - Without a key: the public CSV download behind every FRED chart
    (`fredgraph.csv?id=...`). Same numbers, no metadata, so display metadata comes
    from app/services/macro_registry.py.
"""

import csv
import io
from datetime import date
from typing import Any

import httpx

from app.models.macro import MacroObservation, MacroSeries
from app.services.cache import cache
from app.services.errors import UpstreamError
from app.services.macro_registry import SERIES_BY_ID
from app.services.providers.base import MacroProvider

API_BASE = "https://api.stlouisfed.org/fred"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SERIES_TTL = 3600


def parse_fred_csv(text: str) -> list[MacroObservation]:
    """Parse `observation_date,<ID>` CSV. Missing values are written as '.'."""
    out: list[MacroObservation] = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 2:
        return out
    for row in reader:
        if len(row) < 2 or row[1] in ("", "."):
            continue
        try:
            out.append(MacroObservation(date=date.fromisoformat(row[0]), value=float(row[1])))
        except ValueError:
            continue
    return out


def parse_fred_api(payload: dict[str, Any]) -> list[MacroObservation]:
    out: list[MacroObservation] = []
    for obs in payload.get("observations", []):
        raw = obs.get("value")
        if raw in (None, "", "."):
            continue
        try:
            out.append(MacroObservation(date=date.fromisoformat(obs["date"]), value=float(raw)))
        except (KeyError, ValueError):
            continue
    return out


class FredProvider(MacroProvider):
    name = "fred"

    def __init__(self, api_key: str = "", timeout: float = 30.0) -> None:
        self._api_key = api_key.strip()
        self._timeout = timeout

    async def get_series(self, series_id: str, start: date | None = None) -> MacroSeries | None:
        sid = series_id.strip().upper()
        key = f"fred:series:{sid}:{start.isoformat() if start else 'all'}"
        return await cache.get_or_set(
            key, SERIES_TTL, lambda: self._fetch(sid, start), persist=True
        )

    async def _fetch(self, sid: str, start: date | None) -> MacroSeries | None:
        meta = SERIES_BY_ID.get(sid)
        title = meta.title if meta else sid
        unit = meta.unit if meta else None
        frequency = meta.frequency if meta else None

        if self._api_key:
            observations, api_meta = await self._fetch_api(sid, start)
            if api_meta:
                title = title if meta else str(api_meta.get("title") or sid)
                unit = unit or api_meta.get("units_short")
                frequency = frequency or api_meta.get("frequency_short")
        else:
            observations = await self._fetch_csv(sid, start)
        if observations is None:
            return None
        return MacroSeries(
            series_id=sid,
            title=title,
            unit=unit,
            frequency=frequency,
            observations=observations,
            source=self.name,
        )

    async def _fetch_csv(self, sid: str, start: date | None) -> list[MacroObservation] | None:
        params: dict[str, str] = {"id": sid}
        if start:
            params["cosd"] = start.isoformat()
        response = await self._get(CSV_URL, params)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise UpstreamError(self.name, f"HTTP {response.status_code} for series {sid}")
        return parse_fred_csv(response.text)

    async def _fetch_api(
        self, sid: str, start: date | None
    ) -> tuple[list[MacroObservation] | None, dict[str, Any] | None]:
        common = {"series_id": sid, "api_key": self._api_key, "file_type": "json"}
        obs_params = dict(common)
        if start:
            obs_params["observation_start"] = start.isoformat()
        obs_resp = await self._get(f"{API_BASE}/series/observations", obs_params)
        if obs_resp.status_code == 400:  # FRED's answer for an unknown series id
            return None, None
        if obs_resp.status_code >= 400:
            raise UpstreamError(self.name, f"HTTP {obs_resp.status_code} for series {sid}")
        meta_resp = await self._get(f"{API_BASE}/series", common)
        api_meta: dict[str, Any] | None = None
        if meta_resp.status_code == 200:
            seriess = meta_resp.json().get("seriess") or []
            api_meta = seriess[0] if seriess else None
        return parse_fred_api(obs_resp.json()), api_meta

    async def _get(self, url: str, params: dict[str, str]) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "TradingTerminal/0.1"},
            ) as client:
                return await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise UpstreamError(self.name, str(exc)) from exc
