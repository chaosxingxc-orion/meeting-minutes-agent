"""Tests for :mod:`meeting_minutes_agent.controller.assembly`: the four-
section minutes artifact and the attributed-transcript artifact, both
content-hashed, plus the minutes artifact's ``metrics.saer_m``
compatibility."""

from __future__ import annotations

from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.controller.assembly import (
    build_attributed_transcript_artifact,
    build_minutes_artifact,
)
from meeting_minutes_agent.corpora.nxt.models import MINUTES_SECTIONS, EvidenceLink
from meeting_minutes_agent.heads.minutes import parse_minutes_response
from meeting_minutes_agent.metrics.saer_m import OUTCOME_CORRECT, SpeakerAttributionPrediction

STRICT_MINUTES_REPLY = (
    "ABSTRACT:\n"
    "- The team approved the budget. [evidence: S1|seg-10]\n"
    "ACTIONS:\n"
    "- Follow up with legal. [evidence: none]\n"
    "DECISIONS:\n"
    "- Ship v2 by Friday. [evidence: S2|seg-11]\n"
    "PROBLEMS:\n"
    "- None identified this chunk. [evidence: none]\n"
)


# ---------------------------------------------------------------------------
# build_minutes_artifact
# ---------------------------------------------------------------------------


class TestBuildMinutesArtifact:
    def test_folds_one_parse_into_sections_in_registered_order(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        artifact = build_minutes_artifact("meeting-1", [parse])
        assert tuple(artifact.sections) == MINUTES_SECTIONS
        assert [b.text for b in artifact.sections["abstract"]] == ["The team approved the budget."]
        assert [b.text for b in artifact.sections["actions"]] == ["Follow up with legal."]
        assert [b.text for b in artifact.sections["decisions"]] == ["Ship v2 by Friday."]
        assert [b.text for b in artifact.sections["problems"]] == ["None identified this chunk."]

    def test_bullets_returns_all_bullets_in_section_order(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        artifact = build_minutes_artifact("meeting-1", [parse])
        assert [b.section for b in artifact.bullets()] == ["abstract", "actions", "decisions", "problems"]

    def test_empty_parse_list_produces_an_empty_but_well_formed_artifact(self):
        artifact = build_minutes_artifact("meeting-1", [])
        assert artifact.bullets() == ()
        assert tuple(artifact.sections) == MINUTES_SECTIONS
        assert all(artifact.sections[s] == () for s in MINUTES_SECTIONS)

    def test_folds_multiple_parses_by_concatenation_per_section(self):
        parse_a = parse_minutes_response("ABSTRACT:\n- First. [evidence: none]\n")
        parse_b = parse_minutes_response("ABSTRACT:\n- Second. [evidence: none]\n")
        artifact = build_minutes_artifact("meeting-1", [parse_a, parse_b])
        assert [b.text for b in artifact.sections["abstract"]] == ["First.", "Second."]

    def test_content_hash_is_deterministic_for_identical_input(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        a = build_minutes_artifact("meeting-1", [parse])
        b = build_minutes_artifact("meeting-1", [parse])
        assert a.content_hash == b.content_hash

    def test_content_hash_differs_when_meeting_id_differs(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        a = build_minutes_artifact("meeting-1", [parse])
        b = build_minutes_artifact("meeting-2", [parse])
        assert a.content_hash != b.content_hash

    def test_content_hash_differs_when_bullets_differ(self):
        a = build_minutes_artifact("m", [parse_minutes_response("ABSTRACT:\n- A. [evidence: none]\n")])
        b = build_minutes_artifact("m", [parse_minutes_response("ABSTRACT:\n- B. [evidence: none]\n")])
        assert a.content_hash != b.content_hash

    def test_to_dict_round_trips_the_content_hash(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        artifact = build_minutes_artifact("meeting-1", [parse])
        assert artifact.to_dict()["content_hash"] == artifact.content_hash


class TestSpeakerAttributionPredictionProjection:
    def test_every_bullet_becomes_a_prediction_with_its_claimed_speaker(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        artifact = build_minutes_artifact("meeting-1", [parse])
        predictions = artifact.speaker_attribution_predictions
        assert (
            SpeakerAttributionPrediction(
                sentence_id="abstract-0", predicted_speaker="S1", text="The team approved the budget."
            )
            in predictions
        )
        assert (
            SpeakerAttributionPrediction(
                sentence_id="decisions-0", predicted_speaker="S2", text="Ship v2 by Friday."
            )
            in predictions
        )
        # a bullet with an explicit "[evidence: none]" tag claims no speaker
        assert (
            SpeakerAttributionPrediction(
                sentence_id="actions-0", predicted_speaker=None, text="Follow up with legal."
            )
            in predictions
        )

    def test_score_against_is_compute_saer_m_compatible(self):
        parse = parse_minutes_response(STRICT_MINUTES_REPLY)
        artifact = build_minutes_artifact("meeting-1", [parse])
        evidence_links = (
            EvidenceLink(
                id="el-1",
                sentence_id="abstract-0",
                section="abstract",
                sentence_text="The team approved the budget.",
                da_ids=("da-1",),
                speaker="S1",
                start=0.0,
                end=1.0,
                text="approved",
                word_ids=("w1",),
            ),
        )
        report = artifact.score_against(evidence_links)
        result = next(r for r in report.per_sentence if r.sentence_id == "abstract-0")
        assert result.outcome == OUTCOME_CORRECT


# ---------------------------------------------------------------------------
# build_attributed_transcript_artifact
# ---------------------------------------------------------------------------


class TestBuildAttributedTranscriptArtifact:
    SEGMENTS = (
        Segment(id="seg-0", speaker="S1", start=0.0, end=1.0, text="Hello."),
        Segment(id="seg-1", speaker="S2", start=1.0, end=2.0, text="Hi."),
    )

    def test_preserves_resolution_order_and_fields(self):
        artifact = build_attributed_transcript_artifact("meeting-1", self.SEGMENTS)
        assert artifact.segments == (
            {"id": "seg-0", "speaker": "S1", "start": 0.0, "end": 1.0, "text": "Hello."},
            {"id": "seg-1", "speaker": "S2", "start": 1.0, "end": 2.0, "text": "Hi."},
        )

    def test_empty_segments_produces_a_well_formed_artifact(self):
        artifact = build_attributed_transcript_artifact("meeting-1", ())
        assert artifact.segments == ()
        assert artifact.content_hash

    def test_content_hash_is_deterministic(self):
        a = build_attributed_transcript_artifact("meeting-1", self.SEGMENTS)
        b = build_attributed_transcript_artifact("meeting-1", self.SEGMENTS)
        assert a.content_hash == b.content_hash

    def test_content_hash_differs_when_segment_order_differs(self):
        a = build_attributed_transcript_artifact("meeting-1", self.SEGMENTS)
        b = build_attributed_transcript_artifact("meeting-1", tuple(reversed(self.SEGMENTS)))
        assert a.content_hash != b.content_hash

    def test_to_dict_round_trips_the_content_hash(self):
        artifact = build_attributed_transcript_artifact("meeting-1", self.SEGMENTS)
        assert artifact.to_dict()["content_hash"] == artifact.content_hash
