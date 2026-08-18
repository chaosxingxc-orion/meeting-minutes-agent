"""Tests for :mod:`meeting_minutes_agent.controller.dispatcher`: pure-logic
dispatch (build a request) and fold (parse a response back into
``EpisodeState``), plus the self-introduction miner. No openjiuwen, no
model contact -- every response text here is hand-written."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.chunking.planner import build_chunk_plan
from meeting_minutes_agent.controller.dispatcher import (
    GLOSSARY_ARM_CONSTRUCTORS,
    TaskDispatchNotImplementedError,
    build_dispatch_unit,
    find_self_introduction,
    fold_dispatch_result,
)
from meeting_minutes_agent.controller.tasks import Task, TaskKind
from meeting_minutes_agent.glossary.arms import ArmKind
from meeting_minutes_agent.state.episode import EpisodeState
from meeting_minutes_agent.state.models import SpeakerEvidenceSource
from meeting_minutes_agent.supply.config import SupplyArmConfig

SEGMENTS = (
    Segment(id="seg-0", speaker="S1", start=0.0, end=10.0, text="Let's begin the review."),
    Segment(id="seg-1", speaker="S2", start=10.0, end=20.0, text="Sounds good."),
)


def _chunk_plan(max_chunk_s: float = 3600.0):
    return build_chunk_plan(SEGMENTS, meeting_id="m1", target_chunk_s=max_chunk_s, max_chunk_s=max_chunk_s)


def _task(kind: TaskKind, chunk_index: int = 0, priority: int = 0, seq: int = 0) -> Task:
    return Task(kind=kind, chunk_index=chunk_index, priority=priority, seq=seq)


# ---------------------------------------------------------------------------
# build_dispatch_unit
# ---------------------------------------------------------------------------


class TestBuildDispatchUnitTranscribeSpan:
    def test_builds_a_head_request_with_supply_text_and_span_context(self):
        plan = _chunk_plan()
        unit = build_dispatch_unit(
            _task(TaskKind.TRANSCRIBE_SPAN),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=SEGMENTS,
        )
        assert unit.requires_core_call is True
        assert unit.fold_kind == "transcribe_attribute"
        assert unit.chunk is plan.chunks[0]
        assert unit.request_id == "chunk0000-transcribe"
        assert unit.head_request is not None
        assert "Let's begin the review." in "\n".join(unit.head_request.supplied_text)

    def test_out_of_range_chunk_index_raises(self):
        plan = _chunk_plan()
        with pytest.raises(ValueError, match="out of range"):
            build_dispatch_unit(
                _task(TaskKind.TRANSCRIBE_SPAN, chunk_index=99),
                episode_state=EpisodeState(),
                chunk_plan=plan,
                resolved_segments=(),
            )

    def test_decoding_params_are_forwarded(self):
        plan = _chunk_plan()
        unit = build_dispatch_unit(
            _task(TaskKind.TRANSCRIBE_SPAN),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=(),
            decoding_params={"temperature": 0.1},
        )
        assert unit.head_request.decoding_params == {"temperature": 0.1}


class TestBuildDispatchUnitSummarizeSection:
    def test_builds_a_minutes_head_request_over_the_resolved_transcript(self):
        plan = _chunk_plan()
        unit = build_dispatch_unit(
            _task(TaskKind.SUMMARIZE_SECTION),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=SEGMENTS,
        )
        assert unit.requires_core_call is True
        assert unit.fold_kind == "minutes"
        assert unit.chunk is plan.chunks[0]
        assert unit.request_id == "chunk0000-summarize"
        assert any("seg-0" in part for part in unit.head_request.supplied_text)


class TestBuildDispatchUnitResolveLedger:
    def test_is_a_local_fold_with_no_core_call(self):
        unit = build_dispatch_unit(
            _task(TaskKind.RESOLVE_LEDGER),
            episode_state=EpisodeState(),
            chunk_plan=_chunk_plan(),
            resolved_segments=(),
        )
        assert unit.requires_core_call is False
        assert unit.fold_kind == "ledger_local"
        assert unit.head_request is None
        assert unit.chunk is None
        assert unit.request_id == "chunk0000-ledger"


class TestBuildDispatchUnitHonestStubs:
    @pytest.mark.parametrize("kind", [TaskKind.RE_LISTEN, TaskKind.ANSWER_QUESTION])
    def test_declared_but_unbuilt_kinds_raise_named_precondition(self, kind):
        with pytest.raises(TaskDispatchNotImplementedError, match=kind.value):
            build_dispatch_unit(
                _task(kind),
                episode_state=EpisodeState(),
                chunk_plan=_chunk_plan(),
                resolved_segments=(),
            )


# ---------------------------------------------------------------------------
# self-introduction mining
# ---------------------------------------------------------------------------


class TestFindSelfIntroduction:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("I'm Jane Smith from finance.", "Jane Smith"),
            ("I am John Doe, the project lead.", "John Doe"),
            ("My name is Alice.", "Alice"),
            ("this is Bob Carter speaking.", "Bob Carter"),
            ("THIS IS Dana.", "Dana"),  # trigger phrase case-insensitive
        ],
    )
    def test_recognizes_common_self_introduction_phrasings(self, text, expected):
        assert find_self_introduction(text) == expected

    def test_no_match_returns_none(self):
        assert find_self_introduction("Let's move to the next agenda item.") is None

    def test_case_insensitive_trigger_never_loosens_the_name_capture(self):
        # "I'm not sure" must NOT be read as a self-introduction of "Not" --
        # the trigger phrase is case-insensitive but the name capture still
        # requires a genuine capital letter (dispatcher.py docstring).
        assert find_self_introduction("I'm not sure about the budget.") is None

    def test_empty_string_returns_none(self):
        assert find_self_introduction("") is None


# ---------------------------------------------------------------------------
# fold_dispatch_result: transcribe_attribute
# ---------------------------------------------------------------------------


class TestFoldTranscribeSpan:
    def _unit(self, plan):
        return build_dispatch_unit(
            _task(TaskKind.TRANSCRIBE_SPAN),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=(),
        )

    def test_parses_segments_and_assigns_synthetic_monotonic_timing(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        raw = "S1|First line here.\nS2|Second line here.\n"
        result = fold_dispatch_result(unit, raw, episode_state=EpisodeState())
        assert [s.text for s in result.new_resolved_segments] == ["First line here.", "Second line here."]
        seg0, seg1 = result.new_resolved_segments
        assert seg0.start == unit.chunk.start
        assert seg0.end == seg1.start
        assert seg1.end == unit.chunk.end
        assert seg0.id != seg1.id

    def test_no_segments_parsed_yields_no_new_resolved_segments(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        result = fold_dispatch_result(unit, "", episode_state=EpisodeState())
        assert result.new_resolved_segments == ()

    def test_self_introduction_binds_the_speaker_map(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        raw = "S2|Hi everyone, I'm Jane Smith from finance.\n"
        result = fold_dispatch_result(unit, raw, episode_state=EpisodeState())
        binding = result.episode_state.resolve_speaker("S2")
        assert binding is not None
        assert binding.roster_name == "Jane Smith"
        assert binding.source is SpeakerEvidenceSource.SELF_INTRODUCTION
        assert binding.chunk == 0

    def test_no_self_introduction_leaves_speaker_map_empty(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        raw = "S1|Let's proceed with the agenda.\n"
        result = fold_dispatch_result(unit, raw, episode_state=EpisodeState())
        assert result.episode_state.active_speaker_bindings() == ()

    def test_gated_arm_folds_a_repeated_term_into_the_glossary(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        raw = (
            "S1|Let's discuss Zephyr project status.\n"
            "S2|Yes the Zephyr project timeline looks fine.\n"
        )
        result = fold_dispatch_result(unit, raw, episode_state=EpisodeState(), glossary_arm=ArmKind.GATED)
        surfaces = {e.canonical_surface for e in result.episode_state.glossary}
        assert any("Zephyr" in s for s in surfaces)

    def test_no_carry_arm_discards_the_previous_chunks_glossary(self):
        plan = _chunk_plan()
        # Seed an episode state with an existing (pretend-accumulated) entry.
        first_unit = self._unit(plan)
        seeded = fold_dispatch_result(
            first_unit,
            "S1|Alpha Beta term appears here.\nS2|Alpha Beta term appears again.\n",
            episode_state=EpisodeState(),
            glossary_arm=ArmKind.GATED,
        ).episode_state
        assert len(seeded.glossary) >= 1

        second_unit = self._unit(plan)
        result = fold_dispatch_result(
            second_unit,
            "S1|Totally unrelated content with no repeats.\n",
            episode_state=seeded,
            glossary_arm=ArmKind.NO_CARRY,
        )
        # no_carry: this chunk's (empty, ungated) entries REPLACE the
        # accumulated glossary rather than merging into it.
        assert result.episode_state.glossary == ()

    def test_glossary_arm_selection_uses_the_registered_constructor_table(self):
        assert set(GLOSSARY_ARM_CONSTRUCTORS) == set(ArmKind)


# ---------------------------------------------------------------------------
# fold_dispatch_result: minutes / summarize_section
# ---------------------------------------------------------------------------


class TestFoldSummarizeSection:
    def _unit(self, plan):
        return build_dispatch_unit(
            _task(TaskKind.SUMMARIZE_SECTION),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=(),
        )

    def test_parses_minutes_and_extracts_only_action_decision_bullets_as_pending(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        raw = (
            "ABSTRACT:\n"
            "- The team met. [evidence: none]\n"
            "ACTIONS:\n"
            "- Send the report. [evidence: S1|seg-0]\n"
            "DECISIONS:\n"
            "- Approve the budget. [evidence: S2|seg-1]\n"
            "PROBLEMS:\n"
            "- None. [evidence: none]\n"
        )
        result = fold_dispatch_result(unit, raw, episode_state=EpisodeState())
        assert result.minutes_parse is not None
        assert {b.section for b in result.pending_ledger_bullets} == {"actions", "decisions"}
        assert len(result.pending_ledger_bullets) == 2

    def test_never_touches_the_glossary(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        state = EpisodeState()
        result = fold_dispatch_result(unit, "ABSTRACT:\n- ok [evidence: none]\n", episode_state=state)
        assert result.episode_state.glossary == state.glossary
        assert result.new_resolved_segments == ()


# ---------------------------------------------------------------------------
# fold_dispatch_result: resolve_ledger (local fold, no response text)
# ---------------------------------------------------------------------------


class TestFoldResolveLedger:
    def _unit(self, plan):
        return build_dispatch_unit(
            _task(TaskKind.RESOLVE_LEDGER),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=(),
        )

    def test_folds_pending_bullets_into_the_ledger(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        # Build real pending bullets the way build_minutes_request's parser
        # would (round-trip via the minutes head's own parser).
        summarize_unit = build_dispatch_unit(
            _task(TaskKind.SUMMARIZE_SECTION),
            episode_state=EpisodeState(),
            chunk_plan=plan,
            resolved_segments=(),
        )
        summarize_fold = fold_dispatch_result(
            summarize_unit,
            "ABSTRACT:\n- x [evidence: none]\nACTIONS:\n- Ship it. [evidence: S1|seg-0]\n"
            "DECISIONS:\n- Approve. [evidence: none]\nPROBLEMS:\n- none [evidence: none]\n",
            episode_state=EpisodeState(),
        )
        result = fold_dispatch_result(
            unit,
            "",  # resolve_ledger never reads raw_response_text
            episode_state=summarize_fold.episode_state,
            pending_ledger_bullets=summarize_fold.pending_ledger_bullets,
        )
        entries = result.episode_state.active_ledger_entries()
        assert {e.text for e in entries} == {"Ship it.", "Approve."}
        assert result.pending_ledger_bullets == ()  # consumed

    def test_no_pending_bullets_is_a_no_op(self):
        plan = _chunk_plan()
        unit = self._unit(plan)
        state = EpisodeState()
        result = fold_dispatch_result(unit, "", episode_state=state, pending_ledger_bullets=())
        assert result.episode_state.active_ledger_entries() == ()


# ---------------------------------------------------------------------------
# dispatch -> fold round trip (mission spec's own phrase)
# ---------------------------------------------------------------------------


def test_dispatch_then_fold_round_trip_for_transcribe_span():
    plan = _chunk_plan()
    state = EpisodeState()
    unit = build_dispatch_unit(
        _task(TaskKind.TRANSCRIBE_SPAN), episode_state=state, chunk_plan=plan, resolved_segments=()
    )
    # Simulate what a core reply to unit.head_request might look like.
    raw = "S1|Let's begin the review.\nS2|Sounds good.\n"
    result = fold_dispatch_result(unit, raw, episode_state=state)
    assert [s.text for s in result.new_resolved_segments] == ["Let's begin the review.", "Sounds good."]


def test_dispatch_then_fold_round_trip_for_summarize_then_resolve_ledger():
    plan = _chunk_plan()
    state = EpisodeState()
    summarize_unit = build_dispatch_unit(
        _task(TaskKind.SUMMARIZE_SECTION), episode_state=state, chunk_plan=plan, resolved_segments=()
    )
    summarize_fold = fold_dispatch_result(
        summarize_unit,
        "ABSTRACT:\n- x [evidence: none]\nACTIONS:\n- Follow up. [evidence: none]\n"
        "DECISIONS:\nPROBLEMS:\n- none identified [evidence: none]\n",
        episode_state=state,
    )
    ledger_unit = build_dispatch_unit(
        _task(TaskKind.RESOLVE_LEDGER),
        episode_state=summarize_fold.episode_state,
        chunk_plan=plan,
        resolved_segments=(),
        pending_ledger_bullets=summarize_fold.pending_ledger_bullets,
    )
    assert ledger_unit.requires_core_call is False
    ledger_fold = fold_dispatch_result(
        ledger_unit,
        "",
        episode_state=summarize_fold.episode_state,
        pending_ledger_bullets=summarize_fold.pending_ledger_bullets,
    )
    assert [e.text for e in ledger_fold.episode_state.active_ledger_entries()] == ["Follow up."]
