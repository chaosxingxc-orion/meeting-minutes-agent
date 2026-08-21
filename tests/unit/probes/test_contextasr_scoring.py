from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.probes.contextasr import ARMS, ContextAsrEntry, ContextAsrManifest
from meeting_minutes_agent.probes.contextasr_scoring import (
    SampleScore,
    build_verdict,
    load_scores,
    normalize_english,
    score_response,
)


def _entry(uniq_id: str = "X1") -> ContextAsrEntry:
    return ContextAsrEntry(
        uniq_id=uniq_id,
        language="English",
        duration=10.0,
        domain_label="Medicine",
        reference_text="The patient received pembrolizumab today.",
        entity_list=("pembrolizumab",),
        deranged_entity_list=("trastuzumab",),
        corrupt_entity_list=("pmebrolizumab",),
        source_tar="source.tar",
        tar_member=f"./{uniq_id}.wav",
        audio_sha256="0" * 64,
    )


def test_normalization_and_perfect_entity_score():
    assert normalize_english("DON'T re-enter.") == "do not re enter"
    score = score_response(
        _entry(), "C2-entity", "The patient received pembrolizumab today.", ("pembrolizumab",), 10
    )
    assert score.wer == 0
    assert score.ne_wer == 0
    assert score.ne_fnr == 0
    assert score.injected_activated == 1


def test_wrong_entity_is_charged():
    score = score_response(
        _entry(), "C3-deranged", "The patient received trastuzumab today.", ("trastuzumab",), 10
    )
    assert score.wer > 0
    assert score.ne_wer == 1
    assert score.ne_fnr == 1
    assert score.injected_activated == 1


def test_incomplete_read_fails_closed(tmp_path):
    manifest = ContextAsrManifest(raw={"content_hash": "abc"}, entries=(_entry(),))
    path = tmp_path / "responses.jsonl"
    path.write_text(json.dumps({"outcome": "ok", "uniq_id": "X1", "arm": "C0-bare", "text": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing cells"):
        load_scores(manifest, path)


def test_registered_reachable_branch(monkeypatch):
    scores = []
    for index in range(4):
        for arm in ARMS:
            ne_errors = 0 if arm == "C2-entity" else 10
            wer_errors = 1
            scores.append(
                SampleScore(
                    uniq_id=f"X{index}", arm=arm, wer_errors=wer_errors, wer_tokens=100,
                    ne_errors=ne_errors, ne_tokens=10, ne_hits=1 if arm == "C2-entity" else 0,
                    ne_targets=1, injected_activated=1 if arm == "C2-entity" else 0,
                    injected_total=1 if arm != "C0-bare" else 0, completion_tokens=10,
                )
            )
    monkeypatch.setattr(
        "meeting_minutes_agent.probes.contextasr_scoring._bootstrap_delta",
        lambda by_arm, left, right, metric: {"low": -1.0, "high": -0.01},
    )
    verdict = build_verdict(ContextAsrManifest(raw={"content_hash": "abc"}, entries=()), scores)
    assert verdict["decision"] == "ORACLE-CONTEXT-REACHABLE"
