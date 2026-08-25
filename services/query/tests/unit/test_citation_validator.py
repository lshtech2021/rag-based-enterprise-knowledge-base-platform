import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.application.ports import GeneratedAnswer, RetrievalHit
from kb_query.domain.citation_validator import CitationValidator, UngroundedAnswerError


def _hit(chunk_id: str = "c1") -> RetrievalHit:
    chunk = Chunk(
        chunk_id=chunk_id,
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A Risk Factors",
        text="We face substantial competition risks.",
        token_count=10,
    )
    return RetrievalHit(chunk=chunk, score=1.0, source_url="https://example.com/f")


def test_validator_accepts_grounded_answer() -> None:
    hit = _hit()
    draft = GeneratedAnswer(
        text=f"Competition is material [cite:{hit.chunk.chunk_id}]",
        cited_chunk_ids=(hit.chunk.chunk_id,),
    )
    result = CitationValidator().validate(draft, [hit])
    assert result.citations[0].chunk_id == "c1"


def test_validator_rejects_missing_markers() -> None:
    with pytest.raises(UngroundedAnswerError):
        CitationValidator().validate(
            GeneratedAnswer(text="No citations here", cited_chunk_ids=()),
            [_hit()],
        )


def test_validator_rejects_unknown_chunk_id() -> None:
    with pytest.raises(UngroundedAnswerError):
        CitationValidator().validate(
            GeneratedAnswer(
                text="Bad claim [cite:missing]",
                cited_chunk_ids=("missing",),
            ),
            [_hit()],
        )
