"""Tests for :mod:`meeting_minutes_agent.probes.g1`: the four registered
arm constructors -- T1-A1 prompt-form locking, per-arm slice-plan provenance
validation, minutes/qa anchoring, the seeded QA cap, and Z-nodiar's
fail-closed VAD-supplement consumption."""

from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.chunking.leakage import BoundaryProvenance
from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.chunking.slicer import Slice, SlicePlan, SlicePlanMode, SliceTurnEntry
from meeting_minutes_agent.heads.transcribe_attribute import (
    SYSTEM_INSTRUCTION_TEMPLATE,
    TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE,
)
from meeting_minutes_agent.probes import g1


def _slice(index: int, start: float, end: float, *, turns=()) -> Slice:
    return Slice(index=index, start=start, end=end, vad_snap_applied=False, turns=turns)


def _plan(
    meeting_id: str, mode: SlicePlanMode, turn_provenance, slices: tuple[Slice, ...], *, total_duration_s: float | None = None
) -> SlicePlan:
    return SlicePlan(
        meeting_id=meeting_id,
        mode=mode,
        turn_provenance=turn_provenance,
        total_duration_s=total_duration_s if total_duration_s is not None else (slices[-1].end if slices else 0.0),
        slices=slices,
        content_hash="deadbeef",
    )


def _tool_plan(meeting_id: str = "MTG1") -> SlicePlan:
    turns0 = (
        SliceTurnEntry(speaker="A", absolute_start=0.0, absolute_end=40.0, slice_offset_start=0.0, slice_offset_end=40.0),
        SliceTurnEntry(speaker="B", absolute_start=40.0, absolute_end=90.0, slice_offset_start=40.0, slice_offset_end=90.0),
    )
    turns1 = (
        SliceTurnEntry(speaker="A", absolute_start=90.0, absolute_end=150.0, slice_offset_start=0.0, slice_offset_end=60.0),
    )
    return _plan(
        meeting_id, SlicePlanMode.TURN_AWARE, BoundaryProvenance.TOOL_DIAR,
        (_slice(0, 0.0, 90.0, turns=turns0), _slice(1, 90.0, 150.0, turns=turns1)),
    )


def _oracle_plan(meeting_id: str = "MTG1") -> SlicePlan:
    turns0 = (
        SliceTurnEntry(speaker="A", absolute_start=0.0, absolute_end=45.0, slice_offset_start=0.0, slice_offset_end=45.0),
    )
    return _plan(meeting_id, SlicePlanMode.TURN_AWARE, BoundaryProvenance.ORACLE_TURN, (_slice(0, 0.0, 90.0, turns=turns0),))


def _vad_plan(meeting_id: str = "MTG1") -> SlicePlan:
    return _plan(meeting_id, SlicePlanMode.VAD, None, (_slice(0, 0.0, 90.0),))


# ---------------------------------------------------------------------------
# T1-A1 prompt-form locking
# ---------------------------------------------------------------------------


class TestT1A1Form:
    @pytest.mark.parametrize("arm", [g1.ARM_Z_TURN, g1.ARM_Z_ORACLE])
    def test_attribution_arms_use_the_bare_transcribe_attribute_instruction(self, arm):
        request = g1.build_transcribe_request_for_arm(arm)
        assert request.task_instruction == SYSTEM_INSTRUCTION_TEMPLATE
        assert request.supplied_text == ()
        g1.assert_t1_a1_form(request, attribution=True)

    @pytest.mark.parametrize("arm", [g1.ARM_Z_FREE, g1.ARM_Z_NODIAR])
    def test_transcribe_only_arms_use_the_bare_transcribe_only_instruction(self, arm):
        request = g1.build_transcribe_request_for_arm(arm)
        assert request.task_instruction == TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE
        assert request.supplied_text == ()
        g1.assert_t1_a1_form(request, attribution=False)

    def test_no_context_block_is_ever_present_on_any_arm(self):
        for arm in g1.ARMS:
            request = g1.build_transcribe_request_for_arm(arm)
            assert request.supplied_text == (), f"{arm} carries a context block; T1-A1 excludes one"

    def test_unknown_arm_raises(self):
        with pytest.raises(g1.G1Error):
            g1.build_transcribe_request_for_arm("Z-bogus")

    def test_assert_t1_a1_form_catches_a_smuggled_context_block(self):
        request = g1.build_transcribe_request_for_arm(g1.ARM_Z_TURN)
        from dataclasses import replace

        tampered = replace(request, supplied_text=("=== CONTEXT ===\nsomething",))
        with pytest.raises(g1.G1Error):
            g1.assert_t1_a1_form(tampered, attribution=True)


# ---------------------------------------------------------------------------
# transcribe requests: byte-identical form across slices, per-slice audio
# ---------------------------------------------------------------------------


class TestBuildTranscribeRequests:
    def test_z_turn_over_a_tool_diar_plan(self):
        plan = _tool_plan()
        specs = g1.build_transcribe_requests(g1.ARM_Z_TURN, "MTG1", plan, slice_dir_relative="derived/slices/tool")
        assert len(specs) == 2
        assert specs[0].request_id == "g1-Z-turn-MTG1-transcribe-slice0000"
        assert specs[0].audio_relpath == "derived/slices/tool/MTG1/MTG1-slice0000.wav"
        assert specs[0].audio_seconds == 90.0
        assert specs[1].slice_index == 1
        # Byte-identical template across every slice (T1-A1 renders once).
        assert specs[0].head_request.task_instruction == specs[1].head_request.task_instruction
        assert specs[0].head_request.supplied_text == specs[1].head_request.supplied_text == ()

    def test_z_free_carries_no_turn_metadata_and_uses_transcribe_only(self):
        plan = _tool_plan()  # "same tool-turn slices" (floors prereg SS3)
        specs = g1.build_transcribe_requests(g1.ARM_Z_FREE, "MTG1", plan, slice_dir_relative="derived/slices/tool")
        for spec in specs:
            assert spec.head_request.task_instruction == TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE
            assert spec.head_request.supplied_text == ()
            # No turn-table / grid content anywhere in the built request.
            assert "turn" not in spec.head_request.task_instruction.lower() or "attribut" not in spec.head_request.task_instruction.lower()

    def test_z_oracle_requires_oracle_turn_provenance(self):
        with pytest.raises(g1.G1Error):
            g1.build_transcribe_requests(g1.ARM_Z_ORACLE, "MTG1", _tool_plan(), slice_dir_relative="x")

    def test_z_turn_requires_tool_diar_provenance(self):
        with pytest.raises(g1.G1Error):
            g1.build_transcribe_requests(g1.ARM_Z_TURN, "MTG1", _oracle_plan(), slice_dir_relative="x")

    def test_z_nodiar_requires_vad_mode(self):
        with pytest.raises(g1.G1Error):
            g1.build_transcribe_requests(g1.ARM_Z_NODIAR, "MTG1", _tool_plan(), slice_dir_relative="x")

    def test_z_nodiar_over_a_vad_plan(self):
        specs = g1.build_transcribe_requests(g1.ARM_Z_NODIAR, "MTG1", _vad_plan(), slice_dir_relative="derived/slices/vad")
        assert len(specs) == 1
        assert specs[0].head_request.task_instruction == TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE


# ---------------------------------------------------------------------------
# minutes / qa (Z-turn / Z-oracle only), anchored on last/first slice
# ---------------------------------------------------------------------------


class TestMinutesAndQaArms:
    def test_minutes_is_refused_for_z_free_and_z_nodiar(self):
        with pytest.raises(g1.G1Error):
            g1.build_minutes_request_for_meeting(g1.ARM_Z_FREE, "MTG1", _tool_plan(), (), slice_dir_relative="x")

    def test_qa_is_refused_for_z_free_and_z_nodiar(self):
        with pytest.raises(g1.G1Error):
            g1.build_qa_requests_for_meeting(g1.ARM_Z_FREE, "MTG1", _tool_plan(), [_Q("q1")], slice_dir_relative="x")

    def test_minutes_anchors_on_the_last_slice(self):
        plan = _tool_plan()
        transcript = (Segment(id="s0", speaker="A", start=0.0, end=1.0, text="hello"),)
        spec = g1.build_minutes_request_for_meeting(g1.ARM_Z_TURN, "MTG1", plan, transcript, slice_dir_relative="derived/slices/tool")
        assert spec.kind == "minutes"
        assert spec.slice_index == plan.slices[-1].index
        assert spec.audio_relpath.endswith("MTG1-slice0001.wav")
        assert spec.head_request.supplied_text  # the transcript block is present (structural content, not "context")

    def test_qa_anchors_on_the_first_slice_shared_across_questions(self):
        plan = _oracle_plan()
        questions = [_Q("q1", "What time is it?"), _Q("q2", "Who spoke first?")]
        specs = g1.build_qa_requests_for_meeting(g1.ARM_Z_ORACLE, "MTG1", plan, questions, slice_dir_relative="derived/slices/oracle")
        assert len(specs) == 2
        assert {s.slice_index for s in specs} == {plan.slices[0].index}
        assert {s.audio_relpath for s in specs} == {specs[0].audio_relpath}
        assert specs[0].audio_relpath.endswith("MTG1-slice0000.wav")
        assert specs[0].question_id == "q1" and specs[1].question_id == "q2"

    def test_qa_requires_at_least_one_question(self):
        with pytest.raises(g1.G1Error):
            g1.build_qa_requests_for_meeting(g1.ARM_Z_TURN, "MTG1", _tool_plan(), [], slice_dir_relative="x")

    def test_minutes_requires_a_nonempty_plan(self):
        empty_plan = _plan("MTG1", SlicePlanMode.TURN_AWARE, BoundaryProvenance.TOOL_DIAR, ())
        with pytest.raises(g1.G1Error):
            g1.build_minutes_request_for_meeting(g1.ARM_Z_TURN, "MTG1", empty_plan, (), slice_dir_relative="x")


class _Q:
    def __init__(self, example_id: str, question: str = "question?"):
        self.example_id = example_id
        self.question = question


# ---------------------------------------------------------------------------
# QA cap seeding determinism
# ---------------------------------------------------------------------------


class TestQaCapSeeding:
    def test_cap_is_the_registered_n200_seed(self):
        assert g1.QA_CAP_N == 200
        assert g1.QA_CAP_SEED == 20260818

    def test_short_list_passes_through_unchanged(self):
        qs = [_Q(f"q{i}") for i in range(5)]
        assert g1.select_capped_qa_questions(qs) == tuple(qs)

    def test_cap_selects_exactly_n(self):
        qs = [_Q(f"q{i:04d}") for i in range(500)]
        selected = g1.select_capped_qa_questions(qs)
        assert len(selected) == g1.QA_CAP_N

    def test_deterministic_regardless_of_input_order(self):
        qs = [_Q(f"q{i:04d}") for i in range(500)]
        import random

        shuffled = list(qs)
        random.Random(1).shuffle(shuffled)
        assert g1.select_capped_qa_questions(qs) == g1.select_capped_qa_questions(shuffled)

    def test_selection_is_returned_in_sorted_id_order_not_shuffle_order(self):
        qs = [_Q(f"q{i:04d}") for i in range(500)]
        selected = g1.select_capped_qa_questions(qs)
        ids = [q.example_id for q in selected]
        assert ids == sorted(ids)

    def test_different_seed_yields_a_different_selection(self):
        qs = [_Q(f"q{i:04d}") for i in range(500)]
        a = g1.select_capped_qa_questions(qs, seed=1)
        b = g1.select_capped_qa_questions(qs, seed=2)
        assert a != b

    def test_cap_boundary_equal_to_pool_size_passes_through(self):
        qs = [_Q(f"q{i}") for i in range(200)]
        assert g1.select_capped_qa_questions(qs, cap=200) == tuple(sorted(qs, key=lambda q: q.example_id))


# ---------------------------------------------------------------------------
# Z-nodiar: fail-closed VAD supplement consumption
# ---------------------------------------------------------------------------


class TestVadSupplement:
    def test_missing_manifest_raises_fail_closed(self, tmp_path):
        with pytest.raises(g1.G1VadSupplementMissingError):
            g1.load_vad_slice_plan(tmp_path / "does-not-exist.json")

    def test_round_trips_a_real_slice_plan(self, tmp_path):
        plan = _vad_plan()
        path = tmp_path / "MTG1.json"
        path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
        loaded = g1.load_vad_slice_plan(path)
        assert loaded.meeting_id == plan.meeting_id
        assert loaded.mode == plan.mode
        assert loaded.turn_provenance is None
        assert len(loaded.slices) == len(plan.slices)
        assert loaded.slices[0].start == plan.slices[0].start
        assert loaded.slices[0].end == plan.slices[0].end

    def test_round_trip_preserves_turn_entries(self, tmp_path):
        plan = _oracle_plan()
        path = tmp_path / "MTG1.json"
        path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
        loaded = g1.load_vad_slice_plan(path)
        assert loaded.turn_provenance == BoundaryProvenance.ORACLE_TURN
        assert loaded.slices[0].turns[0].speaker == "A"
        assert loaded.slices[0].turns[0].absolute_end == 45.0

    def test_runner_refuses_z_nodiar_over_a_missing_supplement_end_to_end(self, tmp_path):
        # Simulates the campaign runner's own resolve_slice_plan seam.
        missing_dir = tmp_path / "vad-manifests"
        with pytest.raises(g1.G1VadSupplementMissingError):
            g1.load_vad_slice_plan(missing_dir / "MTG1.json")


# ---------------------------------------------------------------------------
# slice_filename convention
# ---------------------------------------------------------------------------


def test_slice_filename_matches_materialize_slice_plan_convention():
    assert g1.slice_filename("ES2011a", 7) == "ES2011a-slice0007.wav"
