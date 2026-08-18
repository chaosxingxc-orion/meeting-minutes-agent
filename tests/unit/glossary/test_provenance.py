"""Tests for :mod:`meeting_minutes_agent.glossary.provenance`: the
speech-only/metadata-only/combined factorization, the machine-enforced
Tier-M1 refusal on runtime supply views, and the (v2 delta) per-speaker
view filter."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag
from meeting_minutes_agent.glossary.provenance import (
    LeakageTierViolation,
    build_diagnostic_view,
    build_runtime_supply_view,
    combined,
    filter_by_provenance,
    metadata_only,
    speaker_view,
    speech_only,
)


def _entry(surface: str, provenance: ProvenanceTag, tier: LeakageTier, introduced_by: str | None = None) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=(surface,),
        first_seen_chunk=0,
        evidence_count=2,
        provenance=provenance,
        leakage_tier=tier,
        introduced_by=introduced_by,
    )


SPEECH_M0 = _entry("Ortega", ProvenanceTag.SPEECH_PASS, LeakageTier.M0, "spk1")
META_M0 = _entry("Denver", ProvenanceTag.METADATA, LeakageTier.M0, None)
SPEECH_M1 = _entry("Harrison", ProvenanceTag.SPEECH_PASS, LeakageTier.M1, "spk2")


def test_speech_only_and_metadata_only_partition_by_provenance():
    entries = (SPEECH_M0, META_M0, SPEECH_M1)
    assert speech_only(entries) == (SPEECH_M0, SPEECH_M1)
    assert metadata_only(entries) == (META_M0,)


def test_combined_applies_no_provenance_filter():
    entries = (SPEECH_M0, META_M0)
    assert combined(entries) == entries


def test_filter_by_provenance_is_the_shared_primitive():
    entries = (SPEECH_M0, META_M0)
    assert filter_by_provenance(entries, ProvenanceTag.SPEECH_PASS) == speech_only(entries)


def test_runtime_supply_view_passes_through_when_all_entries_are_m0():
    entries = (SPEECH_M0, META_M0)
    assert build_runtime_supply_view(entries) == entries


def test_runtime_supply_view_refuses_on_any_m1_entry():
    entries = (SPEECH_M0, SPEECH_M1)
    with pytest.raises(LeakageTierViolation) as exc_info:
        build_runtime_supply_view(entries)
    assert "Harrison" in str(exc_info.value)


def test_runtime_supply_view_refuses_even_when_m1_is_the_only_entry():
    with pytest.raises(LeakageTierViolation):
        build_runtime_supply_view((SPEECH_M1,))


def test_diagnostic_view_allows_m1_entries_through():
    entries = (SPEECH_M0, SPEECH_M1)
    assert build_diagnostic_view(entries) == entries


def test_speaker_view_filters_to_one_speaker():
    entries = (SPEECH_M0, META_M0, SPEECH_M1)
    assert speaker_view(entries, "spk1") == (SPEECH_M0,)
    assert speaker_view(entries, "spk2") == (SPEECH_M1,)


def test_speaker_view_none_matches_unattributed_entries_only():
    entries = (SPEECH_M0, META_M0, SPEECH_M1)
    assert speaker_view(entries, None) == (META_M0,)


def test_speaker_view_unknown_speaker_gives_empty_view():
    entries = (SPEECH_M0, META_M0)
    assert speaker_view(entries, "nobody-introduced-this") == ()
