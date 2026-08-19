"""Tests for :mod:`meeting_minutes_agent.chunking.rttm`: SPEAKER-line
parsing, non-SPEAKER/comment/blank-line skipping, malformed-line refusal,
and the write/parse round trip."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.rttm import (
    RttmParseError,
    parse_rttm_file,
    parse_rttm_text,
    write_rttm_file,
    write_rttm_text,
)
from meeting_minutes_agent.chunking.slicer import TurnSpan


class TestParseRttmText:
    def test_parses_speaker_lines_into_turn_spans(self):
        text = (
            "SPEAKER MTG1 1 0.000 5.500 <NA> <NA> A <NA> <NA>\n"
            "SPEAKER MTG1 1 5.500 3.250 <NA> <NA> B <NA> <NA>\n"
        )
        turns = parse_rttm_text(text)
        assert turns == (
            TurnSpan(0.0, 5.5, "A"),
            TurnSpan(5.5, 8.75, "B"),
        )

    def test_result_is_sorted_by_start_then_end_then_speaker(self):
        text = (
            "SPEAKER MTG1 1 10.0 1.0 <NA> <NA> B <NA> <NA>\n"
            "SPEAKER MTG1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\n"
        )
        turns = parse_rttm_text(text)
        assert [t.speaker for t in turns] == ["A", "B"]

    def test_blank_and_comment_lines_are_skipped(self):
        text = (
            "; this is a comment\n"
            "\n"
            "   \n"
            "SPEAKER MTG1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\n"
        )
        turns = parse_rttm_text(text)
        assert turns == (TurnSpan(0.0, 1.0, "A"),)

    def test_non_speaker_record_types_are_skipped(self):
        text = (
            "SEGMENT MTG1 1 0.0 20.0 <NA> <NA>\n"
            "NOSCORE MTG1 1 0.0 1.0 <NA>\n"
            "SPEAKER MTG1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\n"
        )
        turns = parse_rttm_text(text)
        assert turns == (TurnSpan(0.0, 1.0, "A"),)

    def test_empty_text_yields_no_turns(self):
        assert parse_rttm_text("") == ()

    def test_too_few_fields_raises(self):
        with pytest.raises(RttmParseError, match="field"):
            parse_rttm_text("SPEAKER MTG1 1 0.0 1.0 A\n")

    def test_non_numeric_onset_raises(self):
        with pytest.raises(RttmParseError, match="numeric"):
            parse_rttm_text("SPEAKER MTG1 1 zero 1.0 <NA> <NA> A <NA> <NA>\n")

    def test_non_numeric_duration_raises(self):
        with pytest.raises(RttmParseError, match="numeric"):
            parse_rttm_text("SPEAKER MTG1 1 0.0 abc <NA> <NA> A <NA> <NA>\n")

    def test_non_positive_duration_raises(self):
        with pytest.raises(RttmParseError, match="duration"):
            parse_rttm_text("SPEAKER MTG1 1 0.0 0.0 <NA> <NA> A <NA> <NA>\n")

    def test_missing_speaker_name_raises(self):
        with pytest.raises(RttmParseError, match="speaker"):
            parse_rttm_text("SPEAKER MTG1 1 0.0 1.0 <NA> <NA> <NA> <NA> <NA>\n")


class TestParseRttmFile:
    def test_reads_from_disk(self, tmp_path):
        path = tmp_path / "meeting.rttm"
        path.write_text("SPEAKER MTG1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\n", encoding="utf-8")
        assert parse_rttm_file(path) == (TurnSpan(0.0, 1.0, "A"),)


class TestWriteRttmText:
    def test_writes_one_speaker_line_per_turn(self):
        turns = (TurnSpan(0.0, 5.5, "A"), TurnSpan(5.5, 8.75, "B"))
        text = write_rttm_text(turns, file_id="MTG1")
        lines = text.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("SPEAKER MTG1 1 0.000 5.500")
        assert lines[0].endswith("A <NA> <NA>")

    def test_empty_turns_yields_empty_text(self):
        assert write_rttm_text((), file_id="MTG1") == ""

    def test_custom_channel(self):
        text = write_rttm_text((TurnSpan(0.0, 1.0, "A"),), file_id="MTG1", channel="2")
        assert text.startswith("SPEAKER MTG1 2 ")


class TestRoundTrip:
    def test_parse_of_write_reproduces_the_turns(self):
        turns = (
            TurnSpan(0.0, 5.5, "A"),
            TurnSpan(5.5, 8.75, "B"),
            TurnSpan(8.75, 20.125, "A"),
        )
        round_tripped = parse_rttm_text(write_rttm_text(turns, file_id="MTG1"))
        assert round_tripped == turns

    def test_round_trip_through_a_real_file(self, tmp_path):
        turns = (TurnSpan(0.0, 5.5, "A"), TurnSpan(5.5, 8.75, "B"))
        path = write_rttm_file(turns, tmp_path / "out" / "meeting.rttm", file_id="MTG1")
        assert path.is_file()
        assert parse_rttm_file(path) == turns

    def test_round_trip_is_stable_under_a_second_write(self, tmp_path):
        # write -> parse -> write again -> parse again reproduces the same
        # turns (idempotent at 3-decimal precision).
        turns = (TurnSpan(0.0, 10.0, "A"), TurnSpan(10.0, 20.5, "B"))
        first = parse_rttm_text(write_rttm_text(turns, file_id="MTG1"))
        second = parse_rttm_text(write_rttm_text(first, file_id="MTG1"))
        assert first == second == turns
