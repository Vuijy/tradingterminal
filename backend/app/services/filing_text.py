"""Turn SEC filing HTML into plain text, sentences and sections.

Pure functions (html_to_text, split_sentences, find_sections) plus a small disk-backed
store that downloads primary documents once and keeps the extracted text under
`data/filings/<cik>/<accession>.txt`. Inline-XBRL 10-Ks are 1-10 MB of HTML and parse
in well under a second with the standard-library parser, so no HTML library is needed.
"""

from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser
from pathlib import Path

import httpx

from app.services.errors import UpstreamError

_VOID = {"br", "hr", "img", "input", "meta", "link", "col", "area", "base", "wbr"}
_SKIP = {"script", "style", "head", "title"}
_BLOCK = {
    "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "section", "article", "ul", "ol", "hr",
}  # fmt: skip


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._hidden: list[list] = []  # stack of [tag, nesting depth] for display:none blocks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip += 1
        if self._hidden and tag == self._hidden[-1][0] and tag not in _VOID:
            self._hidden[-1][1] += 1
        style = (dict(attrs).get("style") or "").replace(" ", "").lower()
        if (tag == "ix:header" or "display:none" in style) and not (
            self._hidden and tag == self._hidden[-1][0]
        ):
            self._hidden.append([tag, 1])
        if tag in _BLOCK:
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        if self._hidden and tag == self._hidden[-1][0]:
            self._hidden[-1][1] -= 1
            if self._hidden[-1][1] <= 0:
                self._hidden.pop()
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip or self._hidden:
            return
        self.parts.append(data)


_TOC_MARK = re.compile(r"(?:\d{1,3} )?Table of Contents ?", re.I)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"')
    text = text.replace("”", '"').replace("�", "'").replace("•", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = _TOC_MARK.sub("", text)
    return text.strip()


def decode_html(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


_ABBREVIATIONS = {
    "inc", "corp", "co", "ltd", "llc", "plc", "lp", "l.p", "s.a", "n.v", "a.g", "u.s", "u.k",
    "mr", "ms", "mrs", "dr", "no", "nos", "vs", "e.g", "i.e", "approx", "jr", "sr", "st",
    "mfg", "bros", "pty", "gov", "dept", "est", "fig", "vol", "ex", "et al", "ca", "etc",
}  # fmt: skip
_BOUNDARY = re.compile(r"[.!?](?=\s+[A-Z(\"'])")
_TABLE_LINE = re.compile(r"(?:\s*\|\s*[^|\n]*){4,}")


def split_sentences(text: str) -> list[tuple[int, str]]:
    """Return (offset, sentence) pairs; abbreviations and decimals do not end sentences."""
    flat = text.replace("\n", " ")
    out: list[tuple[int, str]] = []
    start = 0
    for m in _BOUNDARY.finditer(flat):
        end = m.end()
        before = flat[max(0, end - 12) : end - 1]
        word = re.search(r"(\S+)$", before)
        token = (word.group(1) if word else "").strip("(\"'").rstrip(".").lower()
        if token in _ABBREVIATIONS or re.fullmatch(r"[a-z]", token):
            continue
        sentence = flat[start:end].strip()
        if sentence:
            out.append((start, sentence))
        start = end
    tail = flat[start:].strip()
    if tail:
        out.append((start, tail))
    return [(o, s) for o, s in out if not _TABLE_LINE.fullmatch(s)]


# Headings sit at the start of a line (optionally inside a table cell "| Item 1A. | Risk ...").
_H = r"^\s*\|?\s*"
_SEP = r"\.?\s*\|?\s*[-–—:]?\s*"
_ITEMS: list[tuple[str, re.Pattern[str]]] = [
    (label, re.compile(_H + pattern, re.I | re.M))
    for label, pattern in [
        ("Item 1", rf"item\s*1{_SEP}business\b"),
        ("Item 1A", rf"item\s*1a{_SEP}risk\s*factors\b"),
        ("Item 1B", rf"item\s*1b{_SEP}unresolved"),
        ("Item 1C", rf"item\s*1c{_SEP}cybersecurity"),
        ("Item 2", rf"item\s*2{_SEP}properties\b"),
        ("Item 3", rf"item\s*3{_SEP}legal\s*proceedings\b"),
        ("Item 4", rf"item\s*4{_SEP}mine\s*safety"),
        ("Item 5", rf"item\s*5{_SEP}market\s*for"),
        ("Item 7", rf"item\s*7{_SEP}management"),
        ("Item 7A", rf"item\s*7a{_SEP}quantitative"),
        ("Item 8", rf"item\s*8{_SEP}financial\s*statements"),
        ("Item 9", rf"item\s*9{_SEP}changes\s+in"),
        ("Item 9A", rf"item\s*9a{_SEP}controls"),
        ("Item 10", rf"item\s*10{_SEP}directors"),
        ("Item 15", rf"item\s*15{_SEP}exhibits?"),
    ]
]
_ORDER = [label for label, _ in _ITEMS]
_TOC_GAP = 1500  # headings closer together than this are a table of contents


def find_sections(text: str) -> dict[str, tuple[int, int]]:
    """Start/end offsets of the 10-K items, in document order.

    Table-of-contents entries are headings packed closely together, so an occurrence
    only counts when the next heading of any item is at least _TOC_GAP characters away.
    Items are then assigned greedily in canonical order, each after the previous one.
    """
    occurrences: list[tuple[int, str]] = []
    for label, pattern in _ITEMS:
        occurrences.extend((m.start(), label) for m in pattern.finditer(text))
    occurrences.sort()
    candidates: dict[str, list[int]] = {}
    for i, (pos, label) in enumerate(occurrences):
        nxt = occurrences[i + 1][0] if i + 1 < len(occurrences) else len(text)
        if nxt - pos >= _TOC_GAP:
            candidates.setdefault(label, []).append(pos)
    starts: list[tuple[int, str]] = []
    cursor = -1
    for label in _ORDER:
        for pos in candidates.get(label, []):
            if pos > cursor:
                starts.append((pos, label))
                cursor = pos
                break
    sections: dict[str, tuple[int, int]] = {}
    for i, (pos, label) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        sections[label] = (pos, end)
    return sections


def section_at(sections: dict[str, tuple[int, int]], offset: int) -> str | None:
    for label, (start, end) in sections.items():
        if start <= offset < end:
            return label
    return None


class FilingTextStore:
    """Download primary documents once and keep the extracted text on disk."""

    name = "sec-edgar"

    def __init__(self, user_agent: str, root: Path, max_concurrency: int = 4) -> None:
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self._root = root
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def path_for(self, cik: int, accession: str) -> Path:
        return self._root / str(cik) / f"{accession.replace('-', '')}.txt"

    async def get_text(self, cik: int, accession: str, url: str) -> str:
        path = self.path_for(cik, accession)
        if path.exists():
            return await asyncio.to_thread(path.read_text, "utf-8")
        async with self._semaphore:
            try:
                async with httpx.AsyncClient(
                    headers=self._headers, timeout=90, follow_redirects=True
                ) as client:
                    response = await client.get(url)
            except httpx.HTTPError as exc:
                raise UpstreamError(self.name, f"download failed for {url}: {exc}") from exc
        if response.status_code >= 400:
            raise UpstreamError(self.name, f"HTTP {response.status_code} for {url}")
        text = await asyncio.to_thread(lambda: html_to_text(decode_html(response.content)))
        await asyncio.to_thread(self._write, path, text)
        return text

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
