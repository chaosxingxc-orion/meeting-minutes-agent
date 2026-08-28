"""Offline tests for the LHCP local-candidate ceiling reader."""

from __future__ import annotations

import read_material_lhcp_local_candidate_ceiling as reader


GATES = {
    "minimum_primary_opportunity_slices": 157,
    "minimum_primary_opportunity_meetings": 15,
    "exploratory_minimum_opportunity_slices": 50,
    "exploratory_minimum_opportunity_meetings": 10,
}


def test_candidate_classification_separates_retain_opportunity_and_unsupported() -> None:
    reference = ["the", "qcd", "result"]
    assert reader.classify_candidate(["the", "qcd"], reference, ["qcd"]) == "retain"
    assert reader.classify_candidate(["the", "cutie"], reference, ["qcd"]) == "wrong_to_correct_opportunity"
    assert reader.classify_candidate(["the", "cutie"], reference, ["atlas"]) == "unsupported"


def test_ceiling_verdict_applies_primary_and_exploratory_distribution_gates() -> None:
    assert reader.ceiling_verdict(157, 15, GATES) == "LHCP_LOCAL_CANDIDATE_POOL_POWER_READY"
    assert reader.ceiling_verdict(100, 10, GATES) == "LHCP_LOCAL_CANDIDATE_POOL_EXPLORATORY_ONLY"
    assert reader.ceiling_verdict(49, 25, GATES) == "LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT"
    assert reader.ceiling_verdict(200, 9, GATES) == "LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT"
