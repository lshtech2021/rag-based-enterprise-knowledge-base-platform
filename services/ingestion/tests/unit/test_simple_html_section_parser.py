from kb_ingestion.infrastructure.parsing.simple_html_section_parser import SimpleHtmlSectionParser

FIXTURE_HTML = b"""
<html><body>
<h1>Item 1. Business</h1>
<p>We design and sell consumer electronics.</p>
<h1>Item 1A. Risk Factors</h1>
<p>We face substantial risks related to market competition and regulation.</p>
<p>Additional risk narrative for parsers.</p>
<h1>Item 7. Management's Discussion and Analysis</h1>
<p>Revenue increased year over year due to product demand.</p>
<h1>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h1>
<p>Interest rate risk is monitored.</p>
<h1>Item 8. Financial Statements</h1>
<p>See consolidated statements.</p>
</body></html>
"""


def test_parser_extracts_named_sections() -> None:
    sections = SimpleHtmlSectionParser().parse(FIXTURE_HTML)
    names = [s.name for s in sections]
    assert "Item 1 Business" in names
    assert "Item 1A Risk Factors" in names
    assert "Item 7 MD&A" in names
    assert "Item 7A Market Risk" in names
    risk = next(s for s in sections if s.name == "Item 1A Risk Factors")
    assert "substantial risks" in risk.text.lower()


def test_parser_preserves_paragraph_breaks() -> None:
    html = b"""
    <html><body>
    <h1>Item 1A. Risk Factors</h1>
    <p>First paragraph about competition.</p>
    <p>Second paragraph about regulation.</p>
    </body></html>
    """
    sections = SimpleHtmlSectionParser().parse(html)
    assert len(sections) == 1
    assert "\n\n" in sections[0].text


def test_parser_fallback_full_document() -> None:
    html = b"<html><body><p>No item headings here.</p></body></html>"
    sections = SimpleHtmlSectionParser().parse(html)
    assert sections[0].name == "Full Document"
