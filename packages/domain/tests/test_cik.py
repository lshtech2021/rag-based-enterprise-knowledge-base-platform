import pytest
from kb_domain import CIK, InvalidCIKError


def test_cik_pads_to_ten_digits() -> None:
    assert CIK("320193") == "0000320193"


def test_cik_accepts_already_padded() -> None:
    assert CIK("0000320193") == "0000320193"


def test_cik_rejects_empty() -> None:
    with pytest.raises(InvalidCIKError):
        CIK("")


def test_cik_rejects_non_numeric() -> None:
    with pytest.raises(InvalidCIKError):
        CIK("AAPL")


def test_cik_rejects_too_long() -> None:
    with pytest.raises(InvalidCIKError):
        CIK("12345678901")
