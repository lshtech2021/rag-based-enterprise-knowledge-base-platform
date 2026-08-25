"""BFF query routes — SSE streaming for RAG answers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from kb_identity.domain.principal import Principal, Role
from kb_query.application.use_cases.answer_query import AnswerQuery, AnswerQueryCommand
from pydantic import BaseModel, Field

from kb_bff.auth_deps import require_roles_dep


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


def get_answer_query(request: Request) -> AnswerQuery:
    use_case = getattr(request.app.state, "answer_query", None)
    if use_case is None:
        raise RuntimeError("AnswerQuery is not configured on app.state.answer_query")
    return use_case  # type: ignore[no-any-return]


router = APIRouter(prefix="/v1", tags=["query"])


@router.post("/query")
async def query_sse(
    body: QueryRequest,
    use_case: Annotated[AnswerQuery, Depends(get_answer_query)],
    _principal: Annotated[Principal, Depends(require_roles_dep(Role.ANALYST))],
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[bytes]:
        result = await use_case.execute(
            AnswerQueryCommand(question=body.question, top_k=body.top_k)
        )
        for token in _tokenize(result.answer):
            payload = {"type": "token", "data": token}
            yield f"data: {json.dumps(payload)}\n\n".encode()
        sources = [
            {
                "chunk_id": c.chunk_id,
                "accession_no": str(c.accession_no),
                "section": c.section,
                "source_url": c.source_url,
            }
            for c in result.citations
        ]
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n".encode()
        done = {"type": "done", "data": {"answer": result.answer}}
        yield f"data: {json.dumps(done)}\n\n".encode()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _tokenize(text: str) -> list[str]:
    parts = text.split(" ")
    tokens: list[str] = []
    for i, part in enumerate(parts):
        tokens.append(part if i == len(parts) - 1 else part + " ")
    return [t for t in tokens if t]
