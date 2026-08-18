"""Tests for :mod:`meeting_minutes_agent.heads.minutes`: the four-section
minutes request builder, the strict/lenient section+bullet+evidence parser,
and the SAER-M-compatible prediction projection. Parse failures must always
be DATA, never a raised exception."""

from __future__ import annotations

from meeting_minutes_agent.corpora.nxt.models import MINUTES_SECTIONS
from meeting_minutes_agent.heads.minutes import (
    SECTION_HEADERS,
    SYSTEM_INSTRUCTION_TEMPLATE,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
    TRANSCRIPT_SECTION_HEADER,
    build_minutes_request,
    parse_minutes_response,
)
from meeting_minutes_agent.metrics.saer_m import SpeakerAttributionPrediction
from meeting_minutes_agent.runreceipt import config_hash

from .fixtures import RESOLVED_TRANSCRIPT, STRICT_MINUTES_REPLY

# ---------------------------------------------------------------------------
# section vocabulary reuse
# ---------------------------------------------------------------------------


def test_section_headers_keys_match_corpora_minutes_sections_exactly():
    assert tuple(SECTION_HEADERS) == MINUTES_SECTIONS


# ---------------------------------------------------------------------------
# template hash pin
# ---------------------------------------------------------------------------

_EXPECTED_TEMPLATE_ID = "minutes-v1"
_EXPECTED_SYSTEM_INSTRUCTION = (
    "Produce meeting minutes for the episode so far from the resolved "
    "transcript and the known terms / speaker map supplied below. Output "
    "EXACTLY four sections, each starting on its own line with one of "
    "these exact headers, in this order: "
    "ABSTRACT:, ACTIONS:, DECISIONS:, PROBLEMS:. Under each header, list "
    "one bullet per line starting with '- '. End every bullet line with an "
    "evidence tag in the exact form ' [evidence: <speaker>|<span_id>]' "
    "naming the speaker and transcript span id that supports the "
    "statement, or ' [evidence: none]' if no single span supports it. "
    "Output ONLY the four sections; no extra commentary."
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


def test_build_request_carries_template_identity():
    req = build_minutes_request(supply_text="supply")
    assert req.template_id == TEMPLATE_ID
    assert req.template_sha256 == TEMPLATE_SHA256
    assert req.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE


def test_build_request_without_transcript_has_no_transcript_block():
    req = build_minutes_request(supply_text="supply")
    assert len(req.supplied_text) == 1
    assert TRANSCRIPT_SECTION_HEADER not in req.supplied_text[0]


def test_build_request_with_transcript_appends_transcript_block():
    req = build_minutes_request(supply_text="supply", resolved_transcript=RESOLVED_TRANSCRIPT)
    assert len(req.supplied_text) == 2
    transcript_part = req.supplied_text[1]
    assert transcript_part.startswith(TRANSCRIPT_SECTION_HEADER)
    assert "[seg-10|S1] We should approve the budget." in transcript_part
    assert "[seg-11|S2] Agreed, let's move on." in transcript_part


def test_build_request_is_deterministic():
    req_a = build_minutes_request(supply_text="supply", resolved_transcript=RESOLVED_TRANSCRIPT)
    req_b = build_minutes_request(supply_text="supply", resolved_transcript=RESOLVED_TRANSCRIPT)
    assert req_a == req_b


# ---------------------------------------------------------------------------
# parsing: strict success
# ---------------------------------------------------------------------------


def test_parse_strict_success_all_four_sections():
    result = parse_minutes_response(STRICT_MINUTES_REPLY)
    assert result.parse_mode == "strict"
    assert result.missing_sections == ()
    assert result.malformed_lines == ()
    assert [b.section for b in result.bullets] == ["abstract", "actions", "decisions", "problems"]
    assert [b.sentence_id for b in result.bullets] == ["abstract-0", "actions-0", "decisions-0", "problems-0"]


def test_parse_strict_evidence_tag_speaker_and_span():
    result = parse_minutes_response(STRICT_MINUTES_REPLY)
    abstract_bullet = result.bullets[0]
    assert abstract_bullet.text == "The team approved the budget."
    assert abstract_bullet.claimed_speaker == "S1"
    assert abstract_bullet.claimed_span_id == "seg-10"


def test_parse_strict_evidence_none_tag_gives_no_claim():
    result = parse_minutes_response(STRICT_MINUTES_REPLY)
    actions_bullet = result.bullets[1]
    assert actions_bullet.text == "Follow up with legal."
    assert actions_bullet.claimed_speaker is None
    assert actions_bullet.claimed_span_id is None


def test_multiple_bullets_in_one_section_get_increasing_sentence_ids():
    raw = (
        "ABSTRACT:\n"
        "- First point. [evidence: none]\n"
        "- Second point. [evidence: none]\n"
        "ACTIONS:\n"
        "- An action. [evidence: none]\n"
        "DECISIONS:\n"
        "- A decision. [evidence: none]\n"
        "PROBLEMS:\n"
        "- A problem. [evidence: none]\n"
    )
    result = parse_minutes_response(raw)
    assert result.parse_mode == "strict"
    abstract_ids = [b.sentence_id for b in result.bullets if b.section == "abstract"]
    assert abstract_ids == ["abstract-0", "abstract-1"]


# ---------------------------------------------------------------------------
# parsing: lenient degradation, missing sections, malformed lines as DATA
# ---------------------------------------------------------------------------


def test_parse_missing_section_is_lenient_and_reports_missing_sections():
    raw = "ABSTRACT:\n- Only an abstract. [evidence: none]\n"
    result = parse_minutes_response(raw)
    assert result.parse_mode == "lenient"
    assert result.missing_sections == ("actions", "decisions", "problems")
    assert len(result.bullets) == 1


def test_parse_content_before_first_header_is_malformed_not_raised():
    raw = "some preamble the model was not asked for\n" + STRICT_MINUTES_REPLY
    result = parse_minutes_response(raw)
    assert result.parse_mode == "lenient"
    assert "some preamble the model was not asked for" in result.malformed_lines
    assert len(result.bullets) == 4


_MINIMAL_TAIL_THREE_SECTIONS = (
    "ACTIONS:\n"
    "- a [evidence: none]\n"
    "DECISIONS:\n"
    "- d [evidence: none]\n"
    "PROBLEMS:\n"
    "- p [evidence: none]\n"
)


def test_parse_non_bullet_line_under_a_section_is_malformed_not_raised():
    raw = "ABSTRACT:\nnot a bullet line\n- A real bullet. [evidence: none]\n" + _MINIMAL_TAIL_THREE_SECTIONS
    result = parse_minutes_response(raw)
    assert result.parse_mode == "lenient"
    assert "not a bullet line" in result.malformed_lines
    assert len(result.bullets) == 4


def test_parse_evidence_tag_single_token_treated_as_speaker_only():
    raw = "ABSTRACT:\n- Some point. [evidence: S1]\n" + _MINIMAL_TAIL_THREE_SECTIONS
    result = parse_minutes_response(raw)
    bullet = result.bullets[0]
    assert bullet.claimed_speaker == "S1"
    assert bullet.claimed_span_id is None


def test_parse_bullet_with_no_evidence_tag_at_all_still_parses_text():
    raw = "ABSTRACT:\n- Some point with no tag.\n" + _MINIMAL_TAIL_THREE_SECTIONS
    result = parse_minutes_response(raw)
    bullet = result.bullets[0]
    assert bullet.text == "Some point with no tag."
    assert bullet.claimed_speaker is None
    assert bullet.claimed_span_id is None


def test_parse_totally_unparseable_text_fails_without_raising():
    result = parse_minutes_response("just some prose with no headers at all")
    assert result.parse_mode == "failed"
    assert result.bullets == ()
    assert result.missing_sections == MINUTES_SECTIONS


def test_parse_empty_text_fails_without_raising():
    result = parse_minutes_response("")
    assert result.parse_mode == "failed"
    assert result.bullets == ()
    assert result.malformed_lines == ()


# ---------------------------------------------------------------------------
# SAER-M-compatible projection
# ---------------------------------------------------------------------------


def test_speaker_attribution_predictions_matches_saer_m_input_shape():
    result = parse_minutes_response(STRICT_MINUTES_REPLY)
    predictions = result.speaker_attribution_predictions()
    assert predictions == (
        SpeakerAttributionPrediction(sentence_id="abstract-0", predicted_speaker="S1"),
        SpeakerAttributionPrediction(sentence_id="actions-0", predicted_speaker=None),
        SpeakerAttributionPrediction(sentence_id="decisions-0", predicted_speaker="S2"),
        SpeakerAttributionPrediction(sentence_id="problems-0", predicted_speaker=None),
    )


def test_minutes_parse_result_to_dict_shape():
    result = parse_minutes_response(STRICT_MINUTES_REPLY)
    d = result.to_dict()
    assert d["parse_mode"] == "strict"
    assert d["missing_sections"] == []
    assert d["malformed_lines"] == []
    assert len(d["bullets"]) == 4
    assert d["bullets"][0]["claimed_speaker"] == "S1"
