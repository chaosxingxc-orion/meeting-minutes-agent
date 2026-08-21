from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.probes.state_audit import StateAuditEntry, StateAuditManifest, StateAuditTurn
from meeting_minutes_agent.probes.state_audit_scoring import build_verdict, load_hypotheses


def _manifest() -> StateAuditManifest:
    entry = StateAuditEntry(
        "D1",
        30.0,
        ("Hydro Dent",),
        (
            StateAuditTurn(0, "speaker_1", 0, 10, "We discussed Hydro Dent."),
            StateAuditTurn(1, "speaker_2", 10, 20, "Nothing relevant."),
            StateAuditTurn(2, "speaker_1", 20, 30, "Hydro Dent launched."),
        ),
        "source.tar",
        "./D1.wav",
        "0" * 64,
    )
    return StateAuditManifest({"content_hash": "hash"}, (entry,))


def test_read_requires_every_pass0_turn(tmp_path):
    path = tmp_path / "responses.jsonl"
    path.write_text(json.dumps({"uniq_id": "D1", "turn_index": 0, "outcome": "ok", "text": "x"}) + "\n")
    with pytest.raises(ValueError, match="incomplete"):
        load_hypotheses(_manifest(), path)


def test_verdict_is_machine_determined_and_gold_is_scoring_only():
    hypotheses = {"D1": {0: "We discussed Hydro Dent.", 1: "Nothing relevant.", 2: "Hydro Dent launched."}}
    verdict = build_verdict(_manifest(), hypotheses)
    assert verdict["manifest_hash"] == "hash"
    assert verdict["target_turns"] == 1
    assert verdict["decision"] in {"STATE-EXTRACTION-BOTTLENECK", "STATE-NOT-RECOVERABLE"}
    naive = verdict["aggregate"]["naive-speaker"]
    assert naive["same_targets"] == 1
