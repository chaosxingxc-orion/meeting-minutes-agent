"""Tests for :mod:`meeting_minutes_agent.glossary.dedupe`."""

from __future__ import annotations

from meeting_minutes_agent.glossary.dedupe import Cluster, dedupe_candidates
from meeting_minutes_agent.glossary.extract import Candidate


def test_variants_group_by_normalised_surface_and_evidence_sums():
    candidates = [
        Candidate("Denver", "capitalized_run"),
        Candidate("Denver", "capitalized_run"),
        Candidate("denver", "repeated_oov"),
    ]
    clusters = dedupe_candidates(candidates)
    assert clusters == [Cluster(canonical_surface="Denver", variants=("Denver", "denver"), evidence_count=3)]


def test_canonical_surface_is_the_most_frequent_variant():
    candidates = [Candidate("Denver", "m"), Candidate("DENVER", "m"), Candidate("DENVER", "m")]
    clusters = dedupe_candidates(candidates)
    assert clusters[0].canonical_surface == "DENVER"
    assert clusters[0].evidence_count == 3


def test_tie_break_is_alphabetical_on_equal_counts():
    candidates = [Candidate("bob", "m"), Candidate("Bob", "m")]
    clusters = dedupe_candidates(candidates)
    assert clusters[0].canonical_surface == "Bob"  # 'B' (0x42) < 'b' (0x62)
    assert clusters[0].variants == ("Bob", "bob")


def test_distinct_surfaces_form_distinct_clusters_in_first_seen_order():
    candidates = [Candidate("Zed", "m"), Candidate("Alpha", "m"), Candidate("Zed", "m")]
    clusters = dedupe_candidates(candidates)
    assert [c.canonical_surface for c in clusters] == ["Zed", "Alpha"]


def test_candidates_normalising_to_empty_string_are_dropped():
    candidates = [Candidate("---", "m"), Candidate("Denver", "m")]
    clusters = dedupe_candidates(candidates)
    assert len(clusters) == 1
    assert clusters[0].canonical_surface == "Denver"


def test_empty_input_gives_empty_output():
    assert dedupe_candidates([]) == []
