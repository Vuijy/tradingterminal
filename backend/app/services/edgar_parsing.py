"""Turn SEC `companyfacts` JSON into tidy annual and quarterly statements.

Pure functions, no I/O, so they can be unit-tested against small fixtures.

Why this is not trivial: companyfacts lists every value a company ever reported for a
concept, across every filing. A single fiscal year therefore appears several times
(original 10-K, then as a comparative column in the next two 10-Ks, possibly restated),
and `fy`/`fp` describe the *filing*, not the fact's own period. We therefore:

1. key facts by their own (start, end) period and keep the most recently filed value,
2. classify periods by duration (about a year -> annual, about a quarter -> quarterly),
3. derive Q4 as FY minus Q1-Q3, because companies do not report Q4 on its own,
4. attach balance-sheet instants to the period whose end date they match.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.models.fundamentals import ConceptMeta, Filing, FinancialPeriod, Financials

ANNUAL_FORMS = ("10-K", "20-F", "40-F")
QUARTERLY_FORMS = ("10-Q",)
ALL_FORMS = ANNUAL_FORMS + QUARTERLY_FORMS
ANNUAL_DAYS = (340, 380)  # 52/53-week fiscal years included
QUARTER_DAYS = (80, 100)
CURRENT_PERIOD_LAG_DAYS = 120  # a filing covering its own period is filed within ~45 days
MAX_ANNUAL = 10
MAX_QUARTERLY = 12


@dataclass(frozen=True)
class Concept:
    key: str
    label: str
    kind: str  # "duration" or "instant"
    tags: tuple[str, ...]  # XBRL tags in order of preference
    unit: str = "USD"
    taxonomy: str = "us-gaap"


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        "revenue",
        "Revenue",
        "duration",
        ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    ),
    Concept(
        "cost_of_revenue",
        "Cost of revenue",
        "duration",
        ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    ),
    Concept("gross_profit", "Gross profit", "duration", ("GrossProfit",)),
    Concept("rnd", "R&D expense", "duration", ("ResearchAndDevelopmentExpense",)),
    Concept("operating_income", "Operating income", "duration", ("OperatingIncomeLoss",)),
    Concept("net_income", "Net income", "duration", ("NetIncomeLoss", "ProfitLoss")),
    Concept(
        "eps_diluted",
        "EPS (diluted)",
        "duration",
        ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
        unit="USD/shares",
    ),
    Concept(
        "operating_cash_flow",
        "Operating cash flow",
        "duration",
        ("NetCashProvidedByUsedInOperatingActivities",),
    ),
    Concept(
        "capex",
        "Capital expenditure",
        "duration",
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",  # e.g. NVIDIA: property, equipment and intangibles
            "PaymentsForCapitalImprovements",
        ),
    ),
    Concept("total_assets", "Total assets", "instant", ("Assets",)),
    Concept("total_liabilities", "Total liabilities", "instant", ("Liabilities",)),
    Concept(
        "equity",
        "Shareholders' equity",
        "instant",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
    ),
    Concept("cash", "Cash & equivalents", "instant", ("CashAndCashEquivalentsAtCarryingValue",)),
    Concept(
        "long_term_debt", "Long-term debt", "instant", ("LongTermDebtNoncurrent", "LongTermDebt")
    ),
    Concept(
        "shares_outstanding",
        "Shares outstanding",
        "instant",
        ("CommonStockSharesOutstanding",),
        unit="shares",
    ),
)

CONCEPT_META = [ConceptMeta(key=c.key, label=c.label, kind=c.kind, unit=c.unit) for c in CONCEPTS]


@dataclass(frozen=True)
class _Fact:
    start: date | None
    end: date
    val: float
    filed: date
    form: str
    fy: int | None
    fp: str | None
    rank: int  # index of the tag that produced it (lower is preferred)

    @property
    def days(self) -> int:
        return (self.end - self.start).days if self.start else 0

    @property
    def is_current_period(self) -> bool:
        """True when the filing covers this very period (not a comparative column)."""
        return (self.filed - self.end).days <= CURRENT_PERIOD_LAG_DAYS


@dataclass
class _Period:
    start: date | None
    end: date
    values: dict[str, float] = field(default_factory=dict)
    src: _Fact | None = None  # the original filing for this period
    derived: bool = False

    def note(self, f: _Fact) -> None:
        """Remember the filing that first reported this period (best metadata source)."""
        cur = self.src
        if cur is None:
            self.src = f
            return
        if (f.is_current_period and not cur.is_current_period) or (
            f.is_current_period == cur.is_current_period and f.filed < cur.filed
        ):
            self.src = f


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _form_ok(form: str, allowed: tuple[str, ...]) -> bool:
    return any(form.startswith(a) for a in allowed)


def _collect(facts_json: dict[str, Any], concept: Concept) -> list[_Fact]:
    taxonomy = facts_json.get("facts", {}).get(concept.taxonomy, {})
    out: list[_Fact] = []
    for rank, tag in enumerate(concept.tags):
        raw_facts = taxonomy.get(tag, {}).get("units", {}).get(concept.unit, [])
        for raw in raw_facts:
            end = _parse_date(raw.get("end"))
            val = raw.get("val")
            if end is None or val is None:
                continue
            try:
                val_f = float(val)
            except (TypeError, ValueError):
                continue
            fy = raw.get("fy")
            out.append(
                _Fact(
                    start=_parse_date(raw.get("start")),
                    end=end,
                    val=val_f,
                    filed=_parse_date(raw.get("filed")) or date.min,
                    form=str(raw.get("form") or ""),
                    fy=fy if isinstance(fy, int) else None,
                    fp=raw.get("fp"),
                    rank=rank,
                )
            )
    return out


def _pick(facts: Iterable[_Fact], key_fn: Callable[[_Fact], Any]) -> dict[Any, _Fact]:
    """One fact per period: preferred tag wins, then the most recently filed value."""
    best: dict[Any, _Fact] = {}
    for f in facts:
        k = key_fn(f)
        cur = best.get(k)
        if cur is None or (f.rank, -f.filed.toordinal()) < (cur.rank, -cur.filed.toordinal()):
            best[k] = f
    return best


def _is_annual(f: _Fact) -> bool:
    return f.start is not None and ANNUAL_DAYS[0] <= f.days <= ANNUAL_DAYS[1]


def _is_quarter(f: _Fact) -> bool:
    return f.start is not None and QUARTER_DAYS[0] <= f.days <= QUARTER_DAYS[1]


def _quarter_label(p: _Period, annual: list[_Period]) -> tuple[int, str] | None:
    """(fiscal_year, 'Qn') for a quarterly period, or None if it cannot be placed."""
    if p.start is None:
        return None
    for a in annual:
        if a.start is not None and a.start <= p.start and p.end <= a.end:
            n = round(((p.end - a.start).days + 1) / 91.3)
            return a.end.year, f"Q{min(4, max(1, n))}"
    src = p.src
    if src is not None and src.fy is not None:
        if src.fp in ("Q1", "Q2", "Q3"):
            return src.fy, src.fp
        if src.fp == "FY":  # a ~90-day duration reported inside a 10-K is the fourth quarter
            return src.fy, "Q4"
    return None


def _to_model(
    p: _Period, fiscal_year: int, fiscal_period: str, instants: dict[date, dict[str, float]]
) -> FinancialPeriod:
    merged = dict(p.values)
    merged.update(instants.get(p.end, {}))
    if merged.get("gross_profit") is None:
        rev, cost = merged.get("revenue"), merged.get("cost_of_revenue")
        if rev is not None and cost is not None:
            merged["gross_profit"] = rev - cost
    label = f"FY{fiscal_year}" if fiscal_period == "FY" else f"{fiscal_period} FY{fiscal_year}"
    return FinancialPeriod(
        period=label,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        start=p.start,
        end=p.end,
        filed=p.src.filed if p.src and p.src.filed != date.min else None,
        form=p.src.form if p.src else None,
        derived=p.derived,
        values={c.key: merged.get(c.key) for c in CONCEPTS},
    )


def _merge(periods: dict[tuple[date, date], _Period], facts: list[_Fact], key: str) -> None:
    """Every filing that mentioned a period contributes metadata; then store the winning value."""
    for f in facts:
        periods.setdefault((f.start, f.end), _Period(f.start, f.end)).note(f)  # type: ignore[arg-type]
    for k, f in _pick(facts, lambda f: (f.start, f.end)).items():
        periods[k].values[key] = f.val


def build_financials(
    ticker: str, cik: int, entity_name: str, facts_json: dict[str, Any], source: str
) -> Financials:
    annual: dict[tuple[date, date], _Period] = {}
    quarterly: dict[tuple[date, date], _Period] = {}
    instants: dict[date, dict[str, float]] = {}

    for concept in CONCEPTS:
        facts = _collect(facts_json, concept)
        if concept.kind == "duration":
            annual_facts = [f for f in facts if _is_annual(f) and _form_ok(f.form, ANNUAL_FORMS)]
            _merge(annual, annual_facts, concept.key)
            quarter_facts = [f for f in facts if _is_quarter(f) and _form_ok(f.form, ALL_FORMS)]
            _merge(quarterly, quarter_facts, concept.key)
        else:
            instant_facts = (f for f in facts if f.start is None and _form_ok(f.form, ALL_FORMS))
            for f in _pick(instant_facts, lambda f: f.end).values():
                instants.setdefault(f.end, {})[concept.key] = f.val

    # One annual period per fiscal year (the richer one wins if a transition year overlaps).
    by_year: dict[int, _Period] = {}
    for p in annual.values():
        cur = by_year.get(p.end.year)
        if cur is None or (len(p.values), p.end) > (len(cur.values), cur.end):
            by_year[p.end.year] = p
    annual_all = sorted(by_year.values(), key=lambda p: p.end, reverse=True)

    quarters: list[tuple[_Period, int, str]] = []
    for p in quarterly.values():
        label = _quarter_label(p, annual_all)
        if label is not None:
            quarters.append((p, label[0], label[1]))

    # Derive Q4 = FY - (Q1 + Q2 + Q3) where all three quarters are known.
    for a in annual_all:
        if a.start is None:
            continue
        inside = [
            (q, fp) for q, _fy, fp in quarters if q.start and q.start >= a.start and q.end <= a.end
        ]
        if len(inside) != 3 or {fp for _, fp in inside} != {"Q1", "Q2", "Q3"}:
            continue
        values: dict[str, float] = {}
        for c in CONCEPTS:
            if c.kind != "duration":
                continue
            total = a.values.get(c.key)
            parts = [q.values.get(c.key) for q, _ in inside]
            if total is None or any(v is None for v in parts):
                continue
            values[c.key] = total - sum(v for v in parts if v is not None)
        if not values:
            continue
        q4 = _Period(
            start=max(q.end for q, _ in inside) + timedelta(days=1),
            end=a.end,
            values=values,
            src=a.src,
            derived=True,
        )
        quarters.append((q4, a.end.year, "Q4"))

    quarters.sort(key=lambda item: item[0].end, reverse=True)

    return Financials(
        ticker=ticker,
        cik=cik,
        entity_name=entity_name,
        concepts=CONCEPT_META,
        annual=[_to_model(p, p.end.year, "FY", instants) for p in annual_all[:MAX_ANNUAL]],
        quarterly=[_to_model(p, fy, fp, instants) for p, fy, fp in quarters[:MAX_QUARTERLY]],
        source=source,
    )


def parse_filings(
    cik: int, submissions: dict[str, Any], forms: set[str] | None, limit: int
) -> list[Filing]:
    recent = submissions.get("filings", {}).get("recent", {})
    keys = (
        "accessionNumber",
        "filingDate",
        "reportDate",
        "form",
        "primaryDocument",
        "primaryDocDescription",
    )
    out: list[Filing] = []
    for accn, filed, report, form, doc, desc in zip(
        *(recent.get(k, []) for k in keys), strict=False
    ):
        if forms and form not in forms:
            continue
        filed_d = _parse_date(filed)
        if filed_d is None or not accn:
            continue
        if doc:
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"
        else:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
        out.append(
            Filing(
                accession=accn,
                form=form,
                filed=filed_d,
                report_date=_parse_date(report),
                description=desc or None,
                url=url,
            )
        )
        if len(out) >= limit:
            break
    return out
