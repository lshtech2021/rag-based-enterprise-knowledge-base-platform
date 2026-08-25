import pytest
from kb_domain import AccessionNumber, InvalidAccessionNumberError


def test_accession_accepts_valid() -> None:
    assert AccessionNumber("0000320193-24-000123") == "0000320193-24-000123"


def test_accession_rejects_malformed() -> None:
    with pytest.raises(InvalidAccessionNumberError):
        AccessionNumber("not-an-accession")
