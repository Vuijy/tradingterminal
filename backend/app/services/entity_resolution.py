"""Resolve company names found in filing prose to SEC registrants (CIK + ticker).

Pure, no I/O: the caller supplies the ticker table (company_tickers.json rows). Matching
is deliberately conservative: a wrong link between two companies is worse than no link.

Order: blocklist -> alias table -> exact normalised title -> unique prefix match (the
mention is the start of exactly one title, or one title is the start of the mention) ->
unique token match. Mega-caps are preferred on ties because filings talk about them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEGAL = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "llc", "lp", "holdings", "holding", "group", "the", "sa", "nv", "ag", "se", "spa", "ab",
    "oyj", "asa", "kk", "kgaa", "de", "cv", "bv", "new", "class", "trust", "and", "&",
}  # fmt: skip

# Words that look like company names but are not (or are too generic to link).
BLOCKLIST = {
    "customer",
    "customers",
    "company",
    "the company",
    "group",
    "corporation",
    "we",
    "our",
    "us",
    "apple hospitality",
    "apple isports",
    "u.s.",
    "united states",
    "us government",
    "government",
    "federal government",
    "department of defense",
    "state",
    "china",
    "europe",
    "asia",
    "americas",
    "north america",
    "emea",
    "apac",
    "japan",
    "korea",
    "taiwan",
    "iphone",
    "ipad",
    "mac",
    "windows",
    "android",
    "azure",
    "aws",
    "linux",
}

# Common names in prose that differ from the SEC title (SEC ticker; None = not an SEC filer).
ALIASES: dict[str, str | None] = {
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "youtube": "GOOGL",
    "facebook": "META",
    "meta": "META",
    "meta platforms": "META",
    "instagram": "META",
    "amazon": "AMZN",
    "amazon web services": "AMZN",
    "amazon.com": "AMZN",
    "microsoft": "MSFT",
    "apple": "AAPL",
    "nvidia": "NVDA",
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "intel": "INTC",
    "qualcomm": "QCOM",
    "broadcom": "AVGO",
    "tsmc": "TSM",
    "taiwan semiconductor": "TSM",
    "taiwan semiconductor manufacturing": "TSM",
    "asml": "ASML",
    "arm": "ARM",
    "arm holdings": "ARM",
    "dell": "DELL",
    "dell technologies": "DELL",
    "hp": "HPQ",
    "hp inc": "HPQ",
    "hewlett packard enterprise": "HPE",
    "hpe": "HPE",
    "super micro": "SMCI",
    "supermicro": "SMCI",
    "super micro computer": "SMCI",
    "coreweave": "CRWV",
    "oracle": "ORCL",
    "ibm": "IBM",
    "cisco": "CSCO",
    "salesforce": "CRM",
    "tesla": "TSLA",
    "gm": "GM",
    "general motors": "GM",
    "ford": "F",
    "ford motor": "F",
    "stellantis": "STLA",
    "toyota": "TM",
    "honda": "HMC",
    "rivian": "RIVN",
    "walmart": "WMT",
    "costco": "COST",
    "target": "TGT",
    "best buy": "BBY",
    "home depot": "HD",
    "verizon": "VZ",
    "at&t": "T",
    "t-mobile": "TMUS",
    "comcast": "CMCSA",
    "sony": "SONY",
    "samsung": None,
    "samsung electronics": None,
    "foxconn": None,
    "hon hai": None,
    "hon hai precision industry": None,
    "sk hynix": None,
    "lg": None,
    "lg electronics": None,
    "panasonic": None,
    "catl": None,
    "byd": None,
    "huawei": None,
    "xiaomi": None,
    "bosch": None,
    "volkswagen": None,
    "mercedes-benz": None,
    "bmw": None,
    "hyundai": None,
    "kia": None,
    "micron": "MU",
    "micron technology": "MU",
    "texas instruments": "TXN",
    "boeing": "BA",
    "airbus": None,
    "lockheed martin": "LMT",
    "raytheon": "RTX",
    "rtx": "RTX",
    "northrop grumman": "NOC",
    "general electric": "GE",
    "ge aerospace": "GE",
    "exxon": "XOM",
    "exxonmobil": "XOM",
    "chevron": "CVX",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC",
    "visa": "V",
    "mastercard": "MA",
    "paypal": "PYPL",
    "netflix": "NFLX",
    "disney": "DIS",
    "walt disney": "DIS",
    "pepsico": "PEP",
    "coca-cola": "KO",
    "coca cola": "KO",
    "procter & gamble": "PG",
    "johnson & johnson": "JNJ",
    "pfizer": "PFE",
    "merck": "MRK",
    "unitedhealth": "UNH",
    "cvs": "CVS",
    "fedex": "FDX",
    "ups": "UPS",
    "united parcel service": "UPS",
    "uber": "UBER",
    "airbnb": "ABNB",
    "shopify": "SHOP",
    "spotify": "SPOT",
    "adobe": "ADBE",
    "servicenow": "NOW",
    "snowflake": "SNOW",
    "palantir": "PLTR",
    "arista": "ANET",
    "arista networks": "ANET",
    "marvell": "MRVL",
    "marvell technology": "MRVL",
    "applied materials": "AMAT",
    "lam research": "LRCX",
    "kla": "KLAC",
    "skyworks": "SWKS",
    "qorvo": "QRVO",
    "corning": "GLW",
    "jabil": "JBL",
    "flex": "FLEX",
    "amkor": "AMKR",
    "amkor technology": "AMKR",
    "globalfoundries": "GFS",
}


@dataclass(frozen=True)
class Registrant:
    cik: int
    ticker: str
    title: str


@dataclass(frozen=True)
class Resolution:
    cik: int | None
    ticker: str | None
    name: str
    confidence: float
    method: str


def normalize(name: str) -> str:
    s = name.replace("’", "'").replace("'s", "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9&.\- ]+", " ", s)
    s = s.replace(".", "").replace("-", " ")
    tokens = [t for t in s.split() if t]
    while tokens and tokens[-1] in _LEGAL:
        tokens.pop()
    while tokens and tokens[0] in ("the",):
        tokens.pop(0)
    return " ".join(tokens)


def tokens_of(name: str) -> tuple[str, ...]:
    return tuple(t for t in normalize(name).split() if t not in _LEGAL)


class EntityResolver:
    def __init__(self, registrants: list[Registrant]) -> None:
        # company_tickers.json is ordered by market cap desc; keep the first (largest)
        # entry per normalised title and per CIK.
        self._by_norm: dict[str, Registrant] = {}
        self._by_ticker: dict[str, Registrant] = {}
        self._by_cik: dict[int, Registrant] = {}
        self._order: list[tuple[str, Registrant]] = []
        for r in registrants:
            self._by_ticker.setdefault(r.ticker.upper(), r)
            self._by_cik.setdefault(r.cik, r)
            norm = normalize(r.title)
            if norm and norm not in self._by_norm:
                self._by_norm[norm] = r
                self._order.append((norm, r))

    def by_ticker(self, ticker: str) -> Registrant | None:
        return self._by_ticker.get(ticker.upper())

    def by_cik(self, cik: int) -> Registrant | None:
        return self._by_cik.get(cik)

    def resolve(self, mention: str) -> Resolution | None:
        raw = mention.strip().strip(",;:")
        if not raw:
            return None
        norm = normalize(raw)
        if not norm or norm in BLOCKLIST or raw.lower() in BLOCKLIST:
            return None

        if norm in ALIASES or raw.lower() in ALIASES:
            ticker = ALIASES.get(norm, ALIASES.get(raw.lower()))
            if ticker is None:  # known non-filer: keep the name, no link
                return Resolution(None, None, raw, 0.9, "alias-nonfiler")
            reg = self._by_ticker.get(ticker)
            if reg:
                return Resolution(reg.cik, reg.ticker, reg.title, 0.95, "alias")

        reg = self._by_norm.get(norm)
        if reg:
            return Resolution(reg.cik, reg.ticker, reg.title, 0.9, "exact")

        toks = tokens_of(raw)
        if len(toks) == 0 or (len(toks) == 1 and len(toks[0]) < 4):
            return None  # single short word: too ambiguous ("arm", "on", "gap" ...)

        # Prefix match: the mention starts a unique registrant title, or vice versa.
        prefix_hits = [r for n, r in self._order if n.startswith(norm + " ")]
        if len(prefix_hits) == 1:
            return Resolution(
                prefix_hits[0].cik, prefix_hits[0].ticker, prefix_hits[0].title, 0.75, "prefix"
            )
        if len(prefix_hits) > 1:
            # company_tickers is market-cap ordered: accept the biggest only if it dwarfs
            # the ambiguity (first hit) and the mention has at least two tokens.
            if len(toks) >= 2:
                r = prefix_hits[0]
                return Resolution(r.cik, r.ticker, r.title, 0.55, "prefix-ambiguous")
            return None
        reverse_hits = [
            r for n, r in self._order if norm.startswith(n + " ") and len(n.split()) >= 2
        ]
        if len(reverse_hits) == 1:
            r = reverse_hits[0]
            return Resolution(r.cik, r.ticker, r.title, 0.7, "prefix-reverse")
        return None
