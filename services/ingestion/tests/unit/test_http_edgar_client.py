from datetime import date

import httpx
import pytest
from kb_domain import CIK
from kb_ingestion.infrastructure.edgar.http_client import HttpEdgarClient, RateLimiter


def _submissions_payload() -> dict[str, object]:
    return {
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q"],
                "accessionNumber": ["0000320193-24-000123", "0000320193-24-000050"],
                "filingDate": ["2024-11-01", "2024-08-01"],
                "primaryDocument": ["aapl-20240928.htm", "aapl-10q.htm"],
            }
        },
    }


@pytest.mark.asyncio
async def test_http_edgar_sends_user_agent_and_resolves_filing() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "submissions" in str(request.url):
            return httpx.Response(200, json=_submissions_payload())
        return httpx.Response(200, content=b"<html>doc</html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        edgar = HttpEdgarClient("KB Platform test@example.com", client=client)
        meta = await edgar.fetch_latest_filing(CIK("320193"), form_types=("10-K",))
        body = await edgar.download_filing_document(meta)

    assert meta.form_type == "10-K"
    assert meta.filed_date == date(2024, 11, 1)
    assert body == b"<html>doc</html>"
    assert all(c.headers.get("User-Agent") == "KB Platform test@example.com" for c in calls)


@pytest.mark.asyncio
async def test_rate_limiter_caps_burst() -> None:
    limiter = RateLimiter(max_calls=3, period_seconds=1.0)
    for _ in range(3):
        await limiter.acquire()
    # Fourth acquire should eventually succeed without raising
    await limiter.acquire()


@pytest.mark.asyncio
async def test_empty_user_agent_rejected() -> None:
    with pytest.raises(ValueError):
        HttpEdgarClient("   ")
