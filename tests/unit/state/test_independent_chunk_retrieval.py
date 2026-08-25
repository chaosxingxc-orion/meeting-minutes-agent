from meeting_minutes_agent.state.independent_chunk_retrieval import (
    IndependentRetrievalLimits,
    build_independent_index,
    retrieve_independent,
)


def test_retrieval_excludes_query_and_current_turn_from_evidence() -> None:
    rows = [
        {"turn_index": 0, "speaker_id": "speaker_1", "text": "EBIT DA margin"},
        {"turn_index": 1, "speaker_id": "speaker_1", "text": "EBITDA margin"},
        {"turn_index": 2, "speaker_id": "speaker_1", "text": "EBITDA improved"},
        {"turn_index": 3, "speaker_id": "speaker_2", "text": "EBIT DA margin"},
    ]
    index = build_independent_index(rows)
    candidates = retrieve_independent("speaker_1", 0, "EBIT DA margin", index, IndependentRetrievalLimits())

    assert [candidate.term for candidate in candidates] == ["ebitda"]
    assert candidates[0].matched_query_term == "ebit"
    assert candidates[0].supporting_turns == (1, 2)
    assert 0 not in candidates[0].supporting_turns


def test_retrieval_requires_two_other_chunks_from_same_speaker() -> None:
    rows = [
        {"turn_index": 0, "speaker_id": "speaker_1", "text": "margn"},
        {"turn_index": 1, "speaker_id": "speaker_1", "text": "margin"},
        {"turn_index": 2, "speaker_id": "speaker_2", "text": "margin"},
    ]
    index = build_independent_index(rows)

    assert retrieve_independent("speaker_1", 0, "margn", index, IndependentRetrievalLimits()) == ()


def test_index_counts_chunks_not_repeated_tokens() -> None:
    rows = [
        {"turn_index": 0, "speaker_id": "speaker_1", "text": "margn"},
        {"turn_index": 1, "speaker_id": "speaker_1", "text": "margin margin margin"},
    ]
    index = build_independent_index(rows)

    assert retrieve_independent("speaker_1", 0, "margn", index, IndependentRetrievalLimits()) == ()
