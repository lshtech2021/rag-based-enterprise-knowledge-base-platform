"""LangGraph wiring for the RAG answer pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from kb_query.application.ports import RetrievalHit
from kb_query.application.use_cases.answer_query import AnswerQuery, AnswerQueryCommand
from langgraph.graph import END, START, StateGraph


class QueryGraphState(TypedDict, total=False):
    question: str
    rewritten: str
    hits: list[RetrievalHit]
    answer: str
    citations: list[dict[str, str]]
    error: str


def build_answer_graph(use_case: AnswerQuery) -> Any:
    """Compile a graph entrypoint that delegates to AnswerQuery."""

    async def run_pipeline(state: QueryGraphState) -> QueryGraphState:
        result = await use_case.execute(AnswerQueryCommand(question=state["question"]))
        return {
            "question": state["question"],
            "rewritten": result.rewritten_question,
            "hits": list(result.hits),
            "answer": result.answer,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "accession_no": str(c.accession_no),
                    "section": c.section,
                    "source_url": c.source_url,
                }
                for c in result.citations
            ],
        }

    graph: StateGraph[QueryGraphState] = StateGraph(QueryGraphState)
    graph.add_node("answer", run_pipeline)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def build_staged_graph(
    *,
    rewrite_fn: Any,
    retrieve_fn: Any,
    generate_fn: Any,
    validate_fn: Any,
) -> Any:
    """Four-stage graph used to prove LangGraph stage wiring in tests."""

    async def rewrite(state: QueryGraphState) -> QueryGraphState:
        rewritten = await rewrite_fn(state["question"])
        return {**state, "rewritten": rewritten}

    async def retrieve(state: QueryGraphState) -> QueryGraphState:
        hits = await retrieve_fn(state["rewritten"])
        return {**state, "hits": hits}

    async def generate(state: QueryGraphState) -> QueryGraphState:
        answer = await generate_fn(state["question"], state["hits"])
        return {**state, "answer": answer}

    async def validate(state: QueryGraphState) -> QueryGraphState:
        validated = validate_fn(state["answer"], state["hits"])
        return {**state, "answer": validated}

    g: StateGraph[QueryGraphState] = StateGraph(QueryGraphState)
    g.add_node("rewrite", rewrite)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("validate", validate)
    g.add_edge(START, "rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "validate")
    g.add_edge("validate", END)
    return g.compile()
