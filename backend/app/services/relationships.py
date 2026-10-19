"""Assemble the supply-chain graph of a company from SEC filings.

Two sources of evidence, both free:

1. The company's own latest 10-K: who it names as customers, suppliers, competitors.
2. Other companies' 10-Ks found through EDGAR full-text search that name the company
   (a supplier disclosing "Apple accounted for 67% of revenue" is evidence that it
   supplies Apple). Full-text search only says "this document contains the phrase", so
   every candidate document is downloaded and the sentences are classified before
   anything is reported.

Every extracted sentence is stored in SQLite (`mentions`) so later lookups of either
company reuse it, and the assembled graph is cached per company (`relationship_runs`).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.db.models import AnalyzedFiling, RelationshipRun
from app.db.models import Mention as MentionRow
from app.db.session import get_session_factory
from app.models.relationships import (
    AnonymousCustomer,
    RelatedCompany,
    RelationshipEvidence,
    RelationshipGraph,
)
from app.services.entity_resolution import EntityResolver, Registrant, Resolution, normalize
from app.services.filing_text import FilingTextStore
from app.services.providers.edgar_provider import EdgarProvider
from app.services.providers.efts import EdgarFullTextSearch
from app.services.relationship_extraction import (
    KIND_ANON,
    KIND_COMPETITOR,
    KIND_CUSTOMER,
    KIND_PARTNER,
    KIND_SUPPLIER,
    STRONG_PATTERNS,
    Mention,
    extract_own_mentions,
    extract_target_mentions,
)

log = logging.getLogger(__name__)

MAX_REVERSE_DOCS = 30
MAX_PER_RELATION = 40
MIN_CONFIDENCE = 0.45
RUN_TTL = dt.timedelta(days=7)
SEARCH_WINDOW_DAYS = 550  # roughly the latest annual report of every filer
SEARCH_CONCURRENCY = 3

_LEGAL_WORDS = {
    "inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "company", "ltd", "ltd.",
    "limited", "plc", "llc", "holdings", "holding", "group", "the", "new", "/de/", "/de", "sa", "nv",
}  # fmt: skip


@dataclass(frozen=True)
class FilingRef:
    cik: int
    name: str
    ticker: str | None
    form: str
    filed: dt.date | None
    accession: str
    url: str


def name_variants(title: str) -> list[str]:
    """['Apple Inc.', 'Apple'] from the SEC title; used for search phrases and text matching."""
    words = title.replace(",", " ").split()
    while words and words[-1].lower() in _LEGAL_WORDS:
        words.pop()
    short = " ".join(words).strip()
    variants = [title.strip()]
    if short and short.lower() != title.strip().lower():
        variants.append(short)
    return [v for v in variants if len(v) >= 3]


def display_name(title: str) -> str:
    return title.title() if title.isupper() else title


def search_templates(variants: list[str]) -> list[tuple[str, str, int]]:
    """(query, direction, weight). direction: 'customer' = filer names X as its customer,
    'supplier' = filer names X as its supplier, 'competitor'."""
    short = variants[-1]
    legal = variants[0]
    out: list[tuple[str, str, int]] = []
    for v in dict.fromkeys([short, legal]):
        out += [
            (f'"{v} accounted for"', "customer", 5),
            (f'"sales to {v}"', "customer", 5),
            (f'"{v} represented"', "customer", 3),
            (f'"customers include {v}"', "customer", 3),
            (f'"customers such as {v}"', "customer", 2),
            (f'"customers including {v}"', "customer", 2),
            (f'"competitors include {v}"', "competitor", 3),
            (f'"compete with {v}"', "competitor", 3),
            (f'"competitors such as {v}"', "competitor", 2),
            (f'"competitors like {v}"', "competitor", 2),
            (f'"competition from {v}"', "competitor", 2),
            (f'"supplied by {v}"', "supplier", 3),
            (f'"purchase" "from {v}"', "supplier", 1),
        ]
    out += [
        (f'"{short}" "our largest customer"', "customer", 2),
        (f'"{short}" "largest customers"', "customer", 1),
        (f'"{short}" "suppliers accounted for"', "supplier", 3),
        (f'"{short}" "sole source"', "supplier", 2),
        (f'"{short}" "our suppliers"', "supplier", 2),
        (f'"{short}" "largest suppliers"', "supplier", 2),
        (f'"{short} products" "resell"', "supplier", 2),
    ]
    return out


# --- graph assembly (pure) -------------------------------------------------------------


def _evidence(filing: FilingRef, m: Mention, method: str) -> RelationshipEvidence:
    return RelationshipEvidence(
        source_cik=filing.cik,
        source_name=display_name(filing.name),
        source_ticker=filing.ticker,
        form=filing.form,
        filed=filing.filed,
        accession=filing.accession,
        url=filing.url,
        section=m.section,
        snippet=m.sentence[:600],
        percent=m.percent if m.basis == "revenue" else None,
        method=method,  # type: ignore[arg-type]
        pattern=m.pattern,
    )


@dataclass
class _Bucket:
    key: str
    name: str
    ticker: str | None
    cik: int | None
    relation: str
    confidence: float = 0.0
    pct: float | None = None
    evidence: list[RelationshipEvidence] | None = None

    def add(self, ev: RelationshipEvidence, confidence: float) -> None:
        if self.evidence is None:
            self.evidence = []
        if any(e.accession == ev.accession and e.snippet == ev.snippet for e in self.evidence):
            return
        self.evidence.append(ev)
        self.confidence = min(
            0.99, max(self.confidence, confidence) + 0.03 * (len(self.evidence) - 1)
        )
        if ev.percent is not None and (self.pct is None or ev.percent > self.pct):
            self.pct = ev.percent


def assemble_graph(
    target: Registrant,
    own: list[tuple[FilingRef, Mention, Resolution | None]],
    reverse: list[tuple[FilingRef, Mention]],
    analyzed: list[str],
    status: str,
) -> RelationshipGraph:
    buckets: dict[tuple[str, str], _Bucket] = {}
    anonymous: dict[tuple[str, float | None], AnonymousCustomer] = {}

    def bucket(relation: str, key: str, name: str, ticker: str | None, cik: int | None) -> _Bucket:
        b = buckets.get((relation, key))
        if b is None:
            b = _Bucket(key, name, ticker, cik, relation)
            buckets[(relation, key)] = b
        return b

    own_relation = {KIND_CUSTOMER: "customer", KIND_SUPPLIER: "supplier",
                    KIND_COMPETITOR: "competitor", KIND_PARTNER: "partner"}  # fmt: skip
    for filing, m, res in own:
        if m.kind == KIND_ANON:
            ev = _evidence(filing, m, "own_filing")
            label = m.label or "customer"
            key = (label.lower(), m.percent)
            if key not in anonymous or (
                m.basis == "revenue" and anonymous[key].evidence.percent is None
            ):
                anonymous[key] = AnonymousCustomer(
                    label=label, percent=m.percent if m.basis == "revenue" else None, evidence=ev
                )
            continue
        relation = own_relation.get(m.kind)
        if relation is None or not m.entity_text:
            continue
        if res and res.cik == target.cik:
            continue
        if res is None and m.pattern not in STRONG_PATTERNS:
            continue
        if res and res.cik is not None:
            key, name, ticker, cik = f"cik:{res.cik}", display_name(res.name), res.ticker, res.cik
        else:
            key, name, ticker, cik = (
                f"name:{normalize(m.entity_text)}",
                (res.name if res else m.entity_text),
                None,
                None,
            )
        conf = m.confidence * (res.confidence if res else 0.8)
        bucket(relation, key, name, ticker, cik).add(_evidence(filing, m, "own_filing"), conf)

    # A filer F talking about the target X: F's "customer" is X -> F supplies X, and so on.
    reverse_relation = {KIND_CUSTOMER: "supplier", KIND_SUPPLIER: "customer",
                        KIND_COMPETITOR: "competitor", KIND_PARTNER: "partner"}  # fmt: skip
    for filing, m in reverse:
        relation = reverse_relation.get(m.kind)
        if relation is None or filing.cik == target.cik:
            continue
        b = bucket(
            relation, f"cik:{filing.cik}", display_name(filing.name), filing.ticker, filing.cik
        )
        b.add(_evidence(filing, m, "full_text_search"), m.confidence)

    # A weak keyword hit must not contradict a strong relation for the same company
    # (a supplier of X mentioned once near the word "purchase" is not also a customer).
    for (relation, key), b in list(buckets.items()):
        opposite = {"supplier": "customer", "customer": "supplier"}.get(relation)
        if opposite is None:
            continue
        other = buckets.get((opposite, key))
        if other and b.confidence < 0.6 <= other.confidence:
            del buckets[(relation, key)]

    def finish(relation: str) -> list[RelatedCompany]:
        # One weak keyword hit is not a relationship; it needs either a strong pattern or
        # several mentions (each extra mention adds confidence in _Bucket.add).
        items = [
            b
            for (r, _), b in buckets.items()
            if r == relation and b.evidence and b.confidence >= MIN_CONFIDENCE
        ]
        items.sort(key=lambda b: (b.pct or 0) * 0.01 + b.confidence, reverse=True)
        return [
            RelatedCompany(
                name=b.name,
                ticker=b.ticker,
                cik=b.cik,
                relation=relation,  # type: ignore[arg-type]
                confidence=round(b.confidence, 3),
                revenue_share_pct=b.pct,
                evidence=sorted(b.evidence or [], key=lambda e: e.percent or 0, reverse=True)[:6],
            )
            for b in items[:MAX_PER_RELATION]
        ]

    anon = sorted(anonymous.values(), key=lambda a: a.percent or 0, reverse=True)
    return RelationshipGraph(
        ticker=target.ticker,
        cik=target.cik,
        name=display_name(target.title),
        suppliers=finish("supplier"),
        customers=finish("customer"),
        competitors=finish("competitor"),
        partners=finish("partner"),
        anonymous_customers=anon[:12],
        analyzed_filings=analyzed,
        status=status,  # type: ignore[arg-type]
        generated_at=dt.datetime.now(dt.UTC),
    )


# --- service ---------------------------------------------------------------------------


class RelationshipService:
    name = "sec-edgar"

    def __init__(
        self, edgar: EdgarProvider, efts: EdgarFullTextSearch, texts: FilingTextStore
    ) -> None:
        self._edgar = edgar
        self._efts = efts
        self._texts = texts
        self._resolver: EntityResolver | None = None
        self._resolver_at: float = 0.0

    async def get_graph(
        self, ticker: str, *, deep: bool, refresh: bool = False
    ) -> RelationshipGraph | None:
        resolver = await self.resolver()
        target = resolver.by_ticker(ticker.replace(".", "-"))
        if target is None:
            return None
        if not refresh:
            stored = await asyncio.to_thread(self._load_run, target.cik)
            if stored is not None and (stored.status == "complete" or not deep):
                return stored
        graph = await self.build(target, deep=deep, refresh=refresh)
        await asyncio.to_thread(self._save_run, graph)
        return graph

    async def resolver(self) -> EntityResolver:
        now = asyncio.get_running_loop().time()
        if self._resolver is None or now - self._resolver_at > 6 * 3600:
            table = await self._edgar.ticker_table()
            registrants = [Registrant(int(v[0]), k, str(v[1])) for k, v in table.items()]
            self._resolver = EntityResolver(registrants)
            self._resolver_at = now
        return self._resolver

    async def build(
        self, target: Registrant, *, deep: bool, refresh: bool = False
    ) -> RelationshipGraph:
        """refresh=True re-reads every candidate document (texts are cached on disk) so
        stored mentions produced by older extraction rules are replaced."""
        resolver = await self.resolver()
        variants = name_variants(target.title)
        analyzed: list[str] = []
        own: list[tuple[FilingRef, Mention, Resolution | None]] = []

        latest = await self._edgar.latest_filing(target.cik)
        if latest:
            filing = FilingRef(
                cik=target.cik,
                name=latest["name"] or target.title,
                ticker=target.ticker,
                form=latest["form"],
                filed=_date(latest["filed"]),
                accession=latest["accession"],
                url=latest["url"],
            )
            text = await self._texts.get_text(filing.cik, filing.accession, filing.url)
            mentions = await asyncio.to_thread(extract_own_mentions, text, variants)
            own = [
                (filing, m, resolver.resolve(m.entity_text) if m.entity_text else None)
                for m in mentions
            ]
            await asyncio.to_thread(self._store_own, filing, own)
            analyzed.append(filing.accession)

        reverse: list[tuple[FilingRef, Mention]] = await asyncio.to_thread(
            self._load_reverse, target.cik
        )
        status = "own_filing_only"
        if deep:
            candidates = await self._search_candidates(target, variants)
            known = set() if refresh else {f.accession for f, _ in reverse}
            todo = [c for c in candidates if c.accession not in known][:MAX_REVERSE_DOCS]
            redo = {c.accession for c in todo}
            reverse = [(f, m) for f, m in reverse if f.accession not in redo]
            results = await asyncio.gather(
                *(self._analyze_reverse(c, target, variants) for c in todo), return_exceptions=True
            )
            for c, r in zip(todo, results, strict=True):
                if isinstance(r, BaseException):
                    log.warning("reverse analysis failed for %s: %s", c.accession, r)
                    continue
                reverse.extend((c, m) for m in r)
                analyzed.append(c.accession)
            status = "complete"

        return assemble_graph(target, own, reverse, analyzed, status)

    # --- reverse search -----------------------------------------------------------------

    async def _search_candidates(self, target: Registrant, variants: list[str]) -> list[FilingRef]:
        start = dt.date.today() - dt.timedelta(days=SEARCH_WINDOW_DAYS)
        end = dt.date(2099, 12, 31)
        semaphore = asyncio.Semaphore(SEARCH_CONCURRENCY)
        scores: dict[int, float] = {}
        best: dict[int, FilingRef] = {}

        async def run(query: str, weight: int) -> None:
            async with semaphore:
                try:
                    hits, _ = await self._efts.search(query, forms="10-K", start=start, end=end)
                except Exception as exc:  # one bad template must not sink the whole scan
                    log.warning("EFTS query failed %s: %s", query, exc)
                    return
            for h in hits:
                if not h.is_primary or h.cik == target.cik or not h.form.startswith("10-K"):
                    continue
                ref = FilingRef(
                    h.cik,
                    h.entity_name,
                    h.ticker,
                    h.form,
                    h.file_date,
                    h.accession,
                    h.primary_doc_url,
                )
                cur = best.get(h.cik)
                if cur is None or (ref.filed or dt.date.min) > (cur.filed or dt.date.min):
                    best[h.cik] = ref
                scores[h.cik] = scores.get(h.cik, 0.0) + weight + min(h.score, 20) / 100

        await asyncio.gather(*(run(q, w) for q, _direction, w in search_templates(variants)))
        ranked = sorted(best.values(), key=lambda r: scores.get(r.cik, 0), reverse=True)
        return ranked

    async def _analyze_reverse(
        self, filing: FilingRef, target: Registrant, variants: list[str]
    ) -> list[Mention]:
        text = await self._texts.get_text(filing.cik, filing.accession, filing.url)
        mentions = await asyncio.to_thread(extract_target_mentions, text, variants)
        await asyncio.to_thread(self._store_reverse, filing, target, mentions)
        return mentions

    # --- storage ---------------------------------------------------------------------

    def _store_own(
        self, filing: FilingRef, own: list[tuple[FilingRef, Mention, Resolution | None]]
    ) -> None:
        with get_session_factory()() as db:
            self._upsert_filing(db, filing)
            db.execute(
                delete(MentionRow).where(
                    MentionRow.source_accession == filing.accession,
                    MentionRow.source_cik == filing.cik,
                )
            )
            for _, m, res in own:
                db.add(
                    MentionRow(
                        source_cik=filing.cik,
                        source_accession=filing.accession,
                        section=m.section,
                        kind=m.kind,
                        entity_text=(m.entity_text or m.label or "")[:256],
                        entity_cik=res.cik if res else None,
                        entity_ticker=res.ticker if res else None,
                        entity_name=(res.name if res else None),
                        confidence=m.confidence,
                        percent=m.percent if m.basis == "revenue" else None,
                        sentence=m.sentence[:2000],
                        pattern=m.pattern,
                    )
                )
            db.commit()

    def _store_reverse(
        self, filing: FilingRef, target: Registrant, mentions: list[Mention]
    ) -> None:
        with get_session_factory()() as db:
            self._upsert_filing(db, filing)
            db.execute(
                delete(MentionRow).where(
                    MentionRow.source_accession == filing.accession,
                    MentionRow.entity_cik == target.cik,
                )
            )
            for m in mentions:
                db.add(
                    MentionRow(
                        source_cik=filing.cik,
                        source_accession=filing.accession,
                        section=m.section,
                        kind=m.kind,
                        entity_text=(m.entity_text or "")[:256],
                        entity_cik=target.cik,
                        entity_ticker=target.ticker,
                        entity_name=target.title,
                        confidence=m.confidence,
                        percent=m.percent if m.basis == "revenue" else None,
                        sentence=m.sentence[:2000],
                        pattern=m.pattern,
                    )
                )
            db.commit()

    @staticmethod
    def _upsert_filing(db, filing: FilingRef) -> None:
        row = db.get(AnalyzedFiling, filing.accession)
        if row is None:
            db.add(
                AnalyzedFiling(
                    accession=filing.accession,
                    cik=filing.cik,
                    form=filing.form,
                    filed=filing.filed,
                    url=filing.url,
                    analyzed_at=dt.datetime.now(dt.UTC),
                    filer_name=filing.name[:256] if filing.name else None,
                    filer_ticker=filing.ticker,
                )
            )
        else:
            row.analyzed_at = dt.datetime.now(dt.UTC)
            row.filer_name = filing.name[:256] if filing.name else row.filer_name
            row.filer_ticker = filing.ticker or row.filer_ticker
        db.flush()

    def _load_reverse(self, target_cik: int) -> list[tuple[FilingRef, Mention]]:
        """Mentions of the target stored from earlier scans of other filers' documents."""
        out: list[tuple[FilingRef, Mention]] = []
        with get_session_factory()() as db:
            rows = db.execute(
                select(MentionRow, AnalyzedFiling)
                .join(AnalyzedFiling, AnalyzedFiling.accession == MentionRow.source_accession)
                .where(MentionRow.entity_cik == target_cik, MentionRow.source_cik != target_cik)
            ).all()
        resolver = self._resolver
        for m, f in rows:
            reg = resolver.by_cik(f.cik) if resolver else None
            filing = FilingRef(
                f.cik,
                f.filer_name or (reg.title if reg else f"CIK {f.cik}"),
                f.filer_ticker or (reg.ticker if reg else None),
                f.form,
                f.filed,
                f.accession,
                f.url,
            )
            out.append(
                (
                    filing,
                    Mention(
                        m.kind,
                        m.entity_text,
                        m.sentence,
                        0,
                        m.pattern or "",
                        m.confidence,
                        percent=m.percent,
                        basis="revenue" if m.percent is not None else None,
                        section=m.section,
                    ),
                )
            )
        return out

    def _load_run(self, cik: int) -> RelationshipGraph | None:
        with get_session_factory()() as db:
            row = db.get(RelationshipRun, cik)
            if row is None:
                return None
            generated = row.generated_at
            if generated.tzinfo is None:
                generated = generated.replace(tzinfo=dt.UTC)
            if dt.datetime.now(dt.UTC) - generated > RUN_TTL:
                return None
            try:
                return RelationshipGraph.model_validate_json(row.graph_json)
            except ValueError:
                return None

    def _save_run(self, graph: RelationshipGraph) -> None:
        with get_session_factory()() as db:
            row = db.get(RelationshipRun, graph.cik)
            payload = graph.model_dump_json()
            if row is None:
                db.add(
                    RelationshipRun(
                        cik=graph.cik,
                        ticker=graph.ticker,
                        status=graph.status,
                        generated_at=graph.generated_at,
                        graph_json=payload,
                    )
                )
            else:
                row.ticker, row.status, row.generated_at, row.graph_json = (
                    graph.ticker,
                    graph.status,
                    graph.generated_at,
                    payload,
                )
            db.commit()


def _date(value: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None
