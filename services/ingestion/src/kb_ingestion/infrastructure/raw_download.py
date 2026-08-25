"""Resolve stored raw filing bytes from a filing row."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from kb_application_ports import ObjectStorePort
from kb_domain import AccessionNumber
from kb_ingestion.application.ports import FilingRepository


class RawFilingNotFoundError(LookupError):
    """Raised when a filing or its raw object is missing."""


async def load_raw_filing(
    *,
    filings: FilingRepository,
    object_store: ObjectStorePort,
    accession_no: str,
) -> tuple[bytes, str]:
    """Return ``(body, filename)`` for a previously ingested accession."""
    filing = await filings.get_filing(AccessionNumber(accession_no))
    if filing is None or not filing.s3_raw_path:
        raise RawFilingNotFoundError(accession_no)

    uri = filing.s3_raw_path
    if uri.startswith("memory://"):
        key = uri.removeprefix("memory://")
        body = await object_store.get_bytes(key)
        return body, key.rsplit("/", 1)[-1]

    if uri.startswith("file://"):
        path = Path(unquote(urlparse(uri).path))
        if not path.is_file():
            raise RawFilingNotFoundError(accession_no)
        return path.read_bytes(), path.name

    # Treat as object-store key
    body = await object_store.get_bytes(uri)
    return body, uri.rsplit("/", 1)[-1]
