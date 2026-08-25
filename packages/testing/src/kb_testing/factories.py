from __future__ import annotations

from datetime import date

from kb_domain import CIK, AccessionNumber, Filing


def make_cik(raw: str = "320193") -> CIK:
    return CIK(raw)


def make_filing(
    *,
    accession_no: str = "0000320193-24-000123",
    cik: str = "320193",
    form_type: str = "10-K",
    filed_date: date | None = None,
) -> Filing:
    return Filing(
        accession_no=AccessionNumber(accession_no),
        cik=CIK(cik),
        form_type=form_type,
        filed_date=filed_date or date(2024, 11, 1),
    )
