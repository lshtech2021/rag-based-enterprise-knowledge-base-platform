from kb_testing import make_cik, make_filing


def test_make_filing_builds_valid_stub() -> None:
    filing = make_filing()
    assert filing.cik == make_cik()
    assert filing.form_type == "10-K"
    assert str(filing.accession_no).startswith("0000320193")
