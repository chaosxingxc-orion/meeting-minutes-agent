"""Tests for :mod:`meeting_minutes_agent.glossary.normalise`."""

from __future__ import annotations

from meeting_minutes_agent.glossary.normalise import normalise_surface


def test_lowercase_and_whitespace_collapse():
    assert normalise_surface("  MULTIPLE   Spaces  ") == "multiple spaces"


def test_punctuation_is_stripped():
    assert normalise_surface("Denver's  Office") == "denvers office"


def test_hyphen_like_characters_all_unify_to_ascii_hyphen():
    variants = ["co-op", "co‑op", "co–op", "co—op", "co_op"]  # -, non-breaking hyphen, en-dash, em-dash, underscore
    normalised = {normalise_surface(v) for v in variants}
    assert normalised == {"co-op"}


def test_leading_and_trailing_hyphens_are_stripped():
    assert normalise_surface("-test-") == "test"


def test_period_separated_acronym_normalises_to_bare_letters():
    assert normalise_surface("N.A.S.A") == "nasa"


def test_empty_and_punctuation_only_normalise_to_empty_string():
    assert normalise_surface("") == ""
    assert normalise_surface("---") == ""
    assert normalise_surface("...") == ""
