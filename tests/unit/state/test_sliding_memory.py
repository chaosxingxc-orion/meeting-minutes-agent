from meeting_minutes_agent.state.sliding_memory import (
    MemoryLimits,
    build_meeting_memory,
    content_tokens,
    context_hash,
    render_context,
)


def _rows():
    return [
        {"turn_index": 0, "speaker_id": "speaker_1", "text": "EBITDA margin improved in Q1."},
        {"turn_index": 1, "speaker_id": "speaker_2", "text": "Revenue growth and cloud sales."},
        {"turn_index": 2, "speaker_id": "speaker_1", "text": "Q1 EBITDA margin was strong."},
        {"turn_index": 3, "speaker_id": "speaker_2", "text": "Cloud revenue growth continued."},
    ]


def test_content_tokens_keep_professional_forms_and_drop_function_words() -> None:
    assert content_tokens("The EBITDA in Q1 and SK") == ("ebitda", "q1", "sk")


def test_memory_is_deterministic_and_routes_deranged_speaker() -> None:
    limits = MemoryLimits(summary_characters=100, recent_characters=40, global_keywords=5, speaker_keywords=3)
    first = build_meeting_memory(_rows(), limits)
    second = build_meeting_memory(list(reversed(_rows())), limits)

    assert first == second
    assert first.deranged_speaker == {"speaker_1": "speaker_2", "speaker_2": "speaker_1"}
    assert first.speaker_keywords["speaker_1"][:2] == ("ebitda", "margin")


def test_rendered_arms_are_nested_and_hashed() -> None:
    limits = MemoryLimits(summary_characters=100, recent_characters=40, global_keywords=5, speaker_keywords=3)
    memory = build_meeting_memory(_rows(), limits)
    history = [{"text": "Earlier current-pass words."}]

    recent = render_context("L1-recent", "speaker_1", memory, history, limits)
    global_state = render_context("L2-global", "speaker_1", memory, history, limits)
    speaker_state = render_context("L3-speaker", "speaker_1", memory, history, limits)
    deranged = render_context("L4-deranged", "speaker_1", memory, history, limits)

    assert recent in global_state
    assert global_state in speaker_state
    assert "ebitda" in speaker_state
    assert "cloud" in deranged
    assert context_hash(speaker_state) == context_hash(speaker_state)
