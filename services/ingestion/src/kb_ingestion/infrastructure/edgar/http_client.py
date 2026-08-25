"""SEC EDGAR HTTP client with User-Agent and rate limiting."""

from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Any

import httpx
from kb_domain import CIK, AccessionNumber
from kb_ingestion.application.ports import EdgarFilingMeta


class RateLimiter:
    """Simple sliding-window limiter (max_calls per 1 second)."""

    def __init__(self, max_calls: int = 10, period_seconds: float = 1.0) -> None:
        self._max_calls = max_calls
        self._period = period_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < self._period]
                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return
                sleep_for = self._period - (now - self._timestamps[0]) + 0.001
                await asyncio.sleep(max(sleep_for, 0.001))


class HttpEdgarClient:
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(
        self,
        user_agent: str,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("SEC requires a descriptive User-Agent")
        self._user_agent = user_agent
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._limiter = rate_limiter or RateLimiter(max_calls=10, period_seconds=1.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_latest_filing(
        self, cik: CIK, form_types: tuple[str, ...] = ("10-K", "10-Q", "8-K")
    ) -> EdgarFilingMeta:
        await self._limiter.acquire()
        url = self.SUBMISSIONS_URL.format(cik=str(cik))
        response = await self._client.get(url, headers=self._headers())
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        recent = payload["filings"]["recent"]
        forms: list[str] = recent["form"]
        accessions: list[str] = recent["accessionNumber"]
        filing_dates: list[str] = recent["filingDate"]
        primary_docs: list[str] = recent["primaryDocument"]

        for idx, form in enumerate(forms):
            if form not in form_types:
                continue
            accession = AccessionNumber(accessions[idx])
            accession_path = str(accession).replace("-", "")
            doc = primary_docs[idx]
            source_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(str(cik))}/{accession_path}/{doc}"
            )
            return EdgarFilingMeta(
                accession_no=accession,
                cik=cik,
                form_type=form,
                filed_date=date.fromisoformat(filing_dates[idx]),
                primary_document=doc,
                company_name=str(payload.get("name", "Unknown")),
                source_url=source_url,
            )
        raise LookupError(f"No filings matching {form_types} for CIK {cik}")

    async def download_filing_document(self, meta: EdgarFilingMeta) -> bytes:
        await self._limiter.acquire()
        response = await self._client.get(meta.source_url, headers=self._headers())
        response.raise_for_status()
        return response.content

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
