"""Accession number value object — SEC filing accession."""

from __future__ import annotations

import re

_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class InvalidAccessionNumberError(ValueError):
    """Raised when an accession number is malformed."""


def normalize_accession_number(raw: str) -> str:
    text = raw.strip()
    if not _ACCESSION_RE.match(text):
        raise InvalidAccessionNumberError(
            f"Accession number must match NNNNNNNNNN-NN-NNNNNN, got {raw!r}"
        )
    return text


class AccessionNumber(str):
    """SEC accession number (e.g. 0000320193-24-000123)."""

    __slots__ = ()

    def __new__(cls, raw: str) -> AccessionNumber:
        return str.__new__(cls, normalize_accession_number(raw))
