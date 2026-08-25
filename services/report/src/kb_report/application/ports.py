"""Report application ports and DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import uuid4

from kb_domain import Citation


@dataclass(frozen=True, slots=True)
class SectionAnswer:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ReportSectionResult:
    section_id: str
    title: str
    question: str
    body: str
    citations: tuple[Citation, ...]


@dataclass(slots=True)
class StoredReport:
    report_id: str
    user_id: str
    template_id: str
    title: str
    company: str
    period: str
    markdown: str
    sections: tuple[ReportSectionResult, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new_id() -> str:
        return str(uuid4())


@runtime_checkable
class SectionAnswerPort(Protocol):
    async def answer(self, question: str) -> SectionAnswer: ...


@runtime_checkable
class ReportRepository(Protocol):
    async def save(self, report: StoredReport) -> None: ...

    async def get(self, report_id: str) -> StoredReport | None: ...
