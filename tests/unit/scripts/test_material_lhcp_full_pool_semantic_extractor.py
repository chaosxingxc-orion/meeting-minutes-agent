"""Offline tests for the LHCP full-pool semantic extractor."""

from __future__ import annotations

import numpy as np

import read_material_lhcp_full_pool_semantic_extractor as reader
import run_material_lhcp_full_pool_semantic_extractor as runner


def test_rank_candidates_uses_cosine_score_and_identity_tie_break() -> None:
    candidates = [{"candidate_id": "b"}, {"candidate_id": "a"}, {"candidate_id": "c"}]
    vectors = np.asarray([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    query = np.asarray([1.0, 0.0], dtype=np.float32)
    ranked = runner.rank_candidates(candidates, vectors, query, 2)
    assert [row["candidate_id"] for row in ranked] == ["a", "b"]


def test_reader_applies_primary_width_gate() -> None:
    runtime = {
        "experiment_id": "test",
        "embedding": {"maximum_calls": 331},
        "evaluation": {"widths": [1, 8], "primary_width": 8},
        "gates": {
            "minimum_primary_opportunity_slices": 1,
            "minimum_primary_opportunity_meetings": 1,
            "exploratory_minimum_opportunity_slices": 1,
            "exploratory_minimum_opportunity_meetings": 1,
        },
    }
    rankings = []
    oracle = []
    for position in range(396):
        turn_id = f"t{position}"
        rankings.append({"position": position, "meeting_id": "m1", "turn_id": turn_id, "ranking": [{"candidate_id": "x"}]})
        oracle.append({"position": position, "turn_id": turn_id, "any_opportunity": position == 0, "opportunities": [{"candidate_id": "x"}] if position == 0 else []})
    result = reader.evaluate(runtime, rankings, oracle)
    assert result["verdict"] == "FULL_POOL_SEMANTIC_EXTRACTION_POWER_READY"
