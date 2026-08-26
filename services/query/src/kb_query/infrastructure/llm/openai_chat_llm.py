"""OpenAI Chat Completions adapter for rewrite + grounded generate."""

from __future__ import annotations

import os
import re

import httpx
from kb_query.application.ports import GeneratedAnswer, RetrievalHit

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
_CITE_RE = re.compile(r"\[cite:([^\]]+)\]")


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


class OpenAIChatLLM:
    """LLMPort backed by OpenAI chat completions (httpx)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_CHAT_MODEL,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        key = (api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIChatLLM")
        self._api_key = key
        self._model = model
        self._base_url = resolve_openai_base_url(base_url)
        self._client = client
        self._owns_client = client is None

    @property
    def model(self) -> str:
        return self._model

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def rewrite(self, question: str) -> str:
        text = await self._chat(
            system=(
                "You rewrite analyst questions about SEC filings for retrieval. "
                "Return only the rewritten question, no preamble."
            ),
            user=question.strip(),
        )
        return text.strip() or question.strip()

    async def generate(self, question: str, hits: list[RetrievalHit]) -> GeneratedAnswer:
        if not hits:
            return GeneratedAnswer(
                text="I do not have enough grounded evidence to answer.",
                cited_chunk_ids=(),
            )

        context_blocks: list[str] = []
        allowed_ids: list[str] = []
        for hit in hits:
            allowed_ids.append(hit.chunk.chunk_id)
            context_blocks.append(
                f"chunk_id={hit.chunk.chunk_id}\n"
                f"section={hit.chunk.section}\n"
                f"accession={hit.chunk.accession_no}\n"
                f"url={hit.source_url}\n"
                f"text={hit.chunk.text}"
            )
        system = (
            "You answer questions using ONLY the provided filing chunks. "
            "Every factual claim must include a citation marker exactly like "
            "[cite:CHUNK_ID] using an id from the context. "
            "Do not invent chunk ids. If evidence is insufficient, say so and cite "
            "the closest relevant chunk."
        )
        user = (
            f"Question: {question.strip()}\n\n"
            f"Allowed chunk ids: {', '.join(allowed_ids)}\n\n"
            "Context:\n\n" + "\n\n---\n\n".join(context_blocks)
        )
        text = await self._chat(system=system, user=user)
        cited = tuple(dict.fromkeys(_CITE_RE.findall(text)))
        return GeneratedAnswer(text=text.strip(), cited_chunk_ids=cited)

    async def _chat(self, *, system: str, user: str) -> str:
        client = await self._ensure_client()
        response = await client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            # Some APIs return content parts
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
