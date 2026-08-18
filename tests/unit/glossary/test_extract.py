"""Tests for :mod:`meeting_minutes_agent.glossary.extract`: the three
rule-based candidate miners, each exercised in isolation with minimal
strings chosen so the miners do not overlap (see ``fixtures.py`` for the
deliberately-overlapping integration fixture used by the pipeline/arm
tests)."""

from __future__ import annotations

from meeting_minutes_agent.glossary.extract import (
    Candidate,
    RuleBasedExtractor,
    extract_candidates,
    extract_capitalized_runs,
    extract_repeated_oov_tokens,
    extract_spelled_out_sequences,
)


class TestCapitalizedRuns:
    def test_sentence_initial_token_alone_is_excluded(self):
        assert extract_capitalized_runs("Hello world.") == []

    def test_multi_word_run_joins_consecutive_non_initial_capitals(self):
        out = extract_capitalized_runs("We met John Smith yesterday.")
        assert out == [Candidate("John Smith", "capitalized_run")]

    def test_first_person_pronoun_never_starts_a_run_but_trailing_run_still_flushes(self):
        out = extract_capitalized_runs("I met Sarah.")
        assert out == [Candidate("Sarah", "capitalized_run")]

    def test_multiple_sentences_each_reset_initial_position(self):
        out = extract_capitalized_runs("Today Ortega spoke. Then Ortega left.")
        assert out == [Candidate("Ortega", "capitalized_run"), Candidate("Ortega", "capitalized_run")]

    def test_no_capitals_gives_empty_list(self):
        assert extract_capitalized_runs("nothing capitalized here at all.") == []


class TestSpelledOutSequences:
    def test_spelled_out_run_collapses_into_one_token(self):
        out = extract_spelled_out_sequences("The P G L O S S report was filed.")
        assert out == [Candidate("PGLOSS", "spelled_out")]

    def test_a_single_letter_is_not_enough_to_match(self):
        assert extract_spelled_out_sequences("The A report.") == []

    def test_two_letters_is_the_minimum_match(self):
        out = extract_spelled_out_sequences("Approved by the U N committee.")
        assert out == [Candidate("UN", "spelled_out")]

    def test_no_letters_gives_empty_list(self):
        assert extract_spelled_out_sequences("nothing to see here.") == []


class TestRepeatedOovTokens:
    def test_repeated_words_meeting_the_threshold_are_returned_sorted(self):
        out = extract_repeated_oov_tokens("budget budget review process review")
        assert out == [Candidate("budget", "repeated_oov"), Candidate("review", "repeated_oov")]

    def test_single_occurrence_is_dropped(self):
        out = extract_repeated_oov_tokens("process appears only once here")
        assert out == []

    def test_stopwords_are_excluded_regardless_of_repeat_count(self):
        out = extract_repeated_oov_tokens("that that this this")
        assert out == []

    def test_short_tokens_under_four_chars_are_excluded(self):
        out = extract_repeated_oov_tokens("at at go go")
        assert out == []

    def test_custom_min_repeats_raises_the_bar(self):
        out = extract_repeated_oov_tokens("term term term other other", min_repeats=3)
        assert out == [Candidate("term", "repeated_oov")]

    def test_case_insensitive_counting(self):
        out = extract_repeated_oov_tokens("Budget budget BUDGET")
        assert out == [Candidate("budget", "repeated_oov")]


class TestExtractCandidatesAndExtractor:
    def test_extract_candidates_combines_all_three_miners(self):
        text = "The P G L O S S budget budget was filed by Ortega."
        combined = extract_candidates(text)
        methods = {c.method for c in combined}
        assert methods == {"capitalized_run", "spelled_out", "repeated_oov"}

    def test_rule_based_extractor_matches_the_free_function(self):
        text = "budget budget review review"
        extractor = RuleBasedExtractor()
        assert extractor.extract(text) == extract_candidates(text)

    def test_rule_based_extractor_honours_min_repeats(self):
        text = "term term term other other"
        extractor = RuleBasedExtractor(min_repeats=3)
        assert extractor.extract(text) == extract_candidates(text, min_repeats=3)
