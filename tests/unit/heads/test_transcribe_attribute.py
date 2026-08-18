"""Tests for :mod:`meeting_minutes_agent.heads.transcribe_attribute`: the
LISTEN request builder and the strict/lenient parse pair. Parse failures
must always be DATA on the result, never a raised exception."""

from __future__ import annotations

from meeting_minutes_agent.heads.transcribe_attribute import (
    CONTEXT_SECTION_HEADER,
    SYSTEM_INSTRUCTION_TEMPLATE,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
    TranscribedSegment,
    build_transcribe_attribute_request,
    parse_transcribe_attribute_response,
)
from meeting_minutes_agent.runreceipt import config_hash

from .fixtures import SPAN_CONTEXT

# ---------------------------------------------------------------------------
# template hash pin (an independent copy of the pinned text, separate from
# the imported source constant -- see supply's equivalent pin test)
# ---------------------------------------------------------------------------

_EXPECTED_TEMPLATE_ID = "transcribe-attribute-v1"
_EXPECTED_SYSTEM_INSTRUCTION = (
    "You are transcribing and attributing one chunk of a multi-speaker "
    "meeting recording. Produce one line per speech segment in EXACTLY "
    "this format:\n"
    "<speaker>|<text>\n"
    "Use the KNOWN TERMS spelling and SPEAKER MAP roster names supplied "
    "below when confident; otherwise use the raw speaker cluster id from "
    "the CONTEXT section. Output ONLY these lines, one segment per line, "
    "with no extra commentary before, between, or after them."
)


def test_template_id_is_pinned():
    assert TEMPLATE_ID == _EXPECTED_TEMPLATE_ID


def test_template_sha256_matches_an_independently_recomputed_hash_of_the_pinned_text():
    assert SYSTEM_INSTRUCTION_TEMPLATE == _EXPECTED_SYSTEM_INSTRUCTION
    expected = config_hash({"template_id": _EXPECTED_TEMPLATE_ID, "system_instruction": _EXPECTED_SYSTEM_INSTRUCTION})
    assert TEMPLATE_SHA256 == expected


# ---------------------------------------------------------------------------
# request building
# ---------------------------------------------------------------------------


def test_build_request_carries_template_identity_and_instruction():
    req = build_transcribe_attribute_request(supply_text="=== KNOWN TERMS ===\n(none)")
    assert req.template_id == TEMPLATE_ID
    assert req.template_sha256 == TEMPLATE_SHA256
    assert req.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE
    assert req.supplied_text == ("=== KNOWN TERMS ===\n(none)",)


def test_build_request_without_span_context_has_no_context_block():
    req = build_transcribe_attribute_request(supply_text="supply")
    assert len(req.supplied_text) == 1
    assert CONTEXT_SECTION_HEADER not in req.supplied_text[0]


def test_build_request_with_span_context_appends_context_block():
    req = build_transcribe_attribute_request(supply_text="supply", span_context=SPAN_CONTEXT)
    assert len(req.supplied_text) == 2
    context_part = req.supplied_text[1]
    assert context_part.startswith(CONTEXT_SECTION_HEADER)
    assert "[S1] Let's get started." in context_part
    assert "[S2] Sounds good." in context_part


def test_build_request_two_calls_with_same_inputs_are_equal():
    req_a = build_transcribe_attribute_request(supply_text="supply", span_context=SPAN_CONTEXT)
    req_b = build_transcribe_attribute_request(supply_text="supply", span_context=SPAN_CONTEXT)
    assert req_a == req_b


def test_build_request_passes_decoding_params_through():
    req = build_transcribe_attribute_request(supply_text="supply", decoding_params={"temperature": 0.0})
    assert req.decoding_params == {"temperature": 0.0}


# ---------------------------------------------------------------------------
# parsing: strict success
# ---------------------------------------------------------------------------


def test_parse_strict_success():
    raw = "S1|Hello there.\nS2|Hi, good to see you."
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "strict"
    assert result.malformed_lines == ()
    assert result.segments == (
        TranscribedSegment(speaker="S1", text="Hello there."),
        TranscribedSegment(speaker="S2", text="Hi, good to see you."),
    )


def test_parse_strict_text_may_itself_contain_pipe_characters():
    raw = "S1|Hello | World"
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "strict"
    assert result.segments[0].speaker == "S1"
    assert result.segments[0].text == "Hello | World"


def test_parse_ignores_blank_lines():
    raw = "S1|Hello.\n\n\nS2|Hi.\n"
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "strict"
    assert len(result.segments) == 2


# ---------------------------------------------------------------------------
# parsing: lenient fallback (bracket / colon forms), parse failures as DATA
# ---------------------------------------------------------------------------


def test_parse_lenient_bracket_and_colon_forms():
    raw = "[S1] Hello there.\nS2: Hi, good to see you."
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "lenient"
    assert result.malformed_lines == ()
    assert [s.speaker for s in result.segments] == ["S1", "S2"]
    assert [s.text for s in result.segments] == ["Hello there.", "Hi, good to see you."]


def test_parse_mixed_strict_and_malformed_lines_is_lenient_not_raised():
    raw = "S1|Hello there.\nthis line has no separator at all\nS2|Hi."
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "lenient"
    assert result.malformed_lines == ("this line has no separator at all",)
    assert [s.speaker for s in result.segments] == ["S1", "S2"]


def test_parse_lenient_preserves_good_lines_before_a_bad_one():
    # A strict-fails-fast internal loop must not lose earlier good lines --
    # the fallback re-parses ALL lines, not just from the failure point on.
    raw = "S1|First good line.\nnot parseable\nS2|Second good line."
    result = parse_transcribe_attribute_response(raw)
    assert len(result.segments) == 2
    assert result.segments[0].text == "First good line."
    assert result.segments[1].text == "Second good line."


def test_parse_totally_unparseable_text_fails_without_raising():
    raw = "just some prose\nwith no structure at all"
    result = parse_transcribe_attribute_response(raw)
    assert result.parse_mode == "failed"
    assert result.segments == ()
    assert result.malformed_lines == ("just some prose", "with no structure at all")


def test_parse_empty_text_fails_without_raising():
    result = parse_transcribe_attribute_response("")
    assert result.parse_mode == "failed"
    assert result.segments == ()
    assert result.malformed_lines == ()


def test_parse_whitespace_only_text_fails_without_raising():
    result = parse_transcribe_attribute_response("   \n\n  \n")
    assert result.parse_mode == "failed"
    assert result.segments == ()


def test_parse_result_to_dict_shape():
    raw = "S1|Hello."
    result = parse_transcribe_attribute_response(raw)
    d = result.to_dict()
    assert d["parse_mode"] == "strict"
    assert d["segments"] == [{"speaker": "S1", "text": "Hello."}]
    assert d["malformed_lines"] == []
    assert d["raw_text"] == raw
