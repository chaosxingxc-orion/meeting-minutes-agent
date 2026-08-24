from meeting_minutes_agent.state.chunk_retrieval import (
    RetrievalLimits,
    build_index,
    render_candidates,
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
