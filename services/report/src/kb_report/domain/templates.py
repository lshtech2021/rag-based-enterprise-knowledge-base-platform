"""Report templates and section plans."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportSectionSpec:
    section_id: str
    title: str
    question_template: str


@dataclass(frozen=True, slots=True)
class ReportTemplate:
    template_id: str
    title: str
    sections: tuple[ReportSectionSpec, ...]

    def render_questions(self, *, company: str, period: str) -> list[tuple[ReportSectionSpec, str]]:
        return [
            (
                section,
                section.question_template.format(company=company, period=period),
            )
            for section in self.sections
        ]


QUARTERLY_RISK_SUMMARY = ReportTemplate(
    template_id="quarterly_risk_summary",
    title="Quarterly Risk Summary",
    sections=(
        ReportSectionSpec(
            section_id="risk_factors",
            title="Key Risk Factors",
            question_template=(
                "What are the key risk factors disclosed for {company} relevant to period {period}?"
            ),
        ),
        ReportSectionSpec(
            section_id="mda_outlook",
            title="MD&A Outlook",
            question_template=(
                "What does management discussion say about outlook and performance "
                "for {company} in {period}?"
            ),
        ),
    ),
)

TEMPLATES: dict[str, ReportTemplate] = {
    QUARTERLY_RISK_SUMMARY.template_id: QUARTERLY_RISK_SUMMARY,
}


def get_template(template_id: str) -> ReportTemplate:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown report template: {template_id}") from exc
