"""Tests for :mod:`meeting_minutes_agent.controller.loop`: the openJiuwen
episode workflow -- openjiuwen-gated (module docstring: importing it
without openjiuwen raises ImportError with an install hint, which
importorskip below turns into a clean skip for every test in this file).

Every test drives the REAL openJiuwen Pregel engine (``asyncio.run`` +
``flow.invoke``) against an injected fake client; zero live model contact
anywhere in this file."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

pytest.importorskip(
    "meeting_minutes_agent.controller.loop",
    reason="openjiuwen not installed; the episode workflow is exercised only in the pinned WSL "
    "research venv (zero-dependency gate: never a pyproject dependency)",
)

from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.chunking.planner import build_chunk_plan
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.transport import ModelResponse, RequestAttempt
from meeting_minutes_agent.controller.loop import (
    DISPATCH_LOG_KEY,
    EpisodeLoopError,
    EpisodeLoopState,
    ExecuteViaFrozenCore,
    run_episode_workflow,
)
from meeting_minutes_agent.controller.tasks import TaskKind, TaskQueue
from meeting_minutes_agent.glossary.arms import ArmKind
from meeting_minutes_agent.state.episode import EpisodeState
from meeting_minutes_agent.supply.config import SupplyArmConfig

SEGMENTS = (
    Segment(id="seg-0", speaker="S1", start=0.0, end=5.0, text="Let's get started with the budget review."),
    Segment(id="seg-1", speaker="S2", start=5.0, end=10.0, text="I'm Jane Smith from finance."),
)


class _FakeClient:
    """Returns REAL :class:`~meeting_minutes_agent.client.transport.ModelResponse`
    objects (not a duck-typed stand-in) so :class:`~meeting_minutes_agent.
    client.receipts.FlightReceipt.record` (via the harness's recording
    wrapper) works unmodified -- mirrors this repository's own client tests'
    discipline of using real dependency-free dataclasses wherever possible.

    ``budget``, when given, is reserved against on every call -- exactly
    what a real :class:`~meeting_minutes_agent.client.transport.
    LlamaServerTransport` does before every transport call
    (``EpisodeLoopState.should_continue``'s own docstring: "real
    reservation is the injected client's own responsibility"). Tests that
    exercise budget exhaustion MUST pass the SAME ``CallBudget`` instance
    the loop state itself holds, or the pre-check has nothing real to read."""

    def __init__(self, replies: dict[str, str] | None = None, budget: CallBudget | None = None):
        self.calls: list[dict[str, object]] = []
        self._replies = replies or {}
        self._budget = budget

    def request(
        self,
        *,
        request_id,
        task_instruction,
        audio_path,
        audio_seconds,
        supplied_text=(),
        decoding_params=None,
    ) -> ModelResponse:
        if self._budget is not None:
            self._budget.reserve(audio_seconds)
        self.calls.append(
            {
                "request_id": request_id,
                "task_instruction": task_instruction,
                "audio_path": audio_path,
                "audio_seconds": audio_seconds,
                "supplied_text": supplied_text,
            }
        )
        text = self._reply_for(request_id)
        attempt = RequestAttempt(
            request_id=request_id,
            retry_of=None,
            attempt_number=1,
            started_at="2026-08-18T00:00:00+00:00",
            latency_seconds=0.001,
            outcome="ok",
            error=None,
            audio_seconds=audio_seconds,
        )
        return ModelResponse(request_id=request_id, text=text, usage={"prompt_tokens": 1}, attempts=(attempt,))

    def _reply_for(self, request_id: str) -> str:
        for key, text in self._replies.items():
            if key in request_id:
                return text
        if "transcribe" in request_id:
            return "S1|Let's get started with the budget review.\nS2|I'm Jane Smith from finance.\n"
        if "summarize" in request_id:
            return (
                "ABSTRACT:\n- The team reviewed the budget. [evidence: S1|c0000-s0000]\n"
                "ACTIONS:\n- Follow up with finance. [evidence: S2|c0000-s0001]\n"
                "DECISIONS:\n- Approve the plan. [evidence: none]\n"
                "PROBLEMS:\n- None identified. [evidence: none]\n"
            )
        return ""


def _audio_resolver(tmp_path):
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"RIFF....WAVEfmt ")

    def resolve(chunk):
        return audio_file, max(chunk.end - chunk.start, 1.0)

    return resolve


def _fresh_state(tmp_path, *, max_calls=50, max_audio_seconds=36000.0, max_iterations=None) -> EpisodeLoopState:
    plan = build_chunk_plan(SEGMENTS, meeting_id="m1", window_cap_s=3600.0)
    task_queue = TaskQueue()
    for chunk in plan.chunks:
        task_queue = task_queue.push(TaskKind.TRANSCRIBE_SPAN, chunk.index)
    if plan.chunks:
        last_index = plan.chunks[-1].index
        task_queue = task_queue.push(TaskKind.SUMMARIZE_SECTION, last_index)
        task_queue = task_queue.push(TaskKind.RESOLVE_LEDGER, last_index)
    budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    return EpisodeLoopState(
        meeting_id="m1",
        chunk_plan=plan,
        supply_arm=SupplyArmConfig(),
        glossary_arm=ArmKind.GATED,
        decoding_params={},
        audio_chunk_resolver=_audio_resolver(tmp_path),
        budget=budget,
        max_iterations=max_iterations if max_iterations is not None else len(plan.chunks) + 10,
        task_queue=task_queue,
        episode_state=EpisodeState(),
    )


# ---------------------------------------------------------------------------
# EpisodeLoopState.should_continue -- the FuncCondition callable
# ---------------------------------------------------------------------------


class TestShouldContinue:
    def test_empty_queue_stops(self, tmp_path):
        state = _fresh_state(tmp_path)
        state.task_queue = TaskQueue()
        assert state.should_continue() is False

    def test_non_empty_queue_continues(self, tmp_path):
        state = _fresh_state(tmp_path)
        assert state.should_continue() is True

    def test_runaway_flags_and_stops(self, tmp_path):
        state = _fresh_state(tmp_path, max_iterations=0)
        assert state.should_continue() is False
        assert state.runaway is True

    def test_budget_call_cap_stops_before_a_transcribe_or_summarize_task(self, tmp_path):
        # max_calls=1, one call already reserved -> the next transcribe/
        # summarize task would cross the cap (BudgetLimits itself refuses a
        # non-positive max_calls, so exhaustion is simulated by pre-reserving
        # the one call this budget allows, not by an unreachable 0 cap).
        state = _fresh_state(tmp_path, max_calls=1, max_audio_seconds=36000.0)
        state.budget.reserve(1.0)
        assert state.should_continue() is False
        assert state.budget_exhausted is True

    def test_resolve_ledger_never_needs_budget_headroom(self, tmp_path):
        state = _fresh_state(tmp_path, max_calls=1)
        state.budget.reserve(1.0)  # the one call this budget allows, already spent
        state.task_queue = TaskQueue().push(TaskKind.RESOLVE_LEDGER, 0)
        assert state.should_continue() is True
        assert state.budget_exhausted is False


# ---------------------------------------------------------------------------
# ExecuteViaFrozenCore: linear-chain invariant defense
# ---------------------------------------------------------------------------


def test_execute_raises_if_no_unit_was_staged(tmp_path):
    state = _fresh_state(tmp_path)
    client = _FakeClient()
    from meeting_minutes_agent.client.component import FrozenMeetingCore

    node = ExecuteViaFrozenCore(FrozenMeetingCore(client), state)

    async def run():
        await node.invoke({}, _FakeSession(), None)

    with pytest.raises(EpisodeLoopError, match="NextTask must run first"):
        asyncio.run(run())


class _FakeSession:
    def __init__(self):
        self._g = {}

    def get_global_state(self, key=None):
        return self._g.get(key)

    def update_global_state(self, data):
        self._g.update(data)


# ---------------------------------------------------------------------------
# run_episode_workflow: full graph execution
# ---------------------------------------------------------------------------


class TestRunEpisodeWorkflow:
    def test_dispatches_every_task_in_priority_order(self, tmp_path):
        state = _fresh_state(tmp_path)
        client = _FakeClient(budget=state.budget)
        run_episode_workflow(state, client)
        assert [entry["task_kind"] for entry in state.dispatch_log] == [
            "transcribe_span",
            "summarize_section",
            "resolve_ledger",
        ]
        assert state.task_queue.is_empty()
        assert state.iteration == 3

    def test_resolve_ledger_never_calls_the_client(self, tmp_path):
        state = _fresh_state(tmp_path)
        client = _FakeClient(budget=state.budget)
        run_episode_workflow(state, client)
        assert client.calls == [
            call for call in client.calls if "ledger" not in call["request_id"]
        ]
        assert len(client.calls) == 2  # transcribe + summarize only

    def test_dispatch_log_omits_response_hash_for_the_local_fold_task(self, tmp_path):
        # None-deletion discipline made explicit at OUR OWN dict-building
        # layer (module docstring): a task that made no core call never
        # gets a response_text_sha256 key at all.
        state = _fresh_state(tmp_path)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        by_kind = {entry["task_kind"]: entry for entry in state.dispatch_log}
        assert "response_text_sha256" not in by_kind["resolve_ledger"]
        assert "response_text_sha256" in by_kind["transcribe_span"]
        assert "response_text_sha256" in by_kind["summarize_section"]

    def test_final_episode_state_reflects_the_folded_transcript_and_ledger(self, tmp_path):
        state = _fresh_state(tmp_path)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        assert [s.text for s in state.resolved_segments] == [
            "Let's get started with the budget review.",
            "I'm Jane Smith from finance.",
        ]
        binding = state.episode_state.resolve_speaker("S2")
        assert binding is not None and binding.roster_name == "Jane Smith"
        # The summarize_section fake reply carries both an ACTIONS and a
        # DECISIONS bullet; resolve_ledger folds BOTH sections, not just
        # actions (dispatcher.py's _LEDGER_SECTIONS covers both kinds).
        assert [e.text for e in state.episode_state.active_ledger_entries()] == [
            "Follow up with finance.",
            "Approve the plan.",
        ]
        assert len(state.minutes_parses) == 1

    def test_dispatch_log_is_mirrored_into_session_global_state(self, tmp_path, monkeypatch):
        # Verify the "two homes" claim directly by spying on the per-node
        # Session class itself (the object components actually call
        # .update_global_state on) rather than on whatever
        # create_workflow_session returns at the top level -- the two are
        # not guaranteed to be the same object/type.
        import openjiuwen.core.session.node as session_node_mod

        writes: list[dict[str, object]] = []
        original_update = session_node_mod.Session.update_global_state

        def spy_update(self, data):
            if DISPATCH_LOG_KEY in data:
                writes.append(list(data[DISPATCH_LOG_KEY]))
            return original_update(self, data)

        monkeypatch.setattr(session_node_mod.Session, "update_global_state", spy_update)
        state = _fresh_state(tmp_path)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        assert writes  # at least one write happened
        assert writes[-1] == state.dispatch_log  # the final write matches the mirrored Python state

    def test_audio_chunk_resolver_is_called_with_the_dispatched_chunk(self, tmp_path):
        seen_chunks = []
        state = _fresh_state(tmp_path)
        audio_file = tmp_path / "clip.wav"
        audio_file.write_bytes(b"RIFF....WAVEfmt ")

        def resolver(chunk):
            seen_chunks.append(chunk.index)
            return audio_file, 5.0

        state.audio_chunk_resolver = resolver
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        assert seen_chunks == [0, 0]  # transcribe(chunk 0), summarize(chunk 0)

    def test_runaway_raises_episode_loop_error(self, tmp_path):
        state = _fresh_state(tmp_path, max_iterations=0)
        with pytest.raises(EpisodeLoopError, match="runaway"):
            run_episode_workflow(state, _FakeClient(budget=state.budget))

    def test_budget_exhaustion_stops_gracefully_without_raising(self, tmp_path):
        # Exactly one call's worth of budget: only the transcribe_span task
        # (the first, highest-priority task) should run; summarize_section
        # would need a second call and is refused by should_continue's own
        # pre-check before ever reaching the client.
        state = _fresh_state(tmp_path, max_calls=1)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        assert state.budget_exhausted is True
        assert [entry["task_kind"] for entry in state.dispatch_log] == ["transcribe_span"]
        assert not state.task_queue.is_empty()  # summarize/resolve_ledger never ran


# ---------------------------------------------------------------------------
# Determinism: 5 fresh runs -> identical fingerprint (the SAEA pattern)
# ---------------------------------------------------------------------------


def _fingerprint(state: EpisodeLoopState) -> dict[str, object]:
    return {
        "episode_state_content_hash": state.episode_state.content_hash(),
        "resolved_segments": tuple((s.id, s.speaker, s.start, s.end, s.text) for s in state.resolved_segments),
        "minutes_bullets": tuple(
            tuple(b.to_dict() for b in parse.bullets) for parse in state.minutes_parses
        ),
        "dispatch_log": tuple(dict(entry) for entry in state.dispatch_log),
    }


def test_five_fresh_runs_produce_an_identical_fingerprint(tmp_path):
    fingerprints = []
    for i in range(5):
        run_dir = tmp_path / f"run{i}"
        run_dir.mkdir()
        state = _fresh_state(run_dir)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        fingerprints.append(_fingerprint(state))
    assert all(fp == fingerprints[0] for fp in fingerprints)
    # sanity: the fingerprint is not trivially empty
    assert fingerprints[0]["resolved_segments"]
    assert fingerprints[0]["dispatch_log"]


def test_five_fresh_runs_hash_identically_via_sha256_of_the_full_fingerprint(tmp_path):
    # A stronger, single-number version of the same claim: hash the whole
    # fingerprint's canonical repr and compare digests across 5 runs.
    digests = set()
    for i in range(5):
        run_dir = tmp_path / f"h{i}"
        run_dir.mkdir()
        state = _fresh_state(run_dir)
        state.audio_chunk_resolver = _audio_resolver(run_dir)
        run_episode_workflow(state, _FakeClient(budget=state.budget))
        digest = hashlib.sha256(repr(_fingerprint(state)).encode("utf-8")).hexdigest()
        digests.add(digest)
    assert len(digests) == 1
