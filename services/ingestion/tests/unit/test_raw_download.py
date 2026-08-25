from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber, Filing
from kb_ingestion.infrastructure.persistence.in_memory import (
    InMemoryFilingRepository,
    InMemoryObjectStore,
)
from kb_ingestion.infrastructure.raw_download import (
    RawFilingNotFoundError,
    load_raw_filing,
)


@pytest.mark.asyncio
async def test_load_raw_filing_from_memory_store() -> None:
    store = InMemoryObjectStore()
    filings = InMemoryFilingRepository()
    key = "filings/320193/0000320193-24-000123/aapl.htm"
    await store.put_bytes(key, b"<html>hi</html>", "text/html")
    await filings.save_filing(
        Filing(
            accession_no=AccessionNumber("0000320193-24-000123"),
            cik=CIK("320193"),
            form_type="10-K",
            filed_date=date(2024, 11, 1),
            s3_raw_path=f"memory://{key}",
        ),
        source_url="https://example.com",
    )
    body, filename = await load_raw_filing(
        filings=filings,
        object_store=store,
        accession_no="0000320193-24-000123",
    )
    assert body == b"<html>hi</html>"
    assert filename == "aapl.htm"


@pytest.mark.asyncio
async def test_load_raw_filing_missing() -> None:
    with pytest.raises(RawFilingNotFoundError):
        await load_raw_filing(
            filings=InMemoryFilingRepository(),
            object_store=InMemoryObjectStore(),
            accession_no="0000000000-00-000000",
        )
