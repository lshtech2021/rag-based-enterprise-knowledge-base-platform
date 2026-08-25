from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_domain import AccessionNumber, Citation
from kb_report.application.ports import SectionAnswer
from kb_report.application.use_cases.generate_report import GenerateReport
from kb_report.infrastructure.in_memory_report_store import InMemoryReportRepository


class FakeSectionAnswer:
    async def answer(self, question: str) -> SectionAnswer:
        cite = Citation(
            chunk_id="risk-1",
            accession_no=AccessionNumber("0000320193-24-000123"),
            section="Item 1A Risk Factors",
            source_url="https://example.com/filing",
        )
        return SectionAnswer(text=f"{question} [cite:risk-1]", citations=(cite,))


def _client() -> TestClient:
    repo = InMemoryReportRepository()
    app = create_app()
    app.state.report_repository = repo
    app.state.generate_report = GenerateReport(answers=FakeSectionAnswer(), reports=repo)
    return TestClient(app)


def test_create_and_get_report() -> None:
    client = _client()
    created = client.post(
        "/v1/reports",
        json={
            "template_id": "quarterly_risk_summary",
            "company": "Apple Inc.",
            "period": "FY2024",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["report_id"]
    assert "Key Risk Factors" in body["markdown"]
    assert body["citations"]

    fetched = client.get(f"/v1/reports/{body['report_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["report_id"] == body["report_id"]


def test_get_missing_report_404() -> None:
    client = _client()
    assert client.get("/v1/reports/does-not-exist").status_code == 404
