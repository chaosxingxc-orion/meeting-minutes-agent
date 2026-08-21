from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.probes.state_audit import (
    StateAuditEntry,
    StateAuditTurn,
    build_state_views,
    carry_targets,
    contains_entity,
    load_manifest,
    score_state,
)
from meeting_minutes_agent.runreceipt import config_hash


def _entry() -> StateAuditEntry:
    return StateAuditEntry(
        uniq_id="D1",
        duration=30.0,
        entity_list=("Hydro Dent", "Acme Cloud"),
        turns=(
            StateAuditTurn(0, "speaker_1", 0, 10, "Hydro Dent launched."),
            StateAuditTurn(1, "speaker_2", 10, 20, "Acme Cloud launched."),
            StateAuditTurn(2, "speaker_1", 20, 30, "Hydro Dent expanded."),
        ),
        source_tar="source.tar",
        tar_member="./D1.wav",
        audio_sha256="0" * 64,
    )


def test_entity_matching_is_case_and_punctuation_insensitive():
    assert contains_entity("We use Hydro-Dent today", "hydro dent")
    assert not contains_entity("Hydro is unrelated", "Hydro Dent")


def test_carry_targets_separate_same_speaker_from_global_history():
    entry = _entry()
    assert carry_targets(entry, 2, same_speaker=True) == ("Hydro Dent",)
    assert carry_targets(entry, 2, same_speaker=False) == ("Hydro Dent",)


def test_state_builder_uses_only_supplied_hypotheses():
    entry = _entry()
    hypotheses = {
        0: "We discussed Hydro Dent. Later Hydro Dent launched.",
        1: "We discussed Acme Cloud. Later Acme Cloud launched.",
    }
    views = build_state_views(entry, hypotheses, 2)
    assert "hydro dent" in {x.lower() for x in views["gated-speaker"]}
    assert "hydro dent" in {x.lower() for x in views["first-mention-speaker"]}
    assert "acme cloud" not in {x.lower() for x in views["gated-speaker"]}
    assert "acme cloud" in {x.lower() for x in views["gated-global"]}


def test_score_state_reports_recall_and_pollution():
    score = score_state(_entry(), 2, ("Hydro Dent", "invented"))
    assert score == {
        "terms": 2,
        "supported_terms": 1,
        "hallucinated_terms": 1,
        "speaker_supported_terms": 1,
        "off_speaker_terms": 0,
        "target_relevant_terms": 1,
        "same_target_hits": 1,
        "same_targets": 1,
        "global_target_hits": 1,
        "global_targets": 1,
    }


def test_manifest_hash_is_fail_closed(tmp_path):
    entry = _entry()
    raw_entry = {
        "uniq_id": entry.uniq_id,
        "duration": entry.duration,
        "entity_list": list(entry.entity_list),
        "turns": [turn.to_dict() for turn in entry.turns],
        "source_tar": entry.source_tar,
        "tar_member": entry.tar_member,
        "audio_sha256": entry.audio_sha256,
    }
    document = {"schema_version": "e3-state-audit-manifest-v1", "entries": [raw_entry]}
    document["content_hash"] = config_hash(document)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_manifest(path).entries[0].uniq_id == "D1"
    document["entries"][0]["duration"] = 31
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_manifest(path)
