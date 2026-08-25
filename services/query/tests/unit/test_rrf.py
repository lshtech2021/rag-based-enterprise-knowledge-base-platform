from kb_query.domain.rrf import reciprocal_rank_fusion


def test_rrf_prefers_docs_high_in_both_lists() -> None:
    fused = reciprocal_rank_fusion(
        [
            ["a", "b", "c"],
            ["b", "a", "d"],
        ],
        k=60,
    )
    ids = [doc_id for doc_id, _ in fused]
    assert ids[0] in {"a", "b"}
    assert "d" in ids
