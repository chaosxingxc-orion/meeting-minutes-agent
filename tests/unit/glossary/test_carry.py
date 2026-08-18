"""Tests for :mod:`meeting_minutes_agent.glossary.carry`: per-chunk
new-vs-carried bookkeeping, frequency ranking, and the census's
first-half -> second-half mention-coverage metric
(``docs/readiness/2026-08-17-meetingbank-entity-census.md`` SS7)."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.glossary.carry import (
    ChunkGlossarySnapshot,
    accumulate_glossary,
    carry_accounting,
    rank_terms_by_frequency,
    second_half_coverage,
)
from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag


def _entry(surface: str, evidence: int, first_seen: int, variants: tuple[str, ...] | None = None) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=variants if variants is not None else (surface,),
        first_seen_chunk=first_seen,
        evidence_count=evidence,
        provenance=ProvenanceTag.SPEECH_PASS,
        leakage_tier=LeakageTier.M0,
    )


# Hand-computed three-chunk episode: alpha and beta each recur once later
# (across chunk boundaries 1 and 2 respectively); gamma and delta are each
# introduced once and never recur.
CHUNK_0 = (_entry("alpha", 2, 0), _entry("beta", 1, 0))
CHUNK_1 = (_entry("alpha", 1, 1), _entry("gamma", 3, 1))
CHUNK_2 = (_entry("beta", 2, 2), _entry("delta", 1, 2))
CHUNKS = (CHUNK_0, CHUNK_1, CHUNK_2)


class TestChunkGlossarySnapshotInvariant:
    def test_mismatched_counts_are_rejected(self):
        with pytest.raises(ValueError):
            ChunkGlossarySnapshot(chunk_index=0, total_terms=5, new_terms=2, carried_terms=2)


class TestAccumulateGlossary:
    def test_final_state_matches_hand_computation(self):
        final = accumulate_glossary(CHUNKS)
        assert [(e.canonical_surface, e.evidence_count, e.first_seen_chunk) for e in final] == [
            ("alpha", 3, 0),
            ("beta", 3, 0),
            ("gamma", 3, 1),
            ("delta", 1, 2),
        ]


class TestCarryAccounting:
    def test_snapshots_match_hand_computation(self):
        report = carry_accounting(CHUNKS)
        assert len(report.snapshots) == 3

        s0, s1, s2 = report.snapshots
        assert s0 == ChunkGlossarySnapshot(chunk_index=0, total_terms=2, new_terms=2, carried_terms=0)
        assert s1 == ChunkGlossarySnapshot(chunk_index=1, total_terms=3, new_terms=1, carried_terms=2)
        assert s2 == ChunkGlossarySnapshot(chunk_index=2, total_terms=4, new_terms=1, carried_terms=3)

    def test_totals_match_hand_computation(self):
        report = carry_accounting(CHUNKS)
        assert report.total_new_terms == 4  # == final glossary size, every term is new exactly once
        assert report.total_carried_events == 5  # 0 + 2 + 3

    def test_final_glossary_matches_accumulate_glossary(self):
        report = carry_accounting(CHUNKS)
        assert report.final_glossary == accumulate_glossary(CHUNKS)

    def test_empty_episode_gives_no_snapshots(self):
        report = carry_accounting(())
        assert report.snapshots == ()
        assert report.final_glossary == ()
        assert report.total_new_terms == 0
        assert report.total_carried_events == 0

    def test_single_chunk_episode_has_no_carry(self):
        report = carry_accounting((CHUNK_0,))
        assert len(report.snapshots) == 1
        assert report.snapshots[0].carried_terms == 0
        assert report.snapshots[0].new_terms == 2


class TestRankTermsByFrequency:
    def test_ties_break_by_first_seen_then_alphabetically(self):
        entries = [
            _entry("Beta", 3, 0),
            _entry("Alpha", 3, 0),
            _entry("Later", 5, 1),
            _entry("Earlier", 5, 0),
        ]
        ranked = rank_terms_by_frequency(entries)
        assert [e.canonical_surface for e in ranked] == ["Earlier", "Later", "Alpha", "Beta"]

    def test_empty_input(self):
        assert rank_terms_by_frequency([]) == ()


class TestSecondHalfCoverage:
    FIRST_HALF = (
        _entry("Ortega", 5, 0, variants=("Ortega", "ortega")),
        _entry("Denver", 3, 0, variants=("Denver",)),
        _entry("Quorum", 2, 0, variants=("quorum",)),
    )
    SECOND_HALF_MENTIONS = ["ortega", "Ortega", "Denver", "denver", "quorum", "Unknown", "Random"]

    def test_unbounded_glossary_coverage_hand_computed(self):
        # 5 of 7 mentions normalise to a known term (ortega x2, denver x2, quorum x1).
        coverage = second_half_coverage(self.FIRST_HALF, self.SECOND_HALF_MENTIONS)
        assert coverage == pytest.approx(5 / 7)

    def test_top_n_restricts_to_the_highest_evidence_terms(self):
        # top_n=2 keeps Ortega(5) and Denver(3), dropping Quorum(2) -- the
        # "quorum" mention is no longer covered.
        coverage = second_half_coverage(self.FIRST_HALF, self.SECOND_HALF_MENTIONS, top_n=2)
        assert coverage == pytest.approx(4 / 7)

    def test_matches_variants_not_only_the_canonical_surface(self):
        entries = (_entry("Ortega", 1, 0, variants=("Ortega", "Ortiga")),)  # a fragmented ASR variant
        assert second_half_coverage(entries, ["Ortiga"]) == 1.0

    def test_empty_second_half_is_vacuously_zero_not_an_error(self):
        assert second_half_coverage((_entry("Ortega", 1, 0),), []) == 0.0

    def test_no_matching_terms_gives_zero_coverage(self):
        assert second_half_coverage((_entry("Ortega", 1, 0),), ["completely", "unrelated"]) == 0.0
