"""Tests for :mod:`meeting_minutes_agent.heads.qa`: the meeting-QA request
builder and the strict/lenient abstention-aware parse pair. Parse failures
must always be DATA on the result, never a raised exception, and a
``"failed"`` parse must never be confused with a genuine model
abstention."""

from __future__ import annotations

from meeting_minutes_agent.heads.qa import (
    QUESTION_SECTION_HEADER,
    SYSTEM_INSTRUCTION_TEMPLATE,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
    QAParseResult,
    build_qa_request,
    parse_qa_response,
)
from meeting_minutes_agent.runreceipt import config_hash

# ---------------------------------------------------------------------------
# template hash pin (an independent copy of the pinned text, separate from
# the imported source constant -- see the sibling heads' equivalent pin test)
# ---------------------------------------------------------------------------

_EXPECTED_TEMPLATE_ID = "qa-v1"
_EXPECTED_SYSTEM_INSTRUCTION = (
    "Answer the question below using ONLY the meeting audio you are given. "
    "If the audio does not contain enough information to answer the "
    "question, output EXACTLY this single line and nothing else:\n"
    "ABSTAIN\n"
    "Otherwise output one or more answer lines, each in EXACTLY this "
    "format:\n"
    "ANSWER: <verbatim answer text>\n"
    "Output more than one ANSWER line only when the answer is genuinely "
    "made of separate, non-contiguous parts of the meeting. Output ONLY "
    "the ABSTAIN line or one or more ANSWER lines; no extra commentary "
    "before, between, or after them."
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
    req = build_qa_request(question="What did the team decide?")
    assert req.template_id == TEMPLATE_ID
    assert req.template_sha256 == TEMPLATE_SHA256
    assert req.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE


def test_build_request_question_only_has_no_supply_block():
    req = build_qa_request(question="What did the team decide?")
    assert len(req.supplied_text) == 1
    assert req.supplied_text[0] == f"{QUESTION_SECTION_HEADER}\nWhat did the team decide?"


def test_build_request_default_supply_text_is_none_for_the_zero_supply_arm():
    # docs/readiness/2026-08-18-g1-preregistration-draft.md SS2 Z-qa arm:
    # supply_text must default to None, never a caller-invisible non-empty
    # block, so a zero-supply request really carries zero supply.
    req_default = build_qa_request(question="Q?")
    req_explicit_none = build_qa_request(question="Q?", supply_text=None)
    assert req_default == req_explicit_none
    assert len(req_default.supplied_text) == 1


def test_build_request_with_supply_text_prepends_supply_block():
    req = build_qa_request(question="What did the team decide?", supply_text="=== KNOWN TERMS ===\n(none)")
    assert len(req.supplied_text) == 2
    assert req.supplied_text[0] == "=== KNOWN TERMS ===\n(none)"
    assert req.supplied_text[1] == f"{QUESTION_SECTION_HEADER}\nWhat did the team decide?"


def test_build_request_two_calls_with_same_inputs_are_equal():
    req_a = build_qa_request(question="Q?", supply_text="supply")
    req_b = build_qa_request(question="Q?", supply_text="supply")
    assert req_a == req_b


def test_build_request_passes_decoding_params_through():
    req = build_qa_request(question="Q?", decoding_params={"temperature": 0.0})
    assert req.decoding_params == {"temperature": 0.0}


# ---------------------------------------------------------------------------
# parsing: strict success
# ---------------------------------------------------------------------------


def test_parse_strict_abstain():
    result = parse_qa_response("ABSTAIN")
    assert result.parse_mode == "strict"
    assert result.answer_spans == ()
    assert result.malformed_lines == ()


def test_parse_strict_single_answer():
    result = parse_qa_response("ANSWER: the budget was approved")
    assert result.parse_mode == "strict"
    assert result.answer_spans == ("the budget was approved",)
    assert result.malformed_lines == ()


def test_parse_strict_multi_span_answer():
    raw = "ANSWER: first part of the answer\nANSWER: second, non-contiguous part"
    result = parse_qa_response(raw)
    assert result.parse_mode == "strict"
    assert result.answer_spans == ("first part of the answer", "second, non-contiguous part")


def test_parse_ignores_blank_lines_around_a_strict_reply():
    result = parse_qa_response("\n\nANSWER: yes\n\n")
    assert result.parse_mode == "strict"
    assert result.answer_spans == ("yes",)


# ---------------------------------------------------------------------------
# parsing: lenient fallback, parse failures as DATA
# ---------------------------------------------------------------------------


def test_parse_lenient_case_insensitive_answer_prefix():
    result = parse_qa_response("answer: the budget was approved")
    assert result.parse_mode == "lenient"
    assert result.answer_spans == ("the budget was approved",)
    assert result.malformed_lines == ()


def test_parse_lenient_dash_prefixed_answer():
    result = parse_qa_response("- Answer: the budget was approved")
    assert result.parse_mode == "lenient"
    assert result.answer_spans == ("the budget was approved",)


def test_parse_lenient_abstain_variants():
    for raw in ("abstain", "Abstain.", "ABSTAIN:"):
        result = parse_qa_response(raw)
        assert result.parse_mode == "lenient", raw
        assert result.answer_spans == (), raw


def test_parse_mixed_answer_and_malformed_line_is_lenient_not_raised():
    raw = "ANSWER: the budget was approved\nthis line has no recognisable grammar at all"
    result = parse_qa_response(raw)
    assert result.parse_mode == "lenient"
    assert result.answer_spans == ("the budget was approved",)
    assert result.malformed_lines == ("this line has no recognisable grammar at all",)


def test_parse_real_answer_content_wins_over_a_stray_abstain_marker():
    raw = "ABSTAIN\nANSWER: actually, here is the answer"
    result = parse_qa_response(raw)
    assert result.parse_mode == "lenient"
    assert result.answer_spans == ("actually, here is the answer",)
    # the stray ABSTAIN line was recognised (not content the model meant as
    # an answer), so it is not reported as an unparseable line
    assert result.malformed_lines == ()


def test_parse_lenient_preserves_good_lines_before_a_bad_one():
    raw = "ANSWER: first good span\nnot parseable\nANSWER: second good span"
    result = parse_qa_response(raw)
    assert result.answer_spans == ("first good span", "second good span")


def test_parse_totally_unparseable_text_fails_without_raising():
    result = parse_qa_response("just some prose\nwith no structure at all")
    assert result.parse_mode == "failed"
    assert result.answer_spans == ()
    assert result.malformed_lines == ("just some prose", "with no structure at all")


def test_parse_empty_text_fails_without_raising():
    result = parse_qa_response("")
    assert result.parse_mode == "failed"
    assert result.answer_spans == ()
    assert result.malformed_lines == ()


def test_parse_whitespace_only_text_fails_without_raising():
    result = parse_qa_response("   \n\n  \n")
    assert result.parse_mode == "failed"
    assert result.answer_spans == ()


def test_parse_failed_mode_is_never_a_silent_abstention():
    # a "failed" parse and a genuine ("strict"/"lenient") abstention both
    # report answer_spans == (); parse_mode is the only thing that tells
    # them apart, and callers must not conflate the two.
    failed = parse_qa_response("gibberish")
    abstained = parse_qa_response("ABSTAIN")
    assert failed.answer_spans == abstained.answer_spans == ()
    assert failed.parse_mode == "failed"
    assert abstained.parse_mode == "strict"
    assert failed.parse_mode != abstained.parse_mode


def test_parse_result_to_dict_shape():
    result = parse_qa_response("ANSWER: yes")
    d = result.to_dict()
    assert d == {
        "answer_spans": ["yes"],
        "parse_mode": "strict",
        "malformed_lines": [],
        "raw_text": "ANSWER: yes",
    }


def test_parse_result_is_a_dataclass_instance():
    assert isinstance(parse_qa_response("ABSTAIN"), QAParseResult)
