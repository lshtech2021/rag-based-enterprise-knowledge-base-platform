"""LangGraph entrypoint for report generation."""

from __future__ import annotations

from typing import Any, TypedDict

from kb_report.application.use_cases.generate_report import (
    GenerateReport,
    GenerateReportCommand,
)
from langgraph.graph import END, START, StateGraph


class ReportGraphState(TypedDict, total=False):
    template_id: str
    company: str
    period: str
    user_id: str
    report_id: str
    markdown: str


def build_report_graph(use_case: GenerateReport) -> Any:
    async def run(state: ReportGraphState) -> ReportGraphState:
        result = await use_case.execute(
            GenerateReportCommand(
                template_id=state["template_id"],
                company=state["company"],
                period=state["period"],
                user_id=state["user_id"],
            )
        )
        return {
            **state,
            "report_id": result.report.report_id,
            "markdown": result.report.markdown,
        }

    graph: StateGraph[ReportGraphState] = StateGraph(ReportGraphState)
    graph.add_node("generate", run)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def build_staged_report_graph(
    *,
    plan_fn: Any,
    fill_fn: Any,
    assemble_fn: Any,
) -> Any:
    """Three-stage graph for wiring tests: plan → fill → assemble."""

    async def plan(state: ReportGraphState) -> ReportGraphState:
        planned = await plan_fn(state)
        return {**state, **planned}

    async def fill(state: ReportGraphState) -> ReportGraphState:
        filled = await fill_fn(state)
        return {**state, **filled}

    async def assemble(state: ReportGraphState) -> ReportGraphState:
        assembled = await assemble_fn(state)
        return {**state, **assembled}

    g: StateGraph[ReportGraphState] = StateGraph(ReportGraphState)
    g.add_node("plan", plan)
    g.add_node("fill", fill)
    g.add_node("assemble", assemble)
    g.add_edge(START, "plan")
    g.add_edge("plan", "fill")
    g.add_edge("fill", "assemble")
    g.add_edge("assemble", END)
    return g.compile()
