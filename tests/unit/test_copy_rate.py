from __future__ import annotations

from meeting_minutes_agent.instrumentation.copy_rate import (
    compute_copy_rate,
    count_verbatim_occurrences,
    normalize_tokens,
)


def test_normalize_tokens_lowercases_and_strips_punctuation():
    assert normalize_tokens("Hello, TEAM!") == ["hello", "team"]


def test_normalize_tokens_empty_string():
    assert normalize_tokens("") == []


def test_count_verbatim_occurrences_finds_contiguous_subsequence():
    haystack = ["the", "quick", "brown", "fox"]
    needle = ["quick", "brown"]
    assert count_verbatim_occurrences(haystack, needle) == 1


def test_count_verbatim_occurrences_counts_multiple_hits():
    haystack = ["a", "b", "a", "b", "a", "b"]
    needle = ["a", "b"]
    assert count_verbatim_occurrences(haystack, needle) == 3


def test_count_verbatim_occurrences_rejects_out_of_order():
    haystack = ["brown", "quick"]
    needle = ["quick", "brown"]
    assert count_verbatim_occurrences(haystack, needle) == 0


def test_count_verbatim_occurrences_empty_needle_is_zero():
    assert count_verbatim_occurrences(["a", "b"], []) == 0


def test_count_verbatim_occurrences_needle_longer_than_haystack_is_zero():
    assert count_verbatim_occurrences(["a"], ["a", "b"]) == 0


def test_compute_copy_rate_pairwise():
    produced = [
        "The remote will sell for 25 Euro, definitely.",
        "Something totally unrelated was said here.",
    ]
    reference = [
        "the remote will sell for 25 euro",
        "the remote will sell for 25 euro",
    ]
    result = compute_copy_rate(produced, reference)
    assert result.total_items == 2
    assert result.items_with_copy == 1
    assert result.copy_rate == 0.5


def test_compute_copy_rate_empty_reference_never_counts_as_copy():
    result = compute_copy_rate(["anything"], [""])
    assert result.items_with_copy == 0
    assert result.copy_rate == 0.0


def test_compute_copy_rate_zero_items_never_zero_division():
    result = compute_copy_rate([], [])
    assert result.copy_rate == 0.0


def test_compute_copy_rate_rejects_length_mismatch():
    import pytest

    with pytest.raises(ValueError):
        compute_copy_rate(["a"], ["a", "b"])
