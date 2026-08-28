"""Offline tests for the LHCP development opportunity and power audit."""

from __future__ import annotations

from difflib import SequenceMatcher

import read_material_lhcp_development_opportunity_power as reader


def test_normalization_phrase_matching_and_primary_power_target() -> None:
    sequence = reader.tokens("The CP-violation result uses B2 sigma.")
    assert sequence == ["the", "cp", "violation", "result", "uses", "b2", "sigma"]
    assert reader.contains_phrase(sequence, ["cp", "violation"])
    assert not reader.contains_phrase(sequence, ["cp", "result"])
    assert reader.required_pairs(0.10, 0.20) == 157


def test_reference_span_uses_alignment_and_fixed_padding() -> None:
    hypothesis = "alpha beta gamma delta".split()
    reference = "intro alpha beta corrected gamma delta outro".split()
    opcodes = SequenceMatcher(None, hypothesis, reference, autojunk=True).get_opcodes()
    start, end = reader.reference_span(
        opcodes,
        hypothesis_start=0,
        hypothesis_end=2,
        hypothesis_length=len(hypothesis),
        reference_length=len(reference),
        padding=1,
    )
    assert reference[start:end] == ["intro", "alpha", "beta", "corrected", "gamma"]


def test_reference_span_fallback_uses_whole_hypothesis_position() -> None:
    start, end = reader.reference_span(
        [],
        hypothesis_start=50,
        hypothesis_end=60,
        hypothesis_length=100,
        reference_length=200,
        padding=12,
    )
    assert (start, end) == (88, 112)
