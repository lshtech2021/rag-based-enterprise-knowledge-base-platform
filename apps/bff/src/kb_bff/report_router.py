"""BFF report routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from kb_identity.domain.principal import Principal, Role
from kb_report.application.ports import ReportRepository, StoredReport
from kb_report.application.use_cases.generate_report import (
    GenerateReport,
    GenerateReportCommand,
)
from pydantic import BaseModel, Field

from kb_bff.auth_deps import require_roles_dep


class CreateReportRequest(BaseModel):
    template_id: str = Field(default="quarterly_risk_summary")
    company: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=64)


def get_generate_report(request: Request) -> GenerateReport:
    use_case = getattr(request.app.state, "generate_report", None)
    if use_case is None:
        raise RuntimeError("GenerateReport is not configured on app.state.generate_report")
    return use_case  # type: ignore[no-any-return]


def get_report_repository(request: Request) -> ReportRepository:
    repo = getattr(request.app.state, "report_repository", None)
    if repo is None:
        raise RuntimeError("ReportRepository is not configured on app.state.report_repository")
    return repo  # type: ignore[no-any-return]


router = APIRouter(prefix="/v1", tags=["reports"])


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create_report(
    body: CreateReportRequest,
    use_case: Annotated[GenerateReport, Depends(get_generate_report)],
    principal: Annotated[Principal, Depends(require_roles_dep(Role.ANALYST))],
) -> dict[str, object]:
    try:
        result = await use_case.execute(
            GenerateReportCommand(
                template_id=body.template_id,
                company=body.company,
                period=body.period,
                user_id=principal.user_id,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize(result.report)


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    repo: Annotated[ReportRepository, Depends(get_report_repository)],
    _principal: Annotated[Principal, Depends(require_roles_dep(Role.ANALYST))],
) -> dict[str, object]:
    report = await repo.get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return _serialize(report)


def _serialize(report: StoredReport) -> dict[str, object]:
    return {
        "report_id": report.report_id,
        "template_id": report.template_id,
        "title": report.title,
        "company": report.company,
        "period": report.period,
        "user_id": report.user_id,
        "markdown": report.markdown,
        "citations": [
            {
                "section_id": section.section_id,
                "chunk_id": cite.chunk_id,
                "accession_no": str(cite.accession_no),
                "section": cite.section,
                "source_url": cite.source_url,
            }
            for section in report.sections
            for cite in section.citations
        ],
    }
