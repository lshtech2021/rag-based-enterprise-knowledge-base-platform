"""OpenAI Chat Completions adapter for rewrite + grounded generate."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import httpx
from openai import AsyncOpenAI
from kb_query.application.ports import ChatMessage, GeneratedAnswer, RetrievalHit

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
_CITE_RE = re.compile(r"\[cite:([^\]]+)\]")
_HISTORY_MSG_CHARS = 1500


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


def _clip(text: str, n: int = _HISTORY_MSG_CHARS) -> str:
    cleaned = text.strip()
    if len(cleaned) <= n:
        return cleaned
    return cleaned[: max(0, n - 3)] + "..."


def _format_history_transcript(history: Sequence[ChatMessage]) -> str:
    lines: list[str] = []
    for msg in history:
        label = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{label}: {_clip(msg.content)}")
    return "\n".join(lines)


class OpenAIChatLLM:
    """LLMPort backed by OpenAI chat completions via the official SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_CHAT_MODEL,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._base_url = resolve_openai_base_url(base_url)
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            key = (api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
            if not key:
                raise ValueError("OPENAI_API_KEY is required for OpenAIChatLLM")
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=self._base_url,
                http_client=http_client,
                timeout=120.0,
            )
            # Only close when we created the SDK client without an injected httpx client.
            self._owns_client = http_client is None

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def rewrite(
        self, question: str, *, history: Sequence[ChatMessage] = ()
    ) -> str:
        system = (
            "You rewrite analyst questions about SEC filings for retrieval. "
            "Use prior conversation turns to resolve pronouns and follow-ups into a "
            "standalone search query. Return only the rewritten question, no preamble."
        )
        if history:
            user = (
                "Prior conversation:\n"
                f"{_format_history_transcript(history)}\n\n"
                f"Current question: {question.strip()}"
            )
        else:
            user = question.strip()
        text = await self._chat(system=system, user=user)
        return text.strip() or question.strip()

    async def generate(
        self,
        question: str,
        hits: list[RetrievalHit],
        *,
        history: Sequence[ChatMessage] = (),
    ) -> GeneratedAnswer:
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
            "the closest relevant chunk. Use prior conversation only for context; "
            "ground every fact in the filing chunks."
        )
        final_user = (
            f"Question: {question.strip()}\n\n"
            f"Allowed chunk ids: {', '.join(allowed_ids)}\n\n"
            "Context:\n\n" + "\n\n---\n\n".join(context_blocks)
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for msg in history:
            messages.append({"role": msg.role, "content": _clip(msg.content)})
        messages.append({"role": "user", "content": final_user})
        text = await self._chat_messages(messages)
        cited = tuple(dict.fromkeys(_CITE_RE.findall(text)))
        return GeneratedAnswer(text=text.strip(), cited_chunk_ids=cited)

    async def _chat(self, *, system: str, user: str) -> str:
        return await self._chat_messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )

    async def _chat_messages(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            messages=messages,  # type: ignore[arg-type]
        )
        content = response.choices[0].message.content
        if content is None:
            return ""
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)
