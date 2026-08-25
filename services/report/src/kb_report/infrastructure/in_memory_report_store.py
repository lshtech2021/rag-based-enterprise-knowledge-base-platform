"""In-memory report persistence for MVP tests."""

from __future__ import annotations

from kb_report.application.ports import ReportRepository, StoredReport


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._reports: dict[str, StoredReport] = {}

    async def save(self, report: StoredReport) -> None:
        self._reports[report.report_id] = report

    async def get(self, report_id: str) -> StoredReport | None:
        return self._reports.get(report_id)


def as_report_repo(repo: InMemoryReportRepository) -> ReportRepository:
    return repo
