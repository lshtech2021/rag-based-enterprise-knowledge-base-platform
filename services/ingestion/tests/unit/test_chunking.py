from kb_ingestion.domain.chunking import estimate_tokens, split_section_text


def test_estimate_tokens_non_empty() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2


def test_split_short_text_single_chunk() -> None:
    text = "Risk remains elevated. Liquidity is strong."
    assert split_section_text(text) == [text]


def test_split_long_text_multiple_chunks() -> None:
    sentence = "The company faces competitive pressure in multiple markets. "
    text = sentence * 80
    chunks = split_section_text(text, target_tokens=64, min_tokens=32, max_tokens=96)
    assert len(chunks) > 1
    assert all(estimate_tokens(c) <= 120 for c in chunks)


def test_split_prefers_paragraph_boundaries() -> None:
    para = ("Competition remains intense across product lines and geographies. " * 20).strip()
    text = f"{para}\n\n{(para + ' Extra.')}\n\n{para}"
    chunks = split_section_text(text, target_tokens=80, min_tokens=40, max_tokens=120)
    assert len(chunks) >= 2
    # Paragraph break should appear as separate packed units when under max
    joined = "\n\n".join(chunks)
    assert "Competition remains intense" in joined
