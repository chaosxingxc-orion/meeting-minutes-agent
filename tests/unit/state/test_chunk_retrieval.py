from meeting_minutes_agent.state.chunk_retrieval import (
    RetrievalLimits,
    build_index,
    render_candidates,
    retrieve_deranged,
    retrieve_for_arm,
)


def _rows():
    return [
        {"turn_index": 0, "speaker_id": "speaker_1", "text": "EBITDA margin and cloud revenue."},
        {"turn_index": 1, "speaker_id": "speaker_1", "text": "EBITDA margin improved."},
        {"turn_index": 2, "speaker_id": "speaker_2", "text": "Subscription sales and users."},
        {"turn_index": 3, "speaker_id": "speaker_2", "text": "Subscription sales increased."},
    ]


def test_sparse_retrieval_routes_and_bounds_candidates() -> None:
    limits = RetrievalLimits(maximum_candidates=2, minimum_pool_count=2, minimum_similarity=0.75)
    index = build_index(_rows(), limits)

    speaker = retrieve_for_arm("R2-speaker", "speaker_1", "EBITDA margn rose", index, limits)
    deranged = retrieve_for_arm("R3-deranged", "speaker_1", "EBITDA margn rose", index, limits)

    assert speaker == ("ebitda", "margin")
    assert len(deranged) == len(speaker) == 2
    assert set(deranged).isdisjoint(speaker)


def test_renderer_contains_only_candidates_not_query() -> None:
    rendered = render_candidates(("ebitda", "margin"), 256)

    assert "ebitda, margin" in rendered
    assert len(rendered) <= 256


def test_deranged_control_excludes_shared_correct_candidates() -> None:
    rows = _rows() + [
        {"turn_index": 4, "speaker_id": "speaker_2", "text": "EBITDA subscription sales."},
        {"turn_index": 5, "speaker_id": "speaker_2", "text": "EBITDA subscription sales."},
    ]
    limits = RetrievalLimits(maximum_candidates=2, minimum_pool_count=2)
    index = build_index(rows, limits)
    correct = retrieve_for_arm("R2-speaker", "speaker_1", "EBITDA margin", index, limits)
    deranged = retrieve_for_arm("R3-deranged", "speaker_1", "EBITDA margin", index, limits)

    assert "ebitda" in correct
    assert "ebitda" not in deranged
    assert len(correct) == len(deranged)


def test_deranged_control_rotates_to_one_speaker_with_enough_candidates() -> None:
    rows = _rows() + [
        {"turn_index": 4, "speaker_id": "speaker_1", "text": "Cloud revenue grew."},
        {"turn_index": 5, "speaker_id": "speaker_1", "text": "Cloud revenue grew."},
        {"turn_index": 6, "speaker_id": "speaker_3", "text": "Operating income and cash flow."},
        {"turn_index": 7, "speaker_id": "speaker_3", "text": "Operating income and cash flow."},
    ]
    limits = RetrievalLimits(maximum_candidates=4, minimum_pool_count=2)
    index = build_index(rows, limits)
    result = retrieve_deranged("speaker_1", "EBITDA margin cloud revenue", index, limits)

    assert result.source_speaker_id == "speaker_3"
    assert len(result.candidates) == 4
    assert set(result.candidates).isdisjoint({"ebitda", "margin", "cloud", "revenue"})
