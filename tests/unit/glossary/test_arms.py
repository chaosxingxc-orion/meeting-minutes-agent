"""Tests for :mod:`meeting_minutes_agent.glossary.arms`: all six registered
REVISE-stage arms, each hand-traced against ``fixtures.CHUNK_0_TEXT``."""

from __future__ import annotations

import random

from meeting_minutes_agent.glossary.arms import (
    ArmKind,
    deranged_arm,
    gated_arm,
    naive_raw_arm,
    no_carry_arm,
    scrambled_raw_arm,
    uniform_ungated_arm,
)
from meeting_minutes_agent.glossary.pipeline import build_chunk_entries

from .fixtures import CHUNK_0_TEXT

# A single-entity fixture: only "Ortega" recurs enough to survive the
# default gate, giving exactly ONE post-gate entry -- used to exercise
# the deranged arm's n<2 (nothing to derange) edge case.
SINGLE_ENTITY_TEXT = "Today Ortega raised the item. Later Ortega closed it."


class TestGatedArm:
    def test_matches_build_chunk_entries_exactly(self):
        plan = gated_arm(CHUNK_0_TEXT, chunk_index=0)
        assert plan.kind is ArmKind.GATED
        assert plan.chunk_index == 0
        assert plan.entries == build_chunk_entries(CHUNK_0_TEXT, chunk_index=0)
        assert len(plan.entries) == 2


class TestNaiveRawArm:
    def test_every_raw_candidate_becomes_its_own_unmerged_entry(self):
        plan = naive_raw_arm(CHUNK_0_TEXT, chunk_index=0)
        assert plan.kind is ArmKind.NAIVE_RAW
        # 4 capitalized-run occurrences (Ortega x2, Fitzgerald x2) + 2
        # repeated-oov candidates (fitzgerald, ortega) = 6 raw, unmerged.
        assert len(plan.entries) == 6
        assert all(e.evidence_count == 1 for e in plan.entries)
        assert [e.canonical_surface for e in plan.entries] == [
            "Ortega",
            "Ortega",
            "Fitzgerald",
            "Fitzgerald",
            "fitzgerald",
            "ortega",
        ]
        # unmerged: each entry's own variants is just its own raw surface.
        assert all(e.variants == (e.canonical_surface,) for e in plan.entries)

    def test_no_candidates_gives_empty_plan(self):
        plan = naive_raw_arm("the quick brown fox.", chunk_index=0)
        assert plan.entries == ()


class TestScrambledRawArm:
    def test_content_is_a_permutation_of_the_naive_raw_multiset(self):
        from collections import Counter

        naive = naive_raw_arm(CHUNK_0_TEXT, chunk_index=0)
        scrambled = scrambled_raw_arm(CHUNK_0_TEXT, chunk_index=0, seed=7)
        assert scrambled.kind is ArmKind.SCRAMBLED_RAW
        assert scrambled.seed == 7
        assert Counter(scrambled.entries) == Counter(naive.entries)  # same content
        assert scrambled.entries != naive.entries  # but a different (scrambled) order, for this seed

    def test_same_seed_is_deterministic(self):
        a = scrambled_raw_arm(CHUNK_0_TEXT, chunk_index=0, seed=3)
        b = scrambled_raw_arm(CHUNK_0_TEXT, chunk_index=0, seed=3)
        assert a.entries == b.entries

    def test_matches_an_independent_reimplementation_of_the_shuffle(self):
        naive_order = list(naive_raw_arm(CHUNK_0_TEXT, chunk_index=0).entries)
        expected = list(naive_order)
        random.Random(11).shuffle(expected)
        scrambled = scrambled_raw_arm(CHUNK_0_TEXT, chunk_index=0, seed=11)
        assert list(scrambled.entries) == expected


class TestUniformUngatedArm:
    def test_clean_deduped_list_with_evidence_forced_to_one(self):
        plan = uniform_ungated_arm(CHUNK_0_TEXT, chunk_index=0)
        assert plan.kind is ArmKind.UNIFORM_UNGATED
        assert [e.canonical_surface for e in plan.entries] == ["Ortega", "Fitzgerald"]
        assert all(e.evidence_count == 1 for e in plan.entries)
        assert plan.entries[0].variants == ("Ortega", "ortega")
        assert plan.entries[1].variants == ("Fitzgerald", "fitzgerald")

    def test_a_below_threshold_term_survives_because_no_gate_runs(self):
        # "Solo" appears only once -- the default gate (min_evidence=2)
        # would drop it, but uniform-ungated applies no gate at all.
        plan = uniform_ungated_arm("Today Solo attended the meeting.", chunk_index=0)
        assert [e.canonical_surface for e in plan.entries] == ["Solo"]
        assert plan.entries[0].evidence_count == 1


class TestDerangedArm:
    def test_two_entry_derangement_swaps_evidence_between_terms(self):
        clean = build_chunk_entries(CHUNK_0_TEXT, chunk_index=0)
        plan = deranged_arm(CHUNK_0_TEXT, chunk_index=0, seed=0)
        assert plan.kind is ArmKind.DERANGED
        assert plan.seed == 0
        assert len(plan.entries) == 2

        # identity fields (surface/first_seen/provenance/tier) unchanged...
        for original, deranged in zip(clean, plan.entries):
            assert deranged.canonical_surface == original.canonical_surface
            assert deranged.first_seen_chunk == original.first_seen_chunk
            assert deranged.provenance == original.provenance
            assert deranged.leakage_tier == original.leakage_tier
            # ...but the evidence payload (variants here) came from the OTHER entry.
            assert deranged.variants != original.variants

        assert plan.entries[0].variants == clean[1].variants
        assert plan.entries[1].variants == clean[0].variants

    def test_fewer_than_two_entries_cannot_be_deranged(self):
        clean = build_chunk_entries(SINGLE_ENTITY_TEXT, chunk_index=0)
        assert len(clean) == 1
        plan = deranged_arm(SINGLE_ENTITY_TEXT, chunk_index=0, seed=0)
        assert plan.entries == clean

    def test_zero_entries_cannot_be_deranged(self):
        plan = deranged_arm("the quick brown fox.", chunk_index=0, seed=0)
        assert plan.entries == ()


class TestNoCarryArm:
    def test_per_chunk_construction_matches_gated_content(self):
        gated = gated_arm(CHUNK_0_TEXT, chunk_index=0)
        no_carry = no_carry_arm(CHUNK_0_TEXT, chunk_index=0)
        assert no_carry.kind is ArmKind.NO_CARRY
        assert no_carry.entries == gated.entries
        assert no_carry.kind != gated.kind  # only the arm tag distinguishes them
