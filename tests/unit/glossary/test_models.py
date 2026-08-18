"""Tests for :mod:`meeting_minutes_agent.glossary.models`."""

from __future__ import annotations

from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag


def test_introduced_by_defaults_to_none():
    e = GlossaryEntry(
        canonical_surface="Ortega",
        variants=("Ortega",),
        first_seen_chunk=0,
        evidence_count=1,
        provenance=ProvenanceTag.SPEECH_PASS,
        leakage_tier=LeakageTier.M0,
    )
    assert e.introduced_by is None


def test_to_dict_carries_introduced_by():
    e = GlossaryEntry(
        canonical_surface="Ortega",
        variants=("Ortega", "ortega"),
        first_seen_chunk=1,
        evidence_count=3,
        provenance=ProvenanceTag.SPEECH_PASS,
        leakage_tier=LeakageTier.M0,
        introduced_by="speaker-2",
    )
    d = e.to_dict()
    assert d == {
        "canonical_surface": "Ortega",
        "variants": ["Ortega", "ortega"],
        "first_seen_chunk": 1,
        "evidence_count": 3,
        "provenance": "speech-pass",
        "leakage_tier": "M0",
        "introduced_by": "speaker-2",
    }


def test_entries_are_frozen_and_hashable():
    e1 = GlossaryEntry("A", ("A",), 0, 1, ProvenanceTag.SPEECH_PASS, LeakageTier.M0)
    e2 = GlossaryEntry("A", ("A",), 0, 1, ProvenanceTag.SPEECH_PASS, LeakageTier.M0)
    assert e1 == e2
    assert hash(e1) == hash(e2)
    assert len({e1, e2}) == 1
