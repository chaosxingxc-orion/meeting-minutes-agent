"""Tests for :mod:`meeting_minutes_agent.heads.qa`: an interface-complete
stub -- every entry point must raise, naming the MeetingQA-floor
precondition, never return a placeholder result."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.heads.qa import (
    MeetingQAFloorNotMeasuredError,
    build_qa_request,
    parse_qa_response,
)


def test_meeting_qa_floor_not_measured_error_is_a_not_implemented_error():
    assert issubclass(MeetingQAFloorNotMeasuredError, NotImplementedError)


def test_build_qa_request_raises_naming_the_precondition():
    with pytest.raises(MeetingQAFloorNotMeasuredError) as exc_info:
        build_qa_request()
    assert "MeetingQA-floor" in str(exc_info.value)


def test_build_qa_request_raises_regardless_of_arguments():
    with pytest.raises(MeetingQAFloorNotMeasuredError):
        build_qa_request("anything", keyword="also anything")


def test_parse_qa_response_raises_naming_the_precondition():
    with pytest.raises(MeetingQAFloorNotMeasuredError) as exc_info:
        parse_qa_response("some raw model text")
    assert "MeetingQA-floor" in str(exc_info.value)
