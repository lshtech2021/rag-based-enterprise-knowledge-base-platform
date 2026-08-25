"""Heuristic HTML section extractor for 10-K / 10-Q-like documents."""

from __future__ import annotations

import re
from html import unescape

from kb_ingestion.application.ports import DocumentParserPort, ParsedSection

_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_RE = re.compile(
    r"(?is)</?(?:br|p|div|h[1-6]|tr|li|table|section|article|header|footer)[^>]*>"
)
_HORIZ_WS_RE = re.compile(r"[^\S\n]+")
_MULTI_NL_RE = re.compile(r"\n\s*\n+")

# Ordered patterns: (section display name, heading regex)
_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Item 1 Business", re.compile(r"item\s*1(?!\s*[a-z])[.\s:]*business\b", re.I)),
    ("Item 1A Risk Factors", re.compile(r"item\s*1a[.\s:]*risk\s*factors", re.I)),
    (
        "Item 1B Unresolved Staff Comments",
        re.compile(r"item\s*1b[.\s:]*unresolved\s+staff\s+comments", re.I),
    ),
    ("Item 2 Properties", re.compile(r"item\s*2[.\s:]*properties\b", re.I)),
    ("Item 3 Legal Proceedings", re.compile(r"item\s*3[.\s:]*legal\s+proceedings", re.I)),
    (
        "Item 7 MD&A",
        re.compile(
            r"item\s*7(?!\s*a)[.\s:]*management.?s?\s+discussion\s+and\s+analysis",
            re.I,
        ),
    ),
    (
        "Item 7A Market Risk",
        re.compile(
            r"item\s*7a[.\s:]*quantitative\s+and\s+qualitative\s+disclosures?"
            r"\s+about\s+market\s+risk",
            re.I,
        ),
    ),
    ("Item 8 Financial Statements", re.compile(r"item\s*8[.\s:]*financial\s+statements", re.I)),
    ("Part I Financial Information", re.compile(r"part\s*i[.\s:]*financial\s+information", re.I)),
    ("Part II Other Information", re.compile(r"part\s*ii[.\s:]*other\s+information", re.I)),
]


class SimpleHtmlSectionParser:
    """Extract known filing sections from HTML using heading heuristics."""

    def parse(self, raw_html: bytes) -> list[ParsedSection]:
        text = _html_to_text(raw_html)
        if not text.strip():
            return []

        matches: list[tuple[int, str]] = []
        for name, pattern in _SECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                matches.append((m.start(), name))
        if not matches:
            return [ParsedSection(name="Full Document", text=text)]

        matches.sort(key=lambda x: x[0])
        # Deduplicate overlapping starts (keep first name at each position)
        deduped: list[tuple[int, str]] = []
        seen_starts: set[int] = set()
        for start, name in matches:
            if start in seen_starts:
                continue
            seen_starts.add(start)
            deduped.append((start, name))

        sections: list[ParsedSection] = []
        for i, (start, name) in enumerate(deduped):
            end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(ParsedSection(name=name, text=body))
        return sections


def _html_to_text(raw_html: bytes) -> str:
    decoded = raw_html.decode("utf-8", errors="replace")
    decoded = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", decoded)
    decoded = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", decoded)
    decoded = _BLOCK_RE.sub("\n", decoded)
    text = _TAG_RE.sub(" ", decoded)
    text = unescape(text)
    text = _HORIZ_WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


# Structural typing helper for tests
def as_parser(parser: SimpleHtmlSectionParser) -> DocumentParserPort:
    return parser
