"""Tests for :mod:`meeting_minutes_agent.state.episode`: the EpisodeState
aggregate -- glossary accumulation reuse, speaker-map append-only/supersede
discipline, the decision/action ledger, and snapshot/round-trip hashing."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.glossary.models import LeakageTier, ProvenanceTag
from meeting_minutes_agent.state.episode import EpisodeState, EpisodeStateSnapshot
from meeting_minutes_agent.state.models import LedgerEntryKind, SpeakerEvidenceSource

from .fixtures import glossary_entry


# ---------------------------------------------------------------------------
# glossary accumulation (reuses glossary.accumulate.merge_entries)
# ---------------------------------------------------------------------------


def test_with_glossary_chunk_returns_a_new_state_original_unchanged():
    state0 = EpisodeState()
    state1 = state0.with_glossary_chunk([glossary_entry("Ortega")])

    assert state0.glossary == ()
    assert len(state1.glossary) == 1
    assert state1 is not state0


def test_with_glossary_chunk_merges_across_chunk_boundaries_like_accumulate_glossary():
    from meeting_minutes_agent.glossary.accumulate import merge_entries

    chunk0 = [glossary_entry("Ortega", chunk=0, evidence=2)]
    chunk1 = [glossary_entry("Ortega", chunk=1, evidence=3), glossary_entry("Harrison", chunk=1, evidence=1)]

    state = EpisodeState().with_glossary_chunk(chunk0).with_glossary_chunk(chunk1)
    expected = merge_entries(merge_entries((), chunk0), chunk1)

    assert state.glossary == expected


# ---------------------------------------------------------------------------
# speaker map: append-only, supersede-by-hash
# ---------------------------------------------------------------------------


def test_bind_speaker_returns_a_new_state_and_is_visible_in_active_bindings():
    state = EpisodeState().bind_speaker(
        cluster_id="S2",
        roster_name="J. Doe",
        source=SpeakerEvidenceSource.SELF_INTRODUCTION,
        chunk=0,
        quote="Hi, this is J. Doe from the PM team.",
    )
    active = state.active_speaker_bindings()
    assert len(active) == 1
    b = active[0]
    assert b.cluster_id == "S2"
    assert b.roster_name == "J. Doe"
    assert b.source == SpeakerEvidenceSource.SELF_INTRODUCTION
    assert b.chunk == 0


def test_resolve_speaker_returns_none_for_unknown_cluster():
    state = EpisodeState()
    assert state.resolve_speaker("S99") is None


def test_resolve_speaker_latest_active_binding_wins_on_confirming_evidence():
    state = (
        EpisodeState()
        .bind_speaker(cluster_id="S1", roster_name="A. Smith", source=SpeakerEvidenceSource.ROSTER_MATCH, chunk=0, quote="q0")
        .bind_speaker(cluster_id="S1", roster_name="A. Smith", source=SpeakerEvidenceSource.SELF_INTRODUCTION, chunk=2, quote="q2")
    )
    resolved = state.resolve_speaker("S1")
    assert resolved is not None
    assert resolved.roster_name == "A. Smith"
    assert resolved.chunk == 2  # the later evidence record


def test_speaker_binding_correction_supersedes_the_wrong_entry():
    state = EpisodeState().bind_speaker(
        cluster_id="S3", roster_name="Wrong Name", source=SpeakerEvidenceSource.ROSTER_MATCH, chunk=0, quote="misheard"
    )
    wrong_hash = state.speaker_log.entries[0].entry_hash

    state = state.bind_speaker(
        cluster_id="S3",
        roster_name="Right Name",
        source=SpeakerEvidenceSource.MANUAL,
        chunk=1,
        quote="corrected by owner review",
        supersedes=wrong_hash,
    )

    active = state.active_speaker_bindings()
    assert len(active) == 1
    assert active[0].roster_name == "Right Name"
    assert state.resolve_speaker("S3").roster_name == "Right Name"


def test_speaker_binding_correction_of_unknown_hash_raises_and_never_mutates():
    state = EpisodeState().bind_speaker(
        cluster_id="S4", roster_name="Name", source=SpeakerEvidenceSource.ROSTER_MATCH, chunk=0, quote="q"
    )
    before = state.speaker_log.entries

    with pytest.raises(ValueError):
        state.bind_speaker(
            cluster_id="S4",
            roster_name="Other",
            source=SpeakerEvidenceSource.MANUAL,
            chunk=1,
            quote="q2",
            supersedes="not-a-real-hash",
        )

    assert state.speaker_log.entries == before


# ---------------------------------------------------------------------------
# decision / action ledger: append-only
# ---------------------------------------------------------------------------


def test_add_ledger_entry_returns_a_new_state_visible_in_active_entries():
    state = EpisodeState().add_ledger_entry(
        kind=LedgerEntryKind.DECISION,
        text="Ship the v2 API by Friday.",
        owner_speaker="S1",
        chunk=1,
        evidence_span_refs=("seg-12", "seg-13"),
    )
    active = state.active_ledger_entries()
    assert len(active) == 1
    entry = active[0]
    assert entry.kind == LedgerEntryKind.DECISION
    assert entry.text == "Ship the v2 API by Friday."
    assert entry.owner_speaker == "S1"
    assert entry.chunk == 1
    assert entry.evidence_span_refs == ("seg-12", "seg-13")


def test_ledger_entry_default_evidence_span_refs_is_empty():
    state = EpisodeState().add_ledger_entry(
        kind=LedgerEntryKind.ACTION, text="Follow up with legal.", owner_speaker=None, chunk=0
    )
    assert state.active_ledger_entries()[0].evidence_span_refs == ()


def test_ledger_entry_correction_supersedes_the_wrong_entry():
    state = EpisodeState().add_ledger_entry(
        kind=LedgerEntryKind.ACTION, text="Wrong owner recorded", owner_speaker="S1", chunk=0
    )
    wrong_hash = state.ledger_log.entries[0].entry_hash
    state = state.add_ledger_entry(
        kind=LedgerEntryKind.ACTION,
        text="Wrong owner recorded",
        owner_speaker="S2",
        chunk=1,
        supersedes=wrong_hash,
    )
    active = state.active_ledger_entries()
    assert len(active) == 1
    assert active[0].owner_speaker == "S2"


def test_ledger_and_speaker_logs_are_independent():
    state = EpisodeState().add_ledger_entry(kind=LedgerEntryKind.DECISION, text="d", owner_speaker=None, chunk=0)
    wrong_ledger_hash = state.ledger_log.entries[0].entry_hash

    # A ledger-log hash must not satisfy the speaker-log's supersede check
    # (they are two independent hash chains, not one shared namespace).
    with pytest.raises(ValueError):
        state.bind_speaker(
            cluster_id="S1",
            roster_name="Name",
            source=SpeakerEvidenceSource.MANUAL,
            chunk=0,
            quote="q",
            supersedes=wrong_ledger_hash,
        )


# ---------------------------------------------------------------------------
# serialization / round-trip / content hash
# ---------------------------------------------------------------------------


def _rich_state() -> EpisodeState:
    state = EpisodeState()
    state = state.with_glossary_chunk([glossary_entry("Ortega", chunk=0, introduced_by="S1")])
    state = state.bind_speaker(
        cluster_id="S1", roster_name="A. Ortega", source=SpeakerEvidenceSource.SELF_INTRODUCTION, chunk=0, quote="q"
    )
    state = state.add_ledger_entry(
        kind=LedgerEntryKind.DECISION, text="Approve the budget.", owner_speaker="S1", chunk=0, evidence_span_refs=("seg-1",)
    )
    return state


def test_round_trip_through_to_dict_from_dict_preserves_equality():
    state = _rich_state()
    restored = EpisodeState.from_dict(state.to_dict())
    assert restored == state


def test_round_trip_preserves_content_hash():
    state = _rich_state()
    restored = EpisodeState.from_dict(state.to_dict())
    assert restored.content_hash() == state.content_hash()


def test_content_hash_changes_when_state_changes():
    empty = EpisodeState()
    with_glossary = empty.with_glossary_chunk([glossary_entry("Ortega")])
    assert empty.content_hash() != with_glossary.content_hash()


def test_content_hash_is_stable_for_identical_states():
    a = _rich_state()
    b = _rich_state()
    assert a.content_hash() == b.content_hash()


def test_snapshot_shape_and_invariants():
    state = _rich_state()
    snap = state.snapshot(chunk_index=0)
    assert isinstance(snap, EpisodeStateSnapshot)
    assert snap.chunk_index == 0
    assert snap.content_hash == state.content_hash()
    assert snap.glossary_size == 1
    assert snap.speaker_binding_count == 1
    assert snap.ledger_entry_count == 1


def test_snapshot_to_dict_shape():
    state = _rich_state()
    d = state.snapshot(chunk_index=3).to_dict()
    assert d == {
        "chunk_index": 3,
        "content_hash": state.content_hash(),
        "glossary_size": 1,
        "speaker_binding_count": 1,
        "ledger_entry_count": 1,
    }


def test_to_dict_round_trips_m1_leakage_tier_and_provenance_metadata():
    state = EpisodeState().with_glossary_chunk(
        [glossary_entry("SecretCode", provenance=ProvenanceTag.METADATA, tier=LeakageTier.M1)]
    )
    restored = EpisodeState.from_dict(state.to_dict())
    assert restored.glossary[0].provenance == ProvenanceTag.METADATA
    assert restored.glossary[0].leakage_tier == LeakageTier.M1


def test_empty_state_round_trips_and_hashes_trivially():
    empty = EpisodeState()
    restored = EpisodeState.from_dict(empty.to_dict())
    assert restored == empty
    assert restored.content_hash() == empty.content_hash()
