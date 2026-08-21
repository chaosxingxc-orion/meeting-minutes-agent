import json

from meeting_minutes_agent.probes.e4_confirmatory import RuntimeTarget, ScoreTarget
from meeting_minutes_agent.probes.e4_disjoint_direction import DirectionRuntimeBinding, DirectionScoreBinding
from meeting_minutes_agent.probes.e4_disjoint_direction_scoring import build_verdict, load_scores


def test_directional_gain_is_exploratory_only(tmp_path):
    runtime_target = RuntimeTarget(
        "dialogue-t001",
        "dialogue",
        1,
        "speaker_1",
        1.0,
        2.0,
        ("Acme",),
        ("Acme",),
        ("Beta",),
        "/tmp/source.tar",
        "./dialogue.wav",
        "a" * 64,
    )
    runtime = DirectionRuntimeBinding({"content_hash": "runtime"}, (runtime_target,))
    score = DirectionScoreBinding(
        {"content_hash": "score"},
        (ScoreTarget("dialogue-t001", "dialogue", "Acme launched", ("Acme",)),),
    )
    responses = tmp_path / "responses.jsonl"
    records = [
        {
            "target_id": "dialogue-t001",
            "arm": "D0-global",
            "text": "launched",
            "injected_terms": ["Acme"],
            "outcome": "ok",
            "usage": {"completion_tokens": 2},
        },
        {
            "target_id": "dialogue-t001",
            "arm": "D1-speaker",
            "text": "Acme launched",
            "injected_terms": ["Acme"],
            "outcome": "ok",
            "usage": {"completion_tokens": 3},
        },
    ]
    responses.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    scores = load_scores(runtime, score, responses)
    verdict = build_verdict(runtime, score, scores)

    assert verdict["decision"] == "EXPLORATORY-SPEAKER-DIRECTION"
    assert verdict["confirmatory"] is False
    assert verdict["contrasts"]["speaker_minus_global_carry_hit_rate"] == 1.0


def test_duplicate_response_is_rejected(tmp_path):
    runtime_target = RuntimeTarget(
        "dialogue-t001",
        "dialogue",
        1,
        "speaker_1",
        1.0,
        2.0,
        ("Acme",),
        ("Acme",),
        ("Beta",),
        "/tmp/source.tar",
        "./dialogue.wav",
        "a" * 64,
    )
    runtime = DirectionRuntimeBinding({"content_hash": "runtime"}, (runtime_target,))
    score = DirectionScoreBinding(
        {"content_hash": "score"},
        (ScoreTarget("dialogue-t001", "dialogue", "Acme", ("Acme",)),),
    )
    record = {"target_id": "dialogue-t001", "arm": "D0-global", "text": "Acme", "outcome": "ok"}
    responses = tmp_path / "responses.jsonl"
    responses.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n", encoding="utf-8")

    try:
        load_scores(runtime, score, responses)
    except ValueError as error:
        assert "duplicate response" in str(error)
    else:
        raise AssertionError("duplicate response was accepted")


def test_any_truncation_invalidates_direction_read(tmp_path):
    runtime_target = RuntimeTarget(
        "dialogue-t001", "dialogue", 1, "speaker_1", 1.0, 2.0,
        ("Acme",), ("Acme",), ("Beta",), "/tmp/source.tar", "./dialogue.wav", "a" * 64,
    )
    runtime = DirectionRuntimeBinding({"content_hash": "runtime"}, (runtime_target,))
    score = DirectionScoreBinding(
        {"content_hash": "score"},
        (ScoreTarget("dialogue-t001", "dialogue", "Acme", ("Acme",)),),
    )
    responses = tmp_path / "responses.jsonl"
    records = [
        {"target_id": "dialogue-t001", "arm": "D0-global", "text": "Acme", "outcome": "ok", "usage": {"completion_tokens": 512}},
        {"target_id": "dialogue-t001", "arm": "D1-speaker", "text": "Acme", "outcome": "ok", "usage": {"completion_tokens": 2}},
    ]
    responses.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    verdict = build_verdict(runtime, score, load_scores(runtime, score, responses))

    assert verdict["decision"] == "EXPLORATORY-INVALID-TRUNCATED"
