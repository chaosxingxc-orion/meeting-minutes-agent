"""Tests for :mod:`meeting_minutes_agent.harness.episode`: the light-off
entry point -- openjiuwen-gated (this module imports
:mod:`meeting_minutes_agent.controller.loop`, which raises ``ImportError``
with an install hint when openjiuwen is absent; importorskip below turns
that into a clean skip). Zero live model contact: every test drives an
injected fake client."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "meeting_minutes_agent.harness.episode",
    reason="openjiuwen not installed; the light-off harness is exercised only in the pinned WSL "
    "research venv (zero-dependency gate: never a pyproject dependency)",
)

from meeting_minutes_agent.chunking.models import Segment
from meeting_minutes_agent.chunking.slicer import Slice, SlicePlan, SlicePlanMode
from meeting_minutes_agent.client.budgets import CallBudget
from meeting_minutes_agent.client.receipts import ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import ModelResponse, RequestAttempt
from meeting_minutes_agent.glossary.arms import ArmKind
from meeting_minutes_agent.harness.episode import EpisodeHarnessConfig, run_episode
from meeting_minutes_agent.supply.config import SupplyArmConfig

SEGMENTS = (
    Segment(id="seg-0", speaker="S1", start=0.0, end=5.0, text="Let's get started with the budget review."),
    Segment(id="seg-1", speaker="S2", start=5.0, end=10.0, text="I'm Jane Smith from finance."),
)

SERVER_IDENTITY = ServerIdentity(
    base_url="http://localhost:8080",
    model_files=(ModelFileRef(path="model.gguf", sha256="a" * 64),),
)


class _FakeClient:
    """See ``tests/unit/controller/test_loop.py``'s own ``_FakeClient`` for
    the reasoning behind returning real
    :class:`~meeting_minutes_agent.client.transport.ModelResponse` objects
    and honoring an injected ``CallBudget``."""

    def __init__(self, budget: CallBudget | None = None):
        self.calls: list[str] = []
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
        self.calls.append(request_id)
        if "transcribe" in request_id:
            text = "S1|Let's get started with the budget review.\nS2|I'm Jane Smith from finance.\n"
        elif "summarize" in request_id:
            text = (
                "ABSTRACT:\n- The team reviewed the budget. [evidence: S1|c0000-s0000]\n"
                "ACTIONS:\n- Follow up with finance. [evidence: S2|c0000-s0001]\n"
                "DECISIONS:\n- Approve the plan. [evidence: none]\n"
                "PROBLEMS:\n- None identified. [evidence: none]\n"
            )
        else:
            text = ""
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


def _audio_resolver(tmp_path):
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"RIFF....WAVEfmt ")

    def resolve(chunk):
        return audio_file, max(chunk.end - chunk.start, 1.0)

    return resolve


def _run(tmp_path, *, config=None):
    """Run one episode against a fresh, budget-less
    :class:`_FakeClient` (the default caps are generous enough that no test
    in this file needs real enforcement -- ``run_episode`` constructs its
    OWN internal :class:`~meeting_minutes_agent.client.budgets.CallBudget`,
    invisible to a client built before the call, so true budget-exhaustion
    behaviour is exercised at the lower ``EpisodeLoopState`` layer instead,
    in ``tests/unit/controller/test_loop.py``, where the test explicitly
    shares one ``CallBudget`` object between the loop state and the fake
    client)."""

    client = _FakeClient()
    return run_episode(
        "meeting-1",
        SEGMENTS,
        audio_chunk_resolver=_audio_resolver(tmp_path),
        client=client,
        server_identity=SERVER_IDENTITY,
        config=config or EpisodeHarnessConfig(),
    ), client


# ---------------------------------------------------------------------------
# EpisodeHarnessConfig.validate()
# ---------------------------------------------------------------------------


class TestEpisodeHarnessConfigValidate:
    def test_default_config_validates(self):
        EpisodeHarnessConfig().validate()

    @pytest.mark.parametrize("max_calls", [0, -1, 1.5, True])
    def test_bad_max_calls_raises(self, max_calls):
        with pytest.raises(ValueError, match="max_calls"):
            EpisodeHarnessConfig(max_calls=max_calls).validate()

    @pytest.mark.parametrize("max_audio_seconds", [0, -1.0, float("inf"), float("nan")])
    def test_bad_max_audio_seconds_raises(self, max_audio_seconds):
        with pytest.raises(ValueError, match="max_audio_seconds"):
            EpisodeHarnessConfig(max_audio_seconds=max_audio_seconds).validate()

    def test_non_finite_workflow_timeout_raises(self):
        with pytest.raises(ValueError, match="workflow_timeout_seconds"):
            EpisodeHarnessConfig(workflow_timeout_seconds=float("nan")).validate()

    def test_negative_max_iterations_headroom_raises(self):
        with pytest.raises(ValueError, match="max_iterations_headroom"):
            EpisodeHarnessConfig(max_iterations_headroom=-1).validate()

    def test_invalid_supply_arm_cap_raises(self):
        with pytest.raises(ValueError):
            EpisodeHarnessConfig(supply_arm=SupplyArmConfig(max_glossary_terms=-1)).validate()


# ---------------------------------------------------------------------------
# run_episode: the light-off invocation
# ---------------------------------------------------------------------------


class TestRunEpisode:
    def test_produces_a_well_formed_result(self, tmp_path):
        result, client = _run(tmp_path)
        assert result.meeting_id == "meeting-1"
        assert len(result.chunk_plan.chunks) == 1
        assert client.calls == ["chunk0000-transcribe", "chunk0000-summarize"]

    def test_transcript_artifact_reflects_the_transcribed_segments(self, tmp_path):
        result, _ = _run(tmp_path)
        assert [s["text"] for s in result.transcript_artifact.segments] == [
            "Let's get started with the budget review.",
            "I'm Jane Smith from finance.",
        ]

    def test_minutes_artifact_reflects_the_summarize_reply(self, tmp_path):
        result, _ = _run(tmp_path)
        assert [b.text for b in result.minutes_artifact.sections["actions"]] == ["Follow up with finance."]
        assert [b.text for b in result.minutes_artifact.sections["decisions"]] == ["Approve the plan."]

    def test_episode_state_reflects_the_self_introduction_binding(self, tmp_path):
        result, _ = _run(tmp_path)
        binding = result.episode_state.resolve_speaker("S2")
        assert binding is not None
        assert binding.roster_name == "Jane Smith"

    def test_episode_state_ledger_reflects_the_resolve_ledger_fold(self, tmp_path):
        result, _ = _run(tmp_path)
        texts = {e.text for e in result.episode_state.active_ledger_entries()}
        assert texts == {"Follow up with finance.", "Approve the plan."}

    def test_flight_receipt_records_only_real_core_calls(self, tmp_path):
        result, _ = _run(tmp_path)
        ledger = result.flight_receipt.config["request_ledger"]
        assert len(ledger) == 2  # transcribe + summarize; resolve_ledger never calls the core
        assert {entry["response_of"] for entry in ledger} == {
            "chunk0000-transcribe",
            "chunk0000-summarize",
        }

    def test_budget_not_exhausted_under_generous_defaults(self, tmp_path):
        result, _ = _run(tmp_path)
        assert result.budget_exhausted is False

    def test_dispatch_log_covers_all_three_tasks(self, tmp_path):
        result, _ = _run(tmp_path)
        assert [entry["task_kind"] for entry in result.dispatch_log] == [
            "transcribe_span",
            "summarize_section",
            "resolve_ledger",
        ]

    def test_no_carry_glossary_arm_is_threaded_through(self, tmp_path):
        # Smoke-level check that the config's glossary_arm selection reaches
        # the loop (the arm-behaviour itself is unit-tested in
        # tests/unit/controller/test_dispatcher.py); a NO_CARRY arm over a
        # single-chunk episode is observably identical to GATED here (there
        # is no second chunk to discard), so this only proves the config
        # value is accepted and the episode still completes.
        config = EpisodeHarnessConfig(glossary_arm=ArmKind.NO_CARRY)
        result, _ = _run(tmp_path, config=config)
        assert result.budget_exhausted is False


class TestRunEpisodeEmptyMeeting:
    def test_zero_segments_produces_an_empty_but_well_formed_result(self, tmp_path):
        client = _FakeClient()
        result = run_episode(
            "empty-meeting",
            (),
            audio_chunk_resolver=_audio_resolver(tmp_path),
            client=client,
            server_identity=SERVER_IDENTITY,
        )
        assert result.chunk_plan.chunks == ()
        assert result.dispatch_log == ()
        assert client.calls == []
        assert result.minutes_artifact.bullets() == ()
        assert result.transcript_artifact.segments == ()


class TestRunEpisodeBudgetConfig:
    """``run_episode`` constructs its OWN internal ``CallBudget`` from
    ``config.max_calls``/``config.max_audio_seconds`` -- this class checks
    that plumbing reaches the flight receipt. The actual STOPPING behaviour
    under budget exhaustion (``EpisodeLoopState.should_continue``'s
    pre-check) is exercised at the lower layer, in
    ``tests/unit/controller/test_loop.py``, where the test shares one
    ``CallBudget`` object between the loop state and the fake client
    directly -- a fake client injected here has no way to reserve against
    the budget ``run_episode`` builds internally after the client already
    exists (a real production ``LlamaServerTransport`` is instead
    constructed together with its own ``CallBudget`` by whoever builds it)."""

    def test_max_calls_and_max_audio_seconds_reach_the_flight_receipt(self, tmp_path):
        result, _ = _run(tmp_path, config=EpisodeHarnessConfig(max_calls=7, max_audio_seconds=123.0))
        totals = result.flight_receipt.config["budget_totals"]
        assert totals["max_calls"] == 7
        assert totals["max_audio_seconds"] == 123.0

    def test_generous_caps_leave_the_episode_unexhausted(self, tmp_path):
        result, _ = _run(tmp_path, config=EpisodeHarnessConfig(max_calls=50, max_audio_seconds=36000.0))
        assert result.budget_exhausted is False
        assert [entry["task_kind"] for entry in result.dispatch_log] == [
            "transcribe_span",
            "summarize_section",
            "resolve_ledger",
        ]


# ---------------------------------------------------------------------------
# Light-off determinism: a fixture episode produces stable, hashed artifacts
# ---------------------------------------------------------------------------


class TestLightOffDeterminism:
    def test_two_fresh_runs_produce_identical_fingerprints(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        result_a, _ = _run(tmp_path / "a")
        result_b, _ = _run(tmp_path / "b")
        assert result_a.fingerprint() == result_b.fingerprint()

    def test_fingerprint_is_not_trivially_empty(self, tmp_path):
        result, _ = _run(tmp_path)
        fp = result.fingerprint()
        assert fp["dispatch_log"]
        assert fp["episode_state_content_hash"]
        assert fp["minutes_content_hash"]
        assert fp["transcript_content_hash"]
        assert fp["flight_receipt_config_hash"]

    def test_artifact_content_hashes_are_stable_across_rebuilds_of_the_same_input(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        result_a, _ = _run(tmp_path / "a")
        result_b, _ = _run(tmp_path / "b")
        assert result_a.minutes_artifact.content_hash == result_b.minutes_artifact.content_hash
        assert result_a.transcript_artifact.content_hash == result_b.transcript_artifact.content_hash
        assert result_a.episode_state.content_hash() == result_b.episode_state.content_hash()


# ---------------------------------------------------------------------------
# Per-slice dispatch (item 14): run_episode(slice_plan=...) threads one
# transcribe_span task per transport slice instead of one per chunk
# ---------------------------------------------------------------------------


def _two_slice_plan() -> SlicePlan:
    """A minimal, hand-built two-slice plan over SEGMENTS' [0, 10) span --
    the granularity analysis's own [60, 120] transport-slice bounds do not
    matter here (this module never calls build_vad_slice_plan/
    build_turn_aware_slice_plan, so no bound is enforced on this fixture);
    only the (index, start, end) shape run_episode actually reads."""

    return SlicePlan(
        meeting_id="meeting-1",
        mode=SlicePlanMode.VAD,
        turn_provenance=None,
        total_duration_s=10.0,
        slices=(
            Slice(index=0, start=0.0, end=5.0, vad_snap_applied=False),
            Slice(index=1, start=5.0, end=10.0, vad_snap_applied=False),
        ),
        content_hash="test-two-slice-plan",
    )


def _slice_resolver(tmp_path):
    slice_files = {0: tmp_path / "slice0.wav", 1: tmp_path / "slice1.wav"}
    for p in slice_files.values():
        p.write_bytes(b"RIFF....WAVEfmt ")

    def resolve(slice_index):
        return slice_files[slice_index], 5.0

    return resolve


class TestRunEpisodePerSliceDispatch:
    def test_dispatches_one_transcribe_span_task_per_slice(self, tmp_path):
        client = _FakeClient()
        result = run_episode(
            "meeting-1",
            SEGMENTS,
            audio_chunk_resolver=_audio_resolver(tmp_path),
            client=client,
            server_identity=SERVER_IDENTITY,
            slice_plan=_two_slice_plan(),
            audio_slice_resolver=_slice_resolver(tmp_path),
        )
        assert [entry["task_kind"] for entry in result.dispatch_log] == [
            "transcribe_span",
            "transcribe_span",
            "summarize_section",
            "resolve_ledger",
        ]
        assert client.calls == [
            "chunk0000-slice0000-transcribe",
            "chunk0000-slice0001-transcribe",
            "chunk0000-summarize",
        ]

    def test_max_iterations_is_recomputed_off_the_slice_count(self, tmp_path):
        # 2 slices + summarize + resolve_ledger = 4 real tasks. With
        # max_iterations_headroom=1 the episode needs max_iterations=5 to
        # finish without a false "runaway" -- the OLD (pre-item-14) formula
        # `len(chunk_plan.chunks) + 2 + headroom` would have computed
        # `1 + 2 + 1 = 4` here (one chunk, not two slices), exactly the
        # iteration count the 4th real task reaches, which
        # EpisodeLoopState.should_continue flags as a runaway (its
        # iteration-ceiling check runs before its queue-empty check) and
        # run_episode_workflow would raise instead of returning -- proving
        # `max_iterations` really is now derived from the SLICE count.
        client = _FakeClient()
        result = run_episode(
            "meeting-1",
            SEGMENTS,
            audio_chunk_resolver=_audio_resolver(tmp_path),
            client=client,
            server_identity=SERVER_IDENTITY,
            config=EpisodeHarnessConfig(max_iterations_headroom=1),
            slice_plan=_two_slice_plan(),
            audio_slice_resolver=_slice_resolver(tmp_path),
        )
        assert len(result.dispatch_log) == 4
        assert result.budget_exhausted is False

    def test_no_slice_plan_reproduces_the_pre_item14_one_task_per_chunk_behaviour(self, tmp_path):
        # Default (slice_plan=None) stays byte-for-byte identical to the
        # pre-item-14 shape -- same request ids as TestRunEpisode's own
        # test_produces_a_well_formed_result.
        result, client = _run(tmp_path)
        assert client.calls == ["chunk0000-transcribe", "chunk0000-summarize"]

    def test_slice_plan_without_a_resolver_raises(self, tmp_path):
        client = _FakeClient()
        with pytest.raises(ValueError, match="audio_slice_resolver is None"):
            run_episode(
                "meeting-1",
                SEGMENTS,
                audio_chunk_resolver=_audio_resolver(tmp_path),
                client=client,
                server_identity=SERVER_IDENTITY,
                slice_plan=_two_slice_plan(),
            )

    def test_transcript_artifact_reflects_slice_bounded_segment_timing(self, tmp_path):
        result = run_episode(
            "meeting-1",
            SEGMENTS,
            audio_chunk_resolver=_audio_resolver(tmp_path),
            client=_FakeClient(),
            server_identity=SERVER_IDENTITY,
            slice_plan=_two_slice_plan(),
            audio_slice_resolver=_slice_resolver(tmp_path),
        )
        # The fake client's transcribe reply has 2 segments; the FIRST
        # transcribe_span task is slice 0 ([0, 5)), so its segments must be
        # timed inside [0, 5), never stretched out to the whole chunk's
        # [0, 10).
        starts_and_ends = [(s["start"], s["end"]) for s in result.transcript_artifact.segments[:2]]
        assert all(0.0 <= start and end <= 5.0 for start, end in starts_and_ends)
