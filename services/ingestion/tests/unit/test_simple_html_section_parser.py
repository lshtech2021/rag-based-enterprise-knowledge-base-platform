from kb_ingestion.infrastructure.parsing.simple_html_section_parser import SimpleHtmlSectionParser

FIXTURE_HTML = b"""
<html><body>
<h1>Item 1A. Risk Factors</h1>
<p>We face substantial risks related to market competition and regulation.</p>
<p>Additional risk narrative for parsers.</p>
<h1>Item 7. Management's Discussion and Analysis</h1>
<p>Revenue increased year over year due to product demand.</p>
<h1>Item 8. Financial Statements</h1>
<p>See consolidated statements.</p>
</body></html>
"""


def test_parser_extracts_named_sections() -> None:
    sections = SimpleHtmlSectionParser().parse(FIXTURE_HTML)
    names = [s.name for s in sections]
    assert "Item 1A Risk Factors" in names
    assert "Item 7 MD&A" in names
    risk = next(s for s in sections if s.name == "Item 1A Risk Factors")
    assert "substantial risks" in risk.text.lower()
