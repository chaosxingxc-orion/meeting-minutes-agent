"""Tests for :mod:`meeting_minutes_agent.probes.g1_scoring`: hypothesis-
stream construction (real-timed positional turn alignment for attribution
arms, single-stream untimed for transcribe-only arms), the ORC state-space
guard reused from ``pprompt_scoring``, per-(arm, meeting)/pooled
aggregation, SAER-M scoreability, the reimplemented upstream QA scorer, and
the per-meeting-clustered paired bootstrap deployment-gap arithmetic on
synthetic per-meeting scores."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.slicer import SliceTurnEntry
from meeting_minutes_agent.corpora.nxt.models import EvidenceLink
from meeting_minutes_agent.metrics.saer_m import SpeakerAttributionPrediction
from meeting_minutes_agent.metrics.timestamps import PerSpeakerSegment
from meeting_minutes_agent.probes import g1
from meeting_minutes_agent.probes.g1_scoring import (
    PPROMPT_NOISE_REFERENCE_CPWER,
    UNATTRIBUTED_SPEAKER,
    ArmMeetingScore,
    BootstrapError,
    DeploymentGapResult,
    OneShotOutputExistsError,
    QAExampleInput,
    SliceTranscribeScore,
    aggregate_arm_meeting,
    aggregate_pooled,
    arm_qa_report,
    assert_one_shot_output_dir,
    compute_deployment_gap,
    hypothesis_stream_from_slice_reply,
    is_capped_reply,
    meeting_saer_m,
    paired_cluster_bootstrap,
    score_transcribe_slice,
)


# ---------------------------------------------------------------------------
# hypothesis stream construction
# ---------------------------------------------------------------------------


class TestHypothesisStreamFromSliceReply:
    def test_attribution_arm_aligns_positionally_to_the_slice_turn_table(self):
        turns = (
            SliceTurnEntry(speaker="A", absolute_start=0.0, absolute_end=40.0, slice_offset_start=0.0, slice_offset_end=40.0),
            SliceTurnEntry(speaker="B", absolute_start=40.0, absolute_end=90.0, slice_offset_start=40.0, slice_offset_end=90.0),
        )
        reply = "A|hello world\nB|foo bar"
        hyp = hypothesis_stream_from_slice_reply(g1.ARM_Z_TURN, reply, turns, slice_start=0.0, slice_end=90.0)
        assert len(hyp) == 2
        assert hyp[0].start == 0.0 and hyp[0].end == 40.0 and hyp[0].real_timing is True
        assert hyp[1].start == 40.0 and hyp[1].end == 90.0 and hyp[1].real_timing is True

    def test_surplus_parsed_lines_fall_back_to_whole_slice_bounds_untimed(self):
        turns = (SliceTurnEntry(speaker="A", absolute_start=0.0, absolute_end=40.0, slice_offset_start=0.0, slice_offset_end=40.0),)
        reply = "A|first\nB|second\nC|third"
        hyp = hypothesis_stream_from_slice_reply(g1.ARM_Z_ORACLE, reply, turns, slice_start=0.0, slice_end=90.0)
        assert hyp[0].real_timing is True
        assert hyp[1].real_timing is False and hyp[1].start == 0.0 and hyp[1].end == 90.0
        assert hyp[2].real_timing is False

    def test_empty_turn_table_makes_everything_untimed(self):
        reply = "A|hello"
        hyp = hypothesis_stream_from_slice_reply(g1.ARM_Z_TURN, reply, (), slice_start=10.0, slice_end=20.0)
        assert hyp[0].real_timing is False and hyp[0].start == 10.0 and hyp[0].end == 20.0

    def test_transcribe_only_arm_is_one_untimed_placeholder_speaker_segment(self):
        hyp = hypothesis_stream_from_slice_reply(g1.ARM_Z_FREE, "the meeting started", (), slice_start=0.0, slice_end=90.0)
        assert len(hyp) == 1
        assert hyp[0].speaker == UNATTRIBUTED_SPEAKER
        assert hyp[0].text == "the meeting started"
        assert hyp[0].real_timing is False

    def test_transcribe_only_empty_reply_is_empty_stream(self):
        hyp = hypothesis_stream_from_slice_reply(g1.ARM_Z_NODIAR, "   \n  ", (), slice_start=0.0, slice_end=90.0)
        assert hyp == ()


# ---------------------------------------------------------------------------
# capped-reply detection
# ---------------------------------------------------------------------------


class TestIsCappedReply:
    def test_true_when_completion_tokens_equals_max_tokens(self):
        assert is_capped_reply({"completion_tokens": 1024}, max_tokens=1024) is True

    def test_false_when_under_the_cap(self):
        assert is_capped_reply({"completion_tokens": 200}, max_tokens=1024) is False

    def test_false_on_missing_usage_field(self):
        assert is_capped_reply({}, max_tokens=1024) is False


# ---------------------------------------------------------------------------
# per-slice scoring + the ORC guard (meeteval-backed)
# ---------------------------------------------------------------------------


class TestScoreTranscribeSlice:
    def setup_method(self):
        pytest.importorskip("meeteval")

    def test_empty_hypothesis_scores_worst_case_cp_wer_one(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
        score = score_transcribe_slice(g1.ARM_Z_TURN, "MTG1", 0, reference, "", (), slice_start=0.0, slice_end=90.0)
        assert score.hypothesis_empty is True
        assert score.cp_wer == 1.0
        assert score.n_hypothesis_segments == 0

    def test_perfect_transcription_scores_zero_cp_wer(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
        score = score_transcribe_slice(g1.ARM_Z_TURN, "MTG1", 0, reference, "A|hello world", (), slice_start=0.0, slice_end=90.0)
        assert score.cp_wer == pytest.approx(0.0)
        assert score.secondary_confusion_cost is not None

    def test_transcribe_only_arm_scores_against_a_single_stream(self):
        reference = (
            PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),
            PerSpeakerSegment(speaker="B", start=1.0, end=2.0, words="foo bar"),
        )
        score = score_transcribe_slice(g1.ARM_Z_FREE, "MTG1", 0, reference, "hello world foo bar", (), slice_start=0.0, slice_end=90.0)
        assert score.n_hypothesis_segments == 1
        assert 0.0 <= score.cp_wer <= 1.0

    def test_grammar_compliance_is_always_1_for_transcribe_only_arms(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="x"),)
        score = score_transcribe_slice(g1.ARM_Z_NODIAR, "MTG1", 0, reference, "anything goes here, no grammar", (), slice_start=0.0, slice_end=90.0)
        assert score.grammar_compliance == 1.0

    def test_malformed_lines_reduce_grammar_compliance_for_attribution_arms(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hi"),)
        score = score_transcribe_slice(g1.ARM_Z_TURN, "MTG1", 0, reference, "A|hi\nnot a valid line", (), slice_start=0.0, slice_end=90.0)
        assert score.grammar_compliance == pytest.approx(0.5)

    def test_capped_reply_is_disclosed(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hi"),)
        score = score_transcribe_slice(
            g1.ARM_Z_TURN, "MTG1", 0, reference, "A|hi", (), slice_start=0.0, slice_end=90.0,
            usage={"completion_tokens": 5}, request_max_tokens=5,
        )
        assert score.capped_reply is True

    def test_orc_state_space_guard_refuses_and_keeps_real_cp_wer(self):
        # Force the refusal path with a tiny injected cap -- never a huge
        # fixture: score_transcribe_slice's own orc_dp_bound_cap parameter
        # is the same injection seam pprompt_scoring's score_slice tests use.
        reference = (
            PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),
            PerSpeakerSegment(speaker="B", start=1.0, end=2.0, words="foo bar baz"),
        )
        score = score_transcribe_slice(
            g1.ARM_Z_TURN, "MTG1", 0, reference, "A|hello world\nB|foo bar baz", (), slice_start=0.0, slice_end=90.0,
            orc_dp_bound_cap=1.0,
        )
        assert score.orc_refusal is not None
        assert score.secondary_confusion_cost is None
        assert score.primary_confusion_cost is None
        assert 0.0 <= score.cp_wer <= 1.0  # cpWER is still real, never dropped

    def test_orc_refusal_never_fires_when_the_cap_is_generous(self):
        reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
        score = score_transcribe_slice(g1.ARM_Z_TURN, "MTG1", 0, reference, "A|hello world", (), slice_start=0.0, slice_end=90.0)
        assert score.orc_refusal is None
        assert score.secondary_confusion_cost is not None


# ---------------------------------------------------------------------------
# per-(arm, meeting) and pooled aggregation (pure arithmetic, hand-built)
# ---------------------------------------------------------------------------


def _slice_score(cp_wer, *, meeting_id="M1", secondary=0.0, primary=None, compliance=1.0, capped=False, refused=None) -> SliceTranscribeScore:
    return SliceTranscribeScore(
        arm=g1.ARM_Z_TURN, meeting_id=meeting_id, slice_index=0, cp_wer=cp_wer, secondary_confusion_cost=secondary,
        primary_confusion_cost=primary, grammar_compliance=compliance, n_reference_segments=1, n_hypothesis_segments=1,
        hypothesis_empty=False, capped_reply=capped, orc_refusal=refused,
    )


class TestAggregation:
    def test_arm_meeting_score_means(self):
        scores = [_slice_score(0.2), _slice_score(0.4)]
        agg = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", scores)
        assert agg.n_slices == 2
        assert agg.mean_cp_wer == pytest.approx(0.3)
        assert agg.mean_secondary_confusion_cost == pytest.approx(0.0)

    def test_confusion_refused_slices_are_excluded_from_the_mean_but_counted(self):
        scores = [_slice_score(0.2, secondary=0.1), _slice_score(0.4, secondary=None, refused="cap exceeded")]
        agg = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", scores)
        assert agg.n_confusion_refused == 1
        assert agg.mean_secondary_confusion_cost == pytest.approx(0.1)

    def test_mean_secondary_confusion_is_none_when_every_slice_is_refused(self):
        scores = [_slice_score(0.4, secondary=None, refused="x")]
        agg = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", scores)
        assert agg.mean_secondary_confusion_cost is None

    def test_capped_replies_are_counted(self):
        scores = [_slice_score(0.1, capped=True), _slice_score(0.1, capped=False)]
        agg = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", scores)
        assert agg.n_capped_replies == 1

    def test_empty_slice_list_raises(self):
        with pytest.raises(ValueError):
            aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", [])

    def test_mismatched_arm_or_meeting_raises(self):
        wrong = SliceTranscribeScore(
            arm=g1.ARM_Z_ORACLE, meeting_id="M1", slice_index=0, cp_wer=0.1, secondary_confusion_cost=0.0,
            primary_confusion_cost=None, grammar_compliance=1.0, n_reference_segments=1, n_hypothesis_segments=1,
            hypothesis_empty=False, capped_reply=False,
        )
        with pytest.raises(ValueError):
            aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", [wrong])

    def test_pooled_score_is_the_equal_weighted_mean_over_meetings(self):
        m1 = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", [_slice_score(0.2, meeting_id="M1")])
        m2 = aggregate_arm_meeting(
            g1.ARM_Z_TURN, "M2",
            [_slice_score(0.4, meeting_id="M2"), _slice_score(0.6, meeting_id="M2"), _slice_score(0.8, meeting_id="M2")],
        )
        pooled = aggregate_pooled(g1.ARM_Z_TURN, [m1, m2])
        # equal-weighted over meetings (0.2 and 0.6), never slice-weighted
        # over all four slices (which would be 0.5).
        assert pooled.mean_cp_wer == pytest.approx((0.2 + 0.6) / 2)
        assert pooled.n_meetings == 2
        assert pooled.total_slices == 4

    def test_pooled_rejects_a_mismatched_arm(self):
        m1 = aggregate_arm_meeting(g1.ARM_Z_TURN, "M1", [_slice_score(0.2)])
        with pytest.raises(ValueError):
            aggregate_pooled(g1.ARM_Z_ORACLE, [m1])


# ---------------------------------------------------------------------------
# SAER-M scoreability
# ---------------------------------------------------------------------------


class TestMeetingSaerM:
    def test_no_evidence_links_means_unscoreable(self):
        assert meeting_saer_m((), (SpeakerAttributionPrediction(sentence_id="s0", predicted_speaker="A"),)) is None

    def test_delegates_to_compute_saer_m_when_scoreable(self):
        link = EvidenceLink(
            id="l1", sentence_id="s0", section="abstract", sentence_text="x", da_ids=("d1",), speaker="A",
            start=0.0, end=1.0, text="x", word_ids=(),
        )
        report = meeting_saer_m((link,), (SpeakerAttributionPrediction(sentence_id="s0", predicted_speaker="A"),))
        assert report is not None
        assert report.n_scored == 1 and report.n_correct == 1


# ---------------------------------------------------------------------------
# the reimplemented upstream QA scorer
# ---------------------------------------------------------------------------


class TestArmQaReport:
    def test_exact_match_scores_perfectly(self):
        examples = [QAExampleInput(example_id="q1", reference_spans=("Friday",), prediction_spans=("Friday",))]
        report = arm_qa_report(examples)
        assert report.n_examples == 1
        assert report.upstream_meetingqa_macro_exact_match == pytest.approx(1.0)

    def test_abstention_on_unanswerable_scores_perfectly(self):
        examples = [QAExampleInput(example_id="q1", reference_spans=(), prediction_spans=())]
        report = arm_qa_report(examples)
        assert report.upstream_meetingqa_macro_f1 == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# the paired cluster bootstrap + deployment gap (pure stdlib arithmetic)
# ---------------------------------------------------------------------------


class TestPairedClusterBootstrap:
    def test_deterministic_for_the_same_seed(self):
        ids = ["m1", "m2", "m3"]
        values = {"m1": 1.0, "m2": 2.0, "m3": 3.0}
        stat = lambda sample: sum(values[m] for m in sample) / len(sample)
        r1 = paired_cluster_bootstrap(sample_ids=ids, statistic=stat, n_replicates=500, seed=42)
        r2 = paired_cluster_bootstrap(sample_ids=ids, statistic=stat, n_replicates=500, seed=42)
        assert r1.replicates == r2.replicates
        assert r1.sigma_hat == r2.sigma_hat
        assert r1.ci == r2.ci

    def test_point_estimate_is_the_unresampled_statistic(self):
        ids = ["m1", "m2"]
        values = {"m1": 1.0, "m2": 3.0}
        stat = lambda sample: sum(values[m] for m in sample) / len(sample)
        result = paired_cluster_bootstrap(sample_ids=ids, statistic=stat, n_replicates=100, seed=1)
        assert result.point_estimate == pytest.approx(2.0)

    def test_zero_variance_statistic_has_zero_sigma_and_a_degenerate_ci(self):
        ids = ["m1", "m2", "m3"]
        result = paired_cluster_bootstrap(sample_ids=ids, statistic=lambda sample: 5.0, n_replicates=200, seed=1)
        assert result.sigma_hat == pytest.approx(0.0)
        assert result.ci_low == pytest.approx(5.0)
        assert result.ci_high == pytest.approx(5.0)

    def test_empty_sample_ids_raises(self):
        with pytest.raises(BootstrapError):
            paired_cluster_bootstrap(sample_ids=[], statistic=lambda s: 0.0)

    def test_invalid_ci_level_raises(self):
        with pytest.raises(BootstrapError):
            paired_cluster_bootstrap(sample_ids=["m1"], statistic=lambda s: 0.0, ci_level=1.5)


class TestComputeDeploymentGap:
    def test_registered_seed_and_replicate_count(self):
        z_turn = {"m1": 0.4, "m2": 0.5}
        z_oracle = {"m1": 0.3, "m2": 0.3}
        result = compute_deployment_gap(z_turn, z_oracle, n_replicates=1000)
        assert result.gap.seed == 20260818
        assert result.noise_reference_cp_wer == PPROMPT_NOISE_REFERENCE_CPWER == 0.085

    def test_gap_point_estimate_is_the_mean_difference(self):
        z_turn = {"m1": 0.5, "m2": 0.7}
        z_oracle = {"m1": 0.2, "m2": 0.2}
        result = compute_deployment_gap(z_turn, z_oracle, n_replicates=100)
        assert result.gap.point_estimate == pytest.approx(((0.5 - 0.2) + (0.7 - 0.2)) / 2)

    def test_a_large_consistent_gap_excludes_zero(self):
        z_turn = {f"m{i}": 0.9 for i in range(10)}
        z_oracle = {f"m{i}": 0.1 for i in range(10)}
        result = compute_deployment_gap(z_turn, z_oracle, n_replicates=2000)
        assert result.gap.excludes_zero is True
        assert result.gap.ci_low > 0.0

    def test_no_gap_at_all_does_not_exclude_zero(self):
        z_turn = {f"m{i}": 0.5 for i in range(10)}
        z_oracle = {f"m{i}": 0.5 for i in range(10)}
        result = compute_deployment_gap(z_turn, z_oracle, n_replicates=500)
        assert result.gap.excludes_zero is False
        assert result.gap.ci_low <= 0.0 <= result.gap.ci_high

    def test_mismatched_meeting_sets_raise(self):
        with pytest.raises(BootstrapError):
            compute_deployment_gap({"m1": 0.1}, {"m2": 0.1})

    def test_returns_a_deployment_gap_result(self):
        result = compute_deployment_gap({"m1": 0.1}, {"m1": 0.2}, n_replicates=10)
        assert isinstance(result, DeploymentGapResult)
        assert result.to_dict()["gap"]["seed"] == 20260818


# ---------------------------------------------------------------------------
# one-shot idempotence guard
# ---------------------------------------------------------------------------


class TestOneShotOutputDir:
    def test_passes_on_an_empty_dir(self, tmp_path):
        assert_one_shot_output_dir(tmp_path)  # must not raise

    def test_refuses_when_verdict_json_already_exists(self, tmp_path):
        (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
        with pytest.raises(OneShotOutputExistsError):
            assert_one_shot_output_dir(tmp_path)

    def test_force_bypasses_the_refusal(self, tmp_path):
        (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
        assert_one_shot_output_dir(tmp_path, force=True)  # must not raise
