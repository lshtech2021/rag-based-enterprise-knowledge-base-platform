"""Heuristic HTML section extractor for 10-K-like documents."""

from __future__ import annotations

import re
from html import unescape

from kb_ingestion.application.ports import DocumentParserPort, ParsedSection

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Ordered patterns: (section display name, heading regex)
_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Item 1A Risk Factors", re.compile(r"item\s*1a[.\s:]*risk\s*factors", re.I)),
    (
        "Item 7 MD&A",
        re.compile(
            r"item\s*7[.\s:]*management.?s?\s+discussion\s+and\s+analysis",
            re.I,
        ),
    ),
    ("Item 8 Financial Statements", re.compile(r"item\s*8[.\s:]*financial\s+statements", re.I)),
]


class SimpleHtmlSectionParser:
    """Extract known 10-K sections from HTML using heading heuristics."""

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
        sections: list[ParsedSection] = []
        for i, (start, name) in enumerate(matches):
            end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(ParsedSection(name=name, text=body))
        return sections


def _html_to_text(raw_html: bytes) -> str:
    decoded = raw_html.decode("utf-8", errors="replace")
    decoded = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", decoded)
    decoded = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", decoded)
    text = _TAG_RE.sub(" ", decoded)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


# Structural typing helper for tests
def as_parser(parser: SimpleHtmlSectionParser) -> DocumentParserPort:
    return parser
