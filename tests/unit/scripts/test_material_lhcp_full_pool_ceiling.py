"""Offline tests for the LHCP full material-pool ceiling reader."""

from __future__ import annotations

import read_material_lhcp_full_pool_ceiling as reader


def test_candidate_id_matches_frozen_selected_candidate_identity() -> None:
    assert reader.candidate_id("m1", "QCD") == "lhcp-m1-20a42d0dfbea"
    assert reader.candidate_id("m1", "qcd") == reader.candidate_id("m1", "QCD")
