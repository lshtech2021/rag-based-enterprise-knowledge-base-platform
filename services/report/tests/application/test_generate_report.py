import pytest
from kb_domain import AccessionNumber, Citation
from kb_report.application.ports import SectionAnswer
from kb_report.application.use_cases.generate_report import (
    GenerateReport,
    GenerateReportCommand,
)
from kb_report.infrastructure.in_memory_report_store import InMemoryReportRepository
from kb_report.presentation.graph import build_report_graph, build_staged_report_graph


class FakeSectionAnswer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def answer(self, question: str) -> SectionAnswer:
        self.calls.append(question)
        cite = Citation(
            chunk_id=f"chunk-{len(self.calls)}",
            accession_no=AccessionNumber("0000320193-24-000123"),
            section="Item 1A Risk Factors",
            source_url="https://example.com/filing",
        )
        return SectionAnswer(
            text=f"Grounded answer for: {question} [cite:{cite.chunk_id}]",
            citations=(cite,),
        )


@pytest.mark.asyncio
async def test_generate_report_builds_markdown_and_provenance() -> None:
    answers = FakeSectionAnswer()
    repo = InMemoryReportRepository()
    uc = GenerateReport(answers=answers, reports=repo)
    result = await uc.execute(
        GenerateReportCommand(
            template_id="quarterly_risk_summary",
            company="Apple Inc.",
            period="FY2024",
            user_id="dev-user",
        )
    )
    report = result.report
    assert len(report.sections) >= 2
    assert "## Key Risk Factors" in report.markdown
    assert "## MD&A Outlook" in report.markdown
    assert "[cite:" in report.markdown
    assert all(section.citations for section in report.sections)
    stored = await repo.get(report.report_id)
    assert stored is not None
    assert len(answers.calls) >= 2


@pytest.mark.asyncio
async def test_langgraph_report_entrypoint() -> None:
    uc = GenerateReport(answers=FakeSectionAnswer(), reports=InMemoryReportRepository())
    graph = build_report_graph(uc)
    out = await graph.ainvoke(
        {
            "template_id": "quarterly_risk_summary",
            "company": "Apple Inc.",
            "period": "FY2024",
            "user_id": "dev-user",
        }
    )
    assert out["report_id"]
    assert "Quarterly Risk Summary" in out["markdown"]


@pytest.mark.asyncio
async def test_langgraph_staged_report() -> None:
    async def plan(state: dict[str, str]) -> dict[str, str]:
        return {"company": state["company"].upper()}

    async def fill(state: dict[str, str]) -> dict[str, str]:
        return {"period": state["period"] + "-filled"}

    async def assemble(state: dict[str, str]) -> dict[str, str]:
        return {"markdown": f"{state['company']}/{state['period']}"}

    graph = build_staged_report_graph(plan_fn=plan, fill_fn=fill, assemble_fn=assemble)
    out = await graph.ainvoke({"company": "apple", "period": "FY24", "user_id": "u"})
    assert out["markdown"] == "APPLE/FY24-filled"
