"""Find supplier / customer / competitor statements in 10-K prose.

Pure functions over text. Two entry points:

- extract_own_mentions(text, self_variants): what a filer says about *others* (its
  customers, suppliers, competitors) in its own annual report.
- extract_target_mentions(text, variants): sentences in someone else's filing that
  mention the target company, classified by the surrounding wording. Used after a
  full-text search to confirm what the hit actually says.

Names come back as written; app.services.entity_resolution links them to tickers.
Percentages are the share of the *speaking filer's* revenue (or receivables, see basis).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.filing_text import find_sections, section_at, split_sentences

KIND_CUSTOMER = "customer_named"
KIND_ANON = "customer_anonymous"
KIND_SUPPLIER = "supplier"
KIND_COMPETITOR = "competitor"
KIND_PARTNER = "partner"

STRONG_PATTERNS = {
    "customer_pct", "customer_through", "customer_list", "supplier_from", "supplier_by",
    "supplier_list", "competitor_list", "compete_with",
}  # fmt: skip


@dataclass
class Mention:
    kind: str
    entity_text: str | None  # as written; None for anonymous customers
    sentence: str
    offset: int
    pattern: str
    confidence: float
    percent: float | None = None
    basis: str | None = None  # "revenue" | "receivables"
    label: str | None = None  # anonymous customers: "one customer", "Customer A"
    section: str | None = None
    extra: dict = field(default_factory=dict)


# --- name handling --------------------------------------------------------------------

_NAME = re.compile(
    r"(?:[A-Z][\w&'.\-]*|AT&T|3M)(?:\s+(?:of|de|&|and|the)\s+[A-Z][\w&'.\-]*|\s+[A-Z][\w&'.\-]*)*"
    r"(?:,?\s+(?:Inc|Corp|Co|Ltd|LLC|plc|N\.V|S\.A|AG|SE|L\.P|Limited|Corporation|Company|Incorporated)\.?)?"
)
_GENERIC = {
    "we", "our", "us", "the", "a", "an", "other", "others", "certain", "various", "many",
    "several", "some", "all", "each", "these", "those", "its", "their", "such", "including",
    "customers", "customer", "suppliers", "supplier", "vendors", "vendor", "companies",
    "company", "company's", "competitors", "competitor", "products", "services", "none", "no",
    "item", "note", "notes", "fiscal", "year", "years", "quarter", "inc", "corp", "ltd", "co",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "revenue", "revenues", "sales", "net", "total",
    "direct", "indirect", "group", "oems", "odms", "csps", "ai", "esg", "jv", "ipo", "sec",
    "gaap", "u.s", "united states", "china", "europe", "asia", "taiwan", "japan", "korea",
}  # fmt: skip
_ROLE_WORDS = re.compile(
    r"\b(manufacturers|providers?|officer|counsel|department|agreement|loan|credit|segment"
    r"|customers?|suppliers?|distributors?|resellers?|operators?|carriers?|retailers?"
    r"|technology partners?|cloud|platform|committee|board|government|agency)\b",
    re.I,
)
_FIRST_PERSON = re.compile(r"\b(we|our|us|the company|the company's|its|the registrant)\b", re.I)
_ANON = re.compile(
    r"(?:\b(?:no|one|two|three|four|five|six|ten|a single|a few|our largest|our top|its largest"
    r"|the largest|the top|significant|each of (?:our|its|the) (?:top|largest|significant)"
    r"|our (?:two|three|four|five|ten) largest|the company's (?:largest|top))\b[^,]{0,40}?"
    r"\b(?:customers?|clients?|distributors?|resellers?|direct customers?)\b"
    r"|\bcustomers? [A-Z](?:(?:,| and| &) ?[A-Z]\b)*)\s*(?:that|which|who|each|individually|in the aggregate)?\s*$",
    re.I,
)
_LEADING_JUNK = re.compile(
    r"^(?:including|include|included|such as|like|e\.g\.,?|namely|primarily|the|our|or|and|from|with|by|to|a|an)\s+",
    re.I,
)


def _split_list(text: str) -> list[str]:
    items = re.split(r",\s*(?:and\s+|or\s+)?|;\s*|\s+and\s+|\s+or\s+|\s+as well as\s+", text)
    return [i.strip(" .:;\"'()") for i in items if i and i.strip(" .:;\"'()")]


def _looks_like_acronym_junk(name: str) -> bool:
    bare = name.rstrip("s")
    return bare.isupper() and len(bare) <= 5 and name.lower() not in _KNOWN_ACRONYMS


_KNOWN_ACRONYMS = {"amd", "ibm", "hp", "hpe", "gm", "ups", "cvs", "rtx", "arm", "tsmc", "asml",
                   "sap", "nxp", "kla", "lg", "byd", "catl", "at&t", "3m", "ge", "bmw", "dell", "tsm"}  # fmt: skip


def names_in(text: str) -> list[str]:
    """Capitalised company-looking names from a comma/'and' separated fragment."""
    out: list[str] = []
    for item in _split_list(text):
        for _ in range(3):
            item = _LEADING_JUNK.sub("", item)
        m = _NAME.match(item)
        if not m:
            continue
        name = m.group(0).strip(" ,.")
        low = name.lower()
        if len(name) < 2 or low in _GENERIC or low.rstrip("'s") in _GENERIC:
            continue
        if _looks_like_acronym_junk(name) or _ROLE_WORDS.search(name):
            continue
        if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}", name):  # "September 27"
            continue
        out.append(name)
    return out


_PCT = r"\d{1,2}(?:\.\d+)?\s?%"
_QUAL = (
    r"(?:approximately |about |roughly |more than |over |in excess of |at least |nearly |almost )?"
)
_VERB = r"(?:accounted for|accounting for|represented|representing|comprised|comprising|constituted|contributed)"
_REVENUE = re.compile(r"\b(revenue|revenues|net sales|sales|turnover|billings|purchases)\b", re.I)
_RECEIVABLE = re.compile(r"\breceivable", re.I)


def _percents(text: str) -> list[float]:
    return [float(p.replace(" ", "").rstrip("%")) for p in re.findall(_PCT, text)]


def _basis_after(sentence: str, pos: int) -> str | None:
    window = sentence[pos : pos + 120]
    rev, rec = _REVENUE.search(window), _RECEIVABLE.search(window)
    if rev and (not rec or rev.start() < rec.start()):
        return "revenue"
    if rec:
        return "receivables"
    if _REVENUE.search(sentence):
        return "revenue"
    if _RECEIVABLE.search(sentence):
        return "receivables"
    return None


# --- patterns ------------------------------------------------------------------------

_CUSTOMER_PCT = re.compile(
    rf"(?P<subject>[^.;,]{{2,140}}?)\s+{_VERB}\s+{_QUAL}(?P<pcts>{_PCT}(?:[^%.;]{{0,60}}{_PCT})*)",
    re.I,
)
# "Apple, through sales to multiple distributors, ..., in the aggregate accounted for approximately 70%"
_CUSTOMER_THROUGH = re.compile(
    rf"(?P<name>[A-Z][^,.;]{{1,60}}),\s+(?:through|via|including)[^.;]{{0,300}}?,\s+(?:in the aggregate\s+)?"
    rf"{_VERB}\s+{_QUAL}(?P<pcts>{_PCT}(?:[^%.;]{{0,60}}{_PCT})*)",
)
_SUBJECT_PREFIX = re.compile(
    r"^(?:(?:direct|net|our|the company's|its|total)\s+)*(?:sales|revenue|revenues|shipments)\s+(?:to|from)\s+"
    r"|^(?:sales|revenue|revenues)\s+(?:to|from)\s+",
    re.I,
)
_LIST = r"(?P<list>[^;:]{3,420})"
_CUSTOMER_LIST = re.compile(
    rf"\b(?:customers?|clients?)\s+(?:include|included|including|such as|like|are|comprise)\s*:?\s*{_LIST}",
    re.I,
)
_SUPPLIER_FROM = re.compile(
    r"\b(?:purchase|purchases|purchased|purchasing|source|sources|sourced|sourcing|procure|procures|procured"
    r"|buy|buys|bought|obtain|obtains|license|licenses)\b[^.;]{0,90}?\bfrom\s+(?P<list>[A-Z][^;:]{2,240})",
)
_SUPPLIER_BY = re.compile(
    r"\b(?:supplied|manufactured|fabricated|assembled|hosted)\s+(?:to us\s+|for us\s+)?by\s+(?P<list>[A-Z][^;:]{2,200})",
)
_SUPPLIER_LIST = re.compile(
    rf"\b(?:suppliers?|vendors?|foundry|foundries|contract manufacturers?|manufacturing partners?)\s+"
    rf"(?:include|included|including|such as|like|are)\s*:?\s*{_LIST}",
    re.I,
)
_RELY = re.compile(
    r"\b(?:rely|relies|relying|depend|depends|depending)\s+(?:on|upon)\s+(?P<list>[A-Z][^.;,]{2,90})",
)
_COMPETITOR_LIST = re.compile(
    rf"\b(?:competitors?|competition)\s+(?:include|included|including|such as|like|are|from|primarily from|consists? of)\s*:?\s*{_LIST}",
    re.I,
)
_COMPETE_WITH = re.compile(
    r"\bcompet(?:e|es|ed|ing)\s+(?:directly\s+|primarily\s+|principally\s+)?(?:with|against)\s+(?P<list>[A-Z][^;:]{2,320})",
)
_PARTNER = re.compile(
    r"\b(?:partnership|partnered|partnering|collaboration|collaborate|collaborating|alliance|strategic agreement)\s+with\s+(?P<list>[A-Z][^.;,]{2,90})",
    re.I,
)


# --- own filing ----------------------------------------------------------------------


def extract_own_mentions(text: str, self_variants: list[str] | None = None) -> list[Mention]:
    sections = find_sections(text)
    self_rx = target_regex(self_variants) if self_variants else None
    out: list[Mention] = []
    for offset, sentence in split_sentences(text):
        if len(sentence) > 1500:
            continue
        section = section_at(sections, offset)
        if section in ("Item 9", "Item 9A", "Item 10", "Item 15"):
            continue
        found = _customer_mentions(sentence, offset, section) + _list_mentions(
            sentence, offset, section, first_person_only=True
        )
        for m in found:
            if m.entity_text and self_rx and self_rx.search(m.entity_text):
                continue  # the filer talking about itself ("produced by Ford Blue")
            out.append(m)
    return _dedupe(out)


def _customer_mentions(sentence: str, offset: int, section: str | None) -> list[Mention]:
    out: list[Mention] = []
    if not (_REVENUE.search(sentence) or _RECEIVABLE.search(sentence)):
        return out
    for m in _CUSTOMER_THROUGH.finditer(sentence):
        basis = _basis_after(sentence, m.end()) or "revenue"
        pcts = _percents(m.group("pcts"))
        for name in names_in(m.group("name")):
            out.append(
                Mention(
                    KIND_CUSTOMER,
                    name,
                    sentence,
                    offset,
                    "customer_through",
                    0.95 if basis == "revenue" else 0.6,
                    percent=pcts[0] if pcts else None,
                    basis=basis,
                    section=section,
                )
            )
    for m in _CUSTOMER_PCT.finditer(sentence):
        basis = _basis_after(sentence, m.end())
        if basis is None:
            continue
        subject = _SUBJECT_PREFIX.sub("", m.group("subject").strip(" ,"))
        pcts = _percents(m.group("pcts"))
        conf = 0.95 if basis == "revenue" else 0.6
        anon = _ANON.search(subject)
        if anon:
            label = anon.group(0).strip()
            out.extend(_anonymous(label, pcts, sentence, offset, conf * 0.9, basis, section))
            continue
        names = names_in(subject)
        if not names or len(subject) > 90:
            continue
        for i, name in enumerate(names):
            pct = (
                pcts[i]
                if len(pcts) == len(names)
                else (pcts[0] if len(names) == 1 and pcts else None)
            )
            out.append(
                Mention(
                    KIND_CUSTOMER,
                    name,
                    sentence,
                    offset,
                    "customer_pct",
                    conf,
                    percent=pct,
                    basis=basis,
                    section=section,
                )
            )
    return out


def _anonymous(
    label: str,
    pcts: list[float],
    sentence: str,
    offset: int,
    conf: float,
    basis: str,
    section: str | None,
) -> list[Mention]:
    letters = re.findall(r"\b([A-Z])\b", label)
    if letters and len(letters) == len(pcts) and len(letters) > 1:
        return [
            Mention(
                KIND_ANON,
                None,
                sentence,
                offset,
                "customer_pct",
                conf,
                percent=p,
                basis=basis,
                label=f"Customer {ch}",
                section=section,
            )
            for ch, p in zip(letters, pcts, strict=True)
        ]
    label = re.sub(
        r"\s+(?:that|which|who|each|individually|in the aggregate)$", "", label, flags=re.I
    )
    return [
        Mention(
            KIND_ANON,
            None,
            sentence,
            offset,
            "customer_pct",
            conf,
            percent=pcts[0] if pcts else None,
            basis=basis,
            label=label,
            section=section,
        )
    ]


def _list_mentions(
    sentence: str, offset: int, section: str | None, *, first_person_only: bool = False
) -> list[Mention]:
    """List-style statements. With first_person_only, the clause before the match must be
    about the filer ("we purchase ... from"), not a third party ("NVIDIA relies on ...")."""
    out: list[Mention] = []

    def ok(m: re.Match[str]) -> bool:
        return not first_person_only or bool(_FIRST_PERSON.search(sentence[: m.start() + 1]))

    for m in _CUSTOMER_LIST.finditer(sentence):
        if ok(m):
            for name in names_in(m.group("list")):
                out.append(
                    Mention(
                        KIND_CUSTOMER, name, sentence, offset, "customer_list", 0.6, section=section
                    )
                )
    for pat, pid, conf in (
        (_SUPPLIER_FROM, "supplier_from", 0.8),
        (_SUPPLIER_BY, "supplier_by", 0.8),
        (_SUPPLIER_LIST, "supplier_list", 0.75),
        (_RELY, "supplier_rely", 0.55),
    ):
        for m in pat.finditer(sentence):
            if ok(m):
                for name in names_in(m.group("list")):
                    out.append(
                        Mention(KIND_SUPPLIER, name, sentence, offset, pid, conf, section=section)
                    )
    for pat, pid in ((_COMPETITOR_LIST, "competitor_list"), (_COMPETE_WITH, "compete_with")):
        for m in pat.finditer(sentence):
            if ok(m):
                for name in names_in(m.group("list")):
                    out.append(
                        Mention(KIND_COMPETITOR, name, sentence, offset, pid, 0.75, section=section)
                    )
    for m in _PARTNER.finditer(sentence):
        if ok(m):
            for name in names_in(m.group("list")):
                out.append(
                    Mention(
                        KIND_PARTNER, name, sentence, offset, "partner_with", 0.4, section=section
                    )
                )
    return out


def _dedupe(mentions: list[Mention]) -> list[Mention]:
    seen: dict[tuple, Mention] = {}
    for m in mentions:
        key = (m.kind, (m.entity_text or m.label or "").lower(), m.offset)
        cur = seen.get(key)
        if cur is None or m.confidence > cur.confidence:
            seen[key] = m
    return list(seen.values())


# --- someone else's filing, looking for the target ----------------------------------


def target_regex(variants: list[str]) -> re.Pattern[str]:
    parts = [re.escape(v) for v in sorted({v for v in variants if v}, key=len, reverse=True)]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.I)


_SUPPLY_CUE = re.compile(
    r"\b(suppliers?|vendors?|sole[- ]source|single[- ]source|supply|supplies|supplied|purchase|purchases"
    r"|procure|source|sourced|components|gpus|chips|equipment|hardware|manufactur|licensed from)\w*",
    re.I,
)
_COMPETE_CUE = re.compile(r"\bcompet", re.I)
_CUSTOMER_CUE = re.compile(
    r"\b(customers?|sales to|revenue from|sell|sells|sold|resell|distribut)\w*", re.I
)
_PARTNER_CUE = re.compile(r"\b(partner|collaborat|alliance)\w*", re.I)
_NEAR = 140


def extract_target_mentions(text: str, variants: list[str]) -> list[Mention]:
    """Sentences mentioning the target, classified from the filer's point of view."""
    rx = target_regex(variants)
    sections = find_sections(text)
    out: list[Mention] = []
    for offset, sentence in split_sentences(text):
        if len(sentence) > 700 or not rx.search(sentence):
            continue
        section = section_at(sections, offset)
        if section in ("Item 9", "Item 9A", "Item 10", "Item 15"):
            continue
        hit = _classify_target_sentence(sentence, rx, offset, section)
        if hit is not None:
            out.append(hit)
    return out


def _near(sentence: str, rx: re.Pattern[str], cue: re.Pattern[str]) -> bool:
    positions = [m.start() for m in rx.finditer(sentence)]
    return any(abs(c.start() - p) <= _NEAR for c in cue.finditer(sentence) for p in positions)


def _classify_target_sentence(
    sentence: str, rx: re.Pattern[str], offset: int, section: str | None
) -> Mention | None:
    def target_in(names: list[str]) -> bool:
        return any(rx.search(n) for n in names)

    first = rx.search(sentence)
    display = first.group(0) if first else ""

    t = rx.pattern
    for m in _customer_mentions(sentence, offset, section):
        if m.kind == KIND_CUSTOMER and m.entity_text and rx.search(m.entity_text):
            return m
    # Explicit directions, from the filer's point of view: the target buys from the filer ...
    if re.search(
        rf"(?:{t}\s+(?:purchases|purchased|purchase|buys|bought|licenses|licensed)\b[^.;]{{0,50}}\b(?:our|from us)"
        rf"|\b(?:sales|revenue|revenues|shipments)\s+to\s+(?:[A-Za-z.&' ]{{0,30}})?{t}"
        rf"|\bsupply\s+(?:agreement|arrangement|contract)s?\s+with\s+{t}"
        rf"|\b(?:supply|supplies|supplying|sell|sells|selling|ship|ships|shipped|provide|provides)\b[^.;]{{0,70}}\bto\s+{t}"
        rf"|{t}\s+is\s+(?:one of\s+)?our\s+(?:largest|significant|principal|major)?\s*customers?)",
        sentence,
        re.I,
    ):
        return Mention(
            KIND_CUSTOMER, display, sentence, offset, "customer_direction", 0.8, section=section
        )
    # ... or the filer buys from the target.
    if re.search(
        rf"(?:\b(?:purchase|purchases|purchased|buy|buys|bought|source|sourced|procure|procured|obtain|license|licensed)\b[^.;]{{0,70}}\bfrom\s+{t}"
        rf"|{t}\s+(?:supplies|supplied|provides|provided|manufactures|manufactured)\s+(?:us|our|all|substantially all|the)\b"
        rf"|\b(?:supplied|manufactured|fabricated|provided|hosted)\s+by\s+{t}"
        rf"|{t}\s+is\s+(?:one of\s+)?our\s+(?:sole|single|primary|principal|largest|key)?\s*(?:source|supplier|vendor)s?"
        rf"|\b(?:rely|relies|depend|depends)\s+(?:on|upon)\s+{t})",
        sentence,
        re.I,
    ):
        return Mention(
            KIND_SUPPLIER, display, sentence, offset, "supplier_direction", 0.8, section=section
        )
    for m in _CUSTOMER_LIST.finditer(sentence):
        if target_in(names_in(m.group("list"))) and _FIRST_PERSON.search(sentence[: m.start() + 1]):
            return Mention(
                KIND_CUSTOMER, display, sentence, offset, "customer_list", 0.6, section=section
            )
    for pat, pid, conf in (
        (_SUPPLIER_FROM, "supplier_from", 0.8),
        (_SUPPLIER_BY, "supplier_by", 0.8),
        (_SUPPLIER_LIST, "supplier_list", 0.75),
        (_RELY, "supplier_rely", 0.55),
    ):
        for m in pat.finditer(sentence):
            if target_in(names_in(m.group("list"))):
                return Mention(KIND_SUPPLIER, display, sentence, offset, pid, conf, section=section)
    for pat, pid in ((_COMPETITOR_LIST, "competitor_list"), (_COMPETE_WITH, "compete_with")):
        for m in pat.finditer(sentence):
            if target_in(names_in(m.group("list"))):
                return Mention(
                    KIND_COMPETITOR, display, sentence, offset, pid, 0.75, section=section
                )
    for m in _PARTNER.finditer(sentence):
        if target_in(names_in(m.group("list"))):
            return Mention(
                KIND_PARTNER, display, sentence, offset, "partner_with", 0.45, section=section
            )

    # Weaker fallbacks: the cue has to sit close to the name. A single weak mention is
    # dropped at assembly (MIN_CONFIDENCE); repeated mentions in one filing survive.
    if _near(sentence, rx, _COMPETE_CUE) and not _CUSTOMER_CUE.search(sentence):
        return Mention(
            KIND_COMPETITOR, display, sentence, offset, "compete_cue", 0.4, section=section
        )
    if _near(sentence, rx, _SUPPLY_CUE) and not _CUSTOMER_CUE.search(sentence):
        return Mention(KIND_SUPPLIER, display, sentence, offset, "supply_cue", 0.4, section=section)
    if _near(sentence, rx, _PARTNER_CUE):
        return Mention(KIND_PARTNER, display, sentence, offset, "partner_cue", 0.3, section=section)
    return None
