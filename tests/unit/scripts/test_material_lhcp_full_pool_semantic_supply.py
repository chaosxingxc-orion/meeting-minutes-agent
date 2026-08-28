"""Offline tests for LHCP full-pool semantic supply construction."""

from __future__ import annotations

import build_material_lhcp_full_pool_semantic_supply as builder


def test_build_supply_is_reference_blind_and_causal() -> None:
    config = {
        "counts": {"meetings": 1, "keys": 1, "queries": 1},
        "construction": {"query_instruction": "Find local material.\n", "maximum_prior_keywords": 8},
    }
    trace = [{
        "meeting_id": "m1",
        "turn_id": "m1-slice0000",
        "pass0": {"transcript_text": "Q CD measurement"},
        "runtime_context": {
            "speaker_labels": ["speaker_1"],
            "prior_topic_keywords": ["physics"],
            "potentially_truncated": False,
        },
    }]
    source = [{
        "audio_path": "m1.wav",
        "canonical": "QCD",
        "category": "acronym_or_alphanumeric",
        "occurrences": [{"page": 1, "relative_path": "m1.pdf", "source_span": "QCD physics"}],
    }]
    candidates, queries = builder.build_supply(config, trace, source)
    assert len(candidates) == 1
    assert candidates[0]["value"]["canonical"] == "QCD"
    assert "physics" in queries[0]["query_text"]
    assert "reference" not in queries[0]
