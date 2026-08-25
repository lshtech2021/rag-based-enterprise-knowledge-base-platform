"""Reject answers that cite unknown chunks or lack required grounding markers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from kb_domain import AccessionNumber, Citation
from kb_query.application.ports import GeneratedAnswer, RetrievalHit

_CITE_RE = re.compile(r"\[cite:([^\]]+)\]")


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    text: str
    citations: tuple[Citation, ...]


class UngroundedAnswerError(ValueError):
    """Raised when the model answer is not grounded in retrieved evidence."""


class CitationValidator:
    def validate(self, draft: GeneratedAnswer, hits: list[RetrievalHit]) -> ValidatedAnswer:
        hit_by_id = {h.chunk.chunk_id: h for h in hits}
        markers = _CITE_RE.findall(draft.text)
        if not markers:
            raise UngroundedAnswerError("Answer contains no [cite:chunk_id] markers")

        unknown = [cid for cid in markers if cid not in hit_by_id]
        if unknown:
            raise UngroundedAnswerError(f"Unknown citation ids: {unknown}")

        # Every id the model claimed in structured field must also be in hits
        for cid in draft.cited_chunk_ids:
            if cid not in hit_by_id:
                raise UngroundedAnswerError(f"cited_chunk_ids contains unknown id {cid}")

        citations: list[Citation] = []
        seen: set[str] = set()
        for cid in markers:
            if cid in seen:
                continue
            seen.add(cid)
            hit = hit_by_id[cid]
            citations.append(
                Citation(
                    chunk_id=cid,
                    accession_no=AccessionNumber(str(hit.chunk.accession_no)),
                    section=hit.chunk.section,
                    source_url=hit.source_url,
                )
            )
        return ValidatedAnswer(text=draft.text, citations=tuple(citations))
