"""Generate a multi-section grounded report from a template."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kb_report.application.ports import (
    ReportRepository,
    ReportSectionResult,
    SectionAnswerPort,
    StoredReport,
)
from kb_report.domain.templates import get_template

_log = logging.getLogger("kb_report.generate_report")


@dataclass(frozen=True, slots=True)
class GenerateReportCommand:
    template_id: str
    company: str
    period: str
    user_id: str


@dataclass(frozen=True, slots=True)
class GenerateReportResult:
    report: StoredReport


class GenerateReport:
    def __init__(self, answers: SectionAnswerPort, reports: ReportRepository) -> None:
        self._answers = answers
        self._reports = reports

    async def execute(self, command: GenerateReportCommand) -> GenerateReportResult:
        _log.info(
            "event=generate_report.start user_id=%s template_id=%s company=%s period=%s",
            command.user_id,
            command.template_id,
            command.company,
            command.period,
        )
        try:
            template = get_template(command.template_id)
            section_results: list[ReportSectionResult] = []
            for spec, question in template.render_questions(
                company=command.company, period=command.period
            ):
                answered = await self._answers.answer(question)
                section_results.append(
                    ReportSectionResult(
                        section_id=spec.section_id,
                        title=spec.title,
                        question=question,
                        body=answered.text,
                        citations=answered.citations,
                    )
                )
            markdown = _assemble_markdown(
                template.title, command.company, command.period, section_results
            )
            report = StoredReport(
                report_id=StoredReport.new_id(),
                user_id=command.user_id,
                template_id=template.template_id,
                title=template.title,
                company=command.company,
                period=command.period,
                markdown=markdown,
                sections=tuple(section_results),
            )
            await self._reports.save(report)
            _log.info(
                "event=generate_report.success user_id=%s report_id=%s sections=%s",
                command.user_id,
                report.report_id,
                len(report.sections),
            )
            return GenerateReportResult(report=report)
        except Exception:
            _log.exception(
                "event=generate_report.error user_id=%s template_id=%s",
                command.user_id,
                command.template_id,
            )
            raise


def _assemble_markdown(
    title: str,
    company: str,
    period: str,
    sections: list[ReportSectionResult],
) -> str:
    lines = [f"# {title}", "", f"**Company:** {company}  ", f"**Period:** {period}", ""]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.body)
        lines.append("")
        if section.citations:
            lines.append("### Sources")
            for cite in section.citations:
                lines.append(f"- `{cite.chunk_id}` — {cite.section} — {cite.source_url}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"
