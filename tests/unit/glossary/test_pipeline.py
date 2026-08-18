"""Tests for :mod:`meeting_minutes_agent.glossary.pipeline` -- the wired
extract -> dedupe -> gate REVISE path for one chunk. Expectations here are
hand-traced against :mod:`fixtures`'s ``CHUNK_0_TEXT`` docstring."""

from __future__ import annotations

from meeting_minutes_agent.glossary.gate import GateConfig
from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag
from meeting_minutes_agent.glossary.pipeline import build_chunk_entries

from .fixtures import CHUNK_0_TEXT


def test_build_chunk_entries_end_to_end_hand_traced():
    entries = build_chunk_entries(CHUNK_0_TEXT, chunk_index=0)
    assert entries == (
        GlossaryEntry("Ortega", ("Ortega", "ortega"), 0, 3, ProvenanceTag.SPEECH_PASS, LeakageTier.M0, None),
        GlossaryEntry("Fitzgerald", ("Fitzgerald", "fitzgerald"), 0, 3, ProvenanceTag.SPEECH_PASS, LeakageTier.M0, None),
    )


def test_build_chunk_entries_raises_the_evidence_bar():
    entries = build_chunk_entries(CHUNK_0_TEXT, chunk_index=0, gate_config=GateConfig(min_evidence=4))
    assert entries == ()  # both terms sit at evidence_count=3, below a min_evidence=4 bar


def test_build_chunk_entries_honours_inventory_cap_tie_break():
    entries = build_chunk_entries(
        CHUNK_0_TEXT, chunk_index=0, gate_config=GateConfig(min_evidence=2, inventory_cap=1)
    )
    # both survivors tie on evidence_count(3) and first_seen_chunk(0);
    # alphabetical tie-break keeps "Fitzgerald" ('F' < 'O').
    assert len(entries) == 1
    assert entries[0].canonical_surface == "Fitzgerald"


def test_build_chunk_entries_threads_provenance_tier_and_speaker_context():
    entries = build_chunk_entries(
        CHUNK_0_TEXT,
        chunk_index=2,
        provenance=ProvenanceTag.METADATA,
        leakage_tier=LeakageTier.M1,
        introduced_by="speaker-3",
    )
    assert len(entries) == 2
    for e in entries:
        assert e.first_seen_chunk == 2
        assert e.provenance is ProvenanceTag.METADATA
        assert e.leakage_tier is LeakageTier.M1
        assert e.introduced_by == "speaker-3"


def test_build_chunk_entries_on_text_with_no_candidates_is_empty():
    assert build_chunk_entries("the quick brown fox jumps over the lazy dog.", chunk_index=0) == ()
