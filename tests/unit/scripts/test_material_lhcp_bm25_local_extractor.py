"""Offline tests for the LHCP BM25 local extractor."""

from __future__ import annotations

import read_material_lhcp_bm25_local_extractor as reader


def test_candidate_document_repeats_canonical_and_uses_frozen_occurrence() -> None:
    candidate = {
        "canonical": "QCD Result",
        "occurrences": [
            {"page": 2, "relative_path": "b.pdf", "source_span": "later span"},
            {"page": 1, "relative_path": "a.pdf", "source_span": "Physics context"},
        ],
    }
    assert reader.candidate_document(candidate, 3) == [
        "qcd", "result", "qcd", "result", "qcd", "result", "physics", "context"
    ]


def test_bm25_prefers_document_with_query_terms() -> None:
    documents = [["qcd", "physics"], ["finance", "revenue"]]
    scores = reader.bm25_scores(documents, ["qcd"], k1=1.2, b=0.75)
    assert scores[0] > scores[1]


def test_variant_verdict_applies_slice_and_meeting_gates() -> None:
    gates = {
        "minimum_primary_opportunity_slices": 157,
        "minimum_primary_opportunity_meetings": 15,
        "exploratory_minimum_opportunity_slices": 50,
        "exploratory_minimum_opportunity_meetings": 10,
    }
    assert reader.variant_verdict(157, 15, gates) == "BM25_LOCAL_EXTRACTION_POWER_READY"
    assert reader.variant_verdict(60, 10, gates) == "BM25_LOCAL_EXTRACTION_EXPLORATORY_ONLY"
    assert reader.variant_verdict(49, 25, gates) == "BM25_LOCAL_EXTRACTION_INSUFFICIENT"
