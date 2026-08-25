"""Adapt AnswerQuery into SectionAnswerPort."""

from __future__ import annotations

from kb_query.application.use_cases.answer_query import AnswerQuery, AnswerQueryCommand
from kb_report.application.ports import SectionAnswer, SectionAnswerPort


class AnswerQuerySectionAdapter:
    def __init__(self, answer_query: AnswerQuery) -> None:
        self._answer_query = answer_query

    async def answer(self, question: str) -> SectionAnswer:
        result = await self._answer_query.execute(AnswerQueryCommand(question=question))
        return SectionAnswer(text=result.answer, citations=result.citations)


def as_section_answer(adapter: AnswerQuerySectionAdapter) -> SectionAnswerPort:
    return adapter
