from kb_report.domain.templates import QUARTERLY_RISK_SUMMARY, get_template


def test_quarterly_template_has_at_least_two_sections() -> None:
    template = get_template("quarterly_risk_summary")
    assert template is QUARTERLY_RISK_SUMMARY
    assert len(template.sections) >= 2
    questions = template.render_questions(company="Apple", period="FY2024")
    assert all("Apple" in q for _, q in questions)
    assert questions[0][0].section_id != questions[1][0].section_id
