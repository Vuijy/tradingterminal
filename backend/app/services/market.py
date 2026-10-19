"""Shared rules for price-history requests (what Yahoo will actually serve)."""

RANGES = ("1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max")
INTERVALS = ("1m", "2m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo")
INTRADAY_INTERVALS = frozenset({"1m", "2m", "5m", "15m", "30m", "1h"})


def validate_history_params(range_: str, interval: str) -> str | None:
    """Return an error message if the combination is invalid, else None."""
    if range_ not in RANGES:
        return f"range must be one of {', '.join(RANGES)}"
    if interval not in INTERVALS:
        return f"interval must be one of {', '.join(INTERVALS)}"
    if interval == "1m" and range_ not in ("1d", "5d"):
        return "1m bars are only available for range 1d or 5d"
    if interval in ("2m", "5m", "15m", "30m") and range_ not in ("1d", "5d", "1mo"):
        return f"{interval} bars are only available for range 1d, 5d or 1mo"
    if interval == "1h" and range_ in ("2y", "5y", "10y", "max"):
        return "1h bars are only available for ranges up to 1y"
    return None
