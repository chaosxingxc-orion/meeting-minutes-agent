"""Tests for :mod:`meeting_minutes_agent.glossary.accumulate`: the
cross-chunk carry rule. The merge key is (normalised surface, provenance,
leakage tier) -- deliberately not surface alone, so entries with the same
name but different provenance/tier never collapse into one record."""

from __future__ import annotations

from meeting_minutes_agent.glossary.accumulate import merge_entries
from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag


def _entry(
    surface: str,
    evidence: int,
    first_seen: int,
    *,
    variants: tuple[str, ...] | None = None,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=variants if variants is not None else (surface,),
        first_seen_chunk=first_seen,
        evidence_count=evidence,
        provenance=provenance,
        leakage_tier=tier,
        introduced_by=introduced_by,
    )


def test_merging_into_empty_existing_just_takes_the_new_entries():
    new = (_entry("Ortega", 2, 0),)
    assert merge_entries((), new) == new


def test_matching_key_merges_variants_evidence_and_keeps_the_earlier_speaker():
    existing = (_entry("Ortega", 2, 0, variants=("Ortega",), introduced_by="spk1"),)
    incoming = (_entry("ortega", 5, 1, variants=("ortega",), introduced_by="spk2"),)

    merged = merge_entries(existing, incoming)
    assert len(merged) == 1
    e = merged[0]
    assert e.canonical_surface == "ortega"  # higher evidence_count side (5 > 2) wins the display surface
    assert e.variants == ("Ortega", "ortega")
    assert e.evidence_count == 7
    assert e.first_seen_chunk == 0  # earlier of the two
    assert e.introduced_by == "spk1"  # the earlier entry's introducer, not overwritten by the later mention


def test_tied_evidence_keeps_the_existing_sides_canonical_surface():
    existing = (_entry("Ortega", 3, 0),)
    incoming = (_entry("ortega", 3, 1),)
    merged = merge_entries(existing, incoming)
    assert merged[0].canonical_surface == "Ortega"


def test_different_provenance_never_merges_even_with_the_same_surface():
    existing = (_entry("Ortega", 2, 0, provenance=ProvenanceTag.SPEECH_PASS),)
    incoming = (_entry("Ortega", 3, 1, provenance=ProvenanceTag.METADATA),)
    merged = merge_entries(existing, incoming)
    assert len(merged) == 2
    provenances = {e.provenance for e in merged}
    assert provenances == {ProvenanceTag.SPEECH_PASS, ProvenanceTag.METADATA}


def test_different_leakage_tier_never_merges_even_with_the_same_surface():
    existing = (_entry("Ortega", 2, 0, tier=LeakageTier.M0),)
    incoming = (_entry("Ortega", 3, 1, tier=LeakageTier.M1),)
    merged = merge_entries(existing, incoming)
    assert len(merged) == 2


def test_order_is_existing_first_then_genuinely_new_keys_in_new_order():
    existing = (_entry("Alpha", 1, 0), _entry("Bravo", 1, 0))
    new = (_entry("Bravo", 1, 1), _entry("Charlie", 1, 1))
    merged = merge_entries(existing, new)
    assert [e.canonical_surface for e in merged] == ["Alpha", "Bravo", "Charlie"]


def test_merge_entries_does_not_mutate_its_inputs():
    existing = (_entry("Alpha", 1, 0),)
    new = (_entry("Alpha", 1, 1),)
    merge_entries(existing, new)
    assert existing[0].evidence_count == 1
    assert new[0].evidence_count == 1
