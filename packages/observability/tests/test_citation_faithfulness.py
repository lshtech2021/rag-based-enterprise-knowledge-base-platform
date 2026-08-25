import pytest
from kb_observability.eval.citation_faithfulness import (
    assert_faithful,
    citation_faithfulness_score,
)


def test_faithfulness_passes_with_known_citations() -> None:
    answer = "Risks include competition [cite:risk-1]."
    assert citation_faithfulness_score(answer=answer, allowed_chunk_ids={"risk-1"}) == 1.0
    assert_faithful(answer=answer, allowed_chunk_ids={"risk-1"})


def test_faithfulness_fails_without_citations() -> None:
    assert citation_faithfulness_score(answer="No sources", allowed_chunk_ids={"risk-1"}) == 0.0


def test_faithfulness_fails_on_unknown_citation() -> None:
    with pytest.raises(AssertionError):
        assert_faithful(
            answer="Bad claim [cite:missing]",
            allowed_chunk_ids={"risk-1"},
        )
