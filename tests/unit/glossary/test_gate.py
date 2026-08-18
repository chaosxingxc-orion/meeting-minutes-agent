"""Tests for :mod:`meeting_minutes_agent.glossary.gate`."""

from __future__ import annotations

from meeting_minutes_agent.glossary.gate import (
    GateConfig,
    apply_evidence_threshold,
    apply_inventory_cap,
    apply_repetition_cap,
    gate_entries,
)
from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag


def _entry(surface: str, evidence: int, first_seen: int = 0) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=(surface,),
        first_seen_chunk=first_seen,
        evidence_count=evidence,
        provenance=ProvenanceTag.SPEECH_PASS,
        leakage_tier=LeakageTier.M0,
    )


def test_evidence_threshold_drops_entries_below_the_minimum():
    entries = [_entry("a", 1), _entry("b", 2), _entry("c", 3)]
    kept = apply_evidence_threshold(entries, min_evidence=2)
    assert [e.canonical_surface for e in kept] == ["b", "c"]


def test_repetition_cap_clips_evidence_count_without_dropping_entries():
    entries = [_entry("a", 1), _entry("b", 5), _entry("c", 10)]
    capped = apply_repetition_cap(entries, cap=3)
    assert [e.evidence_count for e in capped] == [1, 3, 3]
    assert len(capped) == 3


def test_repetition_cap_none_is_a_no_op():
    entries = [_entry("a", 1), _entry("b", 5)]
    assert apply_repetition_cap(entries, cap=None) == tuple(entries)


def test_inventory_cap_selects_top_n_by_evidence_then_first_seen_then_surface():
    entries = [
        _entry("Beta", 3, first_seen=0),
        _entry("Alpha", 3, first_seen=0),   # ties Beta on evidence+first_seen -> Alpha wins alphabetically
        _entry("Later", 5, first_seen=1),   # highest evidence but later first_seen than a tied 5
        _entry("Earlier", 5, first_seen=0),  # same evidence as Later, earlier first_seen wins
    ]
    capped = apply_inventory_cap(entries, cap=2)
    assert [e.canonical_surface for e in capped] == ["Earlier", "Later"]


def test_inventory_cap_none_or_over_capacity_is_a_no_op_and_preserves_order():
    entries = [_entry("a", 1), _entry("b", 2)]
    assert apply_inventory_cap(entries, cap=None) == tuple(entries)
    assert apply_inventory_cap(entries, cap=10) == tuple(entries)


def test_gate_entries_composes_threshold_then_repetition_then_inventory():
    entries = [
        _entry("a", 1),   # dropped by threshold
        _entry("b", 20),  # survives threshold, clipped by repetition cap
        _entry("c", 3),
        _entry("d", 4),
    ]
    config = GateConfig(min_evidence=2, per_term_repetition_cap=5, inventory_cap=2)
    gated = gate_entries(entries, config)

    # after threshold: b(20->5), c(3), d(4); after repetition cap: b(5), c(3), d(4);
    # after inventory cap (top 2 by evidence): b(5), d(4)
    assert [(e.canonical_surface, e.evidence_count) for e in gated] == [("b", 5), ("d", 4)]


def test_gate_entries_default_config_only_applies_threshold():
    entries = [_entry("a", 1), _entry("b", 2)]
    gated = gate_entries(entries, GateConfig())
    assert [e.canonical_surface for e in gated] == ["b"]
