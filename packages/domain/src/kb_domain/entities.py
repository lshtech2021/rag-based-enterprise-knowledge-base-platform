from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from kb_domain.accession import AccessionNumber
from kb_domain.value_objects import CIK


@dataclass(frozen=True, slots=True)
class Company:
    cik: CIK
    name: str
    ticker: str | None = None
    sic: str | None = None


@dataclass(frozen=True, slots=True)
class Filing:
    accession_no: AccessionNumber
    cik: CIK
    form_type: str
    filed_date: date
    period: str | None = None
    s3_raw_path: str | None = None


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    accession_no: AccessionNumber
    section: str
    text: str
    token_count: int


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    accession_no: AccessionNumber
    section: str
    source_url: str
