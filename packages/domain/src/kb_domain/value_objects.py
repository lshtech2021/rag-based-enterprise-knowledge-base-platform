"""CIK value object — SEC Central Index Key."""

from __future__ import annotations


class InvalidCIKError(ValueError):
    """Raised when a CIK cannot be normalized to a 10-digit SEC identifier."""


def normalize_cik(raw: str) -> str:
    """Normalize a CIK to a zero-padded 10-digit string.

    Accepts digits with optional leading zeros. Rejects empty, non-digit,
    or values that exceed 10 digits after stripping leading zeros beyond capacity.
    """
    text = raw.strip()
    if not text:
        raise InvalidCIKError("CIK must not be empty")
    if not text.isdigit():
        raise InvalidCIKError(f"CIK must be numeric, got {raw!r}")
    # Strip leading zeros for range check, then pad to 10
    stripped = text.lstrip("0") or "0"
    if len(stripped) > 10:
        raise InvalidCIKError(f"CIK too long: {raw!r}")
    return stripped.zfill(10)


class CIK(str):
    """Zero-padded 10-digit SEC Central Index Key."""

    __slots__ = ()

    def __new__(cls, raw: str) -> CIK:
        return str.__new__(cls, normalize_cik(raw))
