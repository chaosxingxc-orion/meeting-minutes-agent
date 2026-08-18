"""The light-off entry point: run ONE episode end to end (component C10,
mission spec item 5) -- a resolved meeting fixture -> chunk plan -> task
queue -> :mod:`meeting_minutes_agent.controller.loop` -> artifacts +
:class:`~meeting_minutes_agent.runreceipt.RunReceipt` flight receipt, with
an injected client (a fake in every test in this repository; a real
:class:`meeting_minutes_agent.client.transport.LlamaServerTransport` in
production).

Task-set construction (the harness's own, deterministic scheduling
decision -- :mod:`meeting_minutes_agent.controller.tasks`/``.dispatcher``
themselves make no assumption about WHICH tasks an episode runs): one
``transcribe_span`` task per chunk plan chunk, in chunk order -- OR, when a
:class:`~meeting_minutes_agent.chunking.slicer.SlicePlan` is supplied (item
14, ``docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md`` list
item 14), one ``transcribe_span`` task per transport SLICE, in slice order,
each carrying its ``slice_index`` in ``task.payload`` and attributed to its
containing task chunk -- followed by exactly one ``summarize_section`` and
one ``resolve_ledger`` task, both STILL targeting the LAST chunk index
either way (unchanged by item 14; see :func:`run_episode`'s own docstring).
:data:`~meeting_minutes_agent.controller.tasks.DEFAULT_TASK_PRIORITY`
already orders these correctly (transcribe < summarize < resolve-ledger)
regardless of push order, but they are pushed in that same natural order
here for readability -- the linear per-chunk-or-per-slice push loop is
itself the "determinism by construction" this harness relies on (backbone
design doc SS5.3): a plain, ordered ``for`` loop, never a set or any other
unordered structure.

Import discipline: this module imports
:mod:`meeting_minutes_agent.controller.loop`, which imports openjiuwen at
module level and raises ``ImportError`` naming
:data:`meeting_minutes_agent.controller.loop.OJW_INSTALL_HINT` when
openjiuwen is absent -- that error propagates unchanged from importing
THIS module, so ``pytest.importorskip("meeting_minutes_agent.harness.episode")``
turns it into a clean skip exactly as for every other openjiuwen-gated
module in this repository. This module is therefore NOT re-exported from
``meeting_minutes_agent.harness``'s own ``__init__`` (same discipline as
``meeting_minutes_agent.client``'s ``__init__`` never importing
``client.component``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..chunking.constants import TASK_CHUNK_MAX_S, TASK_CHUNK_MIN_S, TASK_CHUNK_TARGET_S
from ..chunking.leakage import BoundaryProvenance
from ..chunking.models import Chunk, ChunkPlan, SegmentLike
from ..chunking.planner import build_chunk_plan
from ..chunking.slicer import SlicePlan
from ..client.budgets import BudgetLimits, CallBudget
from ..context_budget import SlotContextConfig
from ..client.component import MeetingCoreClient
from ..client.receipts import FlightReceipt, ServerIdentity
from ..controller.assembly import (
    AttributedTranscriptArtifact,
    MinutesArtifact,
    build_attributed_transcript_artifact,
    build_minutes_artifact,
)
from ..controller.loop import DEFAULT_WORKFLOW_TIMEOUT_SECONDS, EpisodeLoopState, run_episode_workflow
from ..controller.tasks import TaskKind, TaskQueue
from ..glossary.arms import ArmKind
from ..runreceipt import RunReceipt
from ..state.episode import EpisodeState
from ..supply.config import SupplyArmConfig

__all__ = [
    "EpisodeHarnessConfig",
    "EpisodeResult",
    "run_episode",
]


@dataclass(frozen=True)
class EpisodeHarnessConfig:
    """Arm selection (``supply_arm`` + ``glossary_arm``), caps, and
    chunk-window parameters -- the config surface named by the mission
    spec's harness item explicitly. Every field is deliberately data a
    registered arm/probe config can set; no field encodes policy logic."""

    target_chunk_s: float = TASK_CHUNK_TARGET_S
    min_chunk_s: float = TASK_CHUNK_MIN_S
    max_chunk_s: float = TASK_CHUNK_MAX_S
    chunk_mode: str = "auto"
    topic_marks: tuple[float, ...] = ()
    boundary_provenance: BoundaryProvenance = BoundaryProvenance.SIGNAL
    allow_oracle_boundaries: bool = False
    # single_pass is gated behind an explicit opt-in even at the harness
    # config surface (17-item change list item 3): chunk_mode="single_pass"
    # without allow_single_pass=True still refuses, at plan time.
    allow_single_pass: bool = False
    slot_context: SlotContextConfig | None = None
    supply_arm: SupplyArmConfig = field(default_factory=SupplyArmConfig)
    glossary_arm: ArmKind = ArmKind.GATED
    # 17-item change list item 13: once a call is a transport SLICE rather
    # than a whole task chunk, dev-18 needs up to 33 slices/episode and
    # ICSI's longest meeting needs ~69 (analysis SS8.5/SS7) -- 100 leaves
    # headroom above both for the transcribe+summarize+ledger task set.
    max_calls: int = 100
    max_audio_seconds: float = 36000.0
    decoding_params: Mapping[str, object] = field(default_factory=dict)
    workflow_timeout_seconds: float = DEFAULT_WORKFLOW_TIMEOUT_SECONDS
    max_iterations_headroom: int = 10

    def validate(self) -> "EpisodeHarnessConfig":
        if isinstance(self.max_calls, bool) or not isinstance(self.max_calls, int) or self.max_calls <= 0:
            raise ValueError(f"max_calls must be a positive integer, got {self.max_calls!r}")
        if (
            isinstance(self.max_audio_seconds, bool)
            or not isinstance(self.max_audio_seconds, (int, float))
            or not math.isfinite(self.max_audio_seconds)
            or self.max_audio_seconds <= 0
        ):
            raise ValueError(f"max_audio_seconds must be a finite positive number, got {self.max_audio_seconds!r}")
        if (
            isinstance(self.workflow_timeout_seconds, bool)
            or not isinstance(self.workflow_timeout_seconds, (int, float))
            or not math.isfinite(self.workflow_timeout_seconds)
        ):
            raise ValueError(
                f"workflow_timeout_seconds must be a finite number, got {self.workflow_timeout_seconds!r}"
            )
        if (
            isinstance(self.max_iterations_headroom, bool)
            or not isinstance(self.max_iterations_headroom, int)
            or self.max_iterations_headroom < 0
        ):
            raise ValueError(
                f"max_iterations_headroom must be a non-negative integer, got {self.max_iterations_headroom!r}"
            )
        self.supply_arm.validate()
        return self


@dataclass(frozen=True)
class EpisodeResult:
    """Everything one light-off run produces."""

    meeting_id: str
    chunk_plan: ChunkPlan
    episode_state: EpisodeState
    minutes_artifact: MinutesArtifact
    transcript_artifact: AttributedTranscriptArtifact
    flight_receipt: RunReceipt
    dispatch_log: tuple[Mapping[str, Any], ...]
    budget_exhausted: bool

    def fingerprint(self) -> dict[str, Any]:
        """A compact, content-hashable summary for determinism testing: the
        episode state's own content hash, both artifacts' content hashes,
        the flight receipt's config hash, and the full dispatch log. This
        harness records no wall-clock/latency field anywhere in the
        fingerprint's inputs, unlike the SAEA study's own equivalent
        fingerprint (which has to strip a real ``latency_seconds`` field) --
        there is nothing volatile here to strip."""

        return {
            "episode_state_content_hash": self.episode_state.content_hash(),
            "minutes_content_hash": self.minutes_artifact.content_hash,
            "transcript_content_hash": self.transcript_artifact.content_hash,
            "flight_receipt_config_hash": self.flight_receipt.config_hash,
            "dispatch_log": [dict(entry) for entry in self.dispatch_log],
        }


class _RecordingClient:
    """Wraps an injected :class:`~meeting_minutes_agent.client.component.
    MeetingCoreClient` so every real
    :class:`~meeting_minutes_agent.client.transport.ModelResponse` it
    returns is also recorded into the run's
    :class:`~meeting_minutes_agent.client.receipts.FlightReceipt`, without
    :class:`~meeting_minutes_agent.client.component.FrozenMeetingCore`
    itself needing to know a receipt exists (that component's own
    docstring: it returns only a flattened summary dict, never the full
    :class:`~meeting_minutes_agent.client.transport.ModelResponse` with its
    attempt chain -- this wrapper sits BELOW it, at the client boundary,
    where the full response is still available)."""

    def __init__(self, inner: MeetingCoreClient, flight_receipt: FlightReceipt) -> None:
        self._inner = inner
        self._flight_receipt = flight_receipt

    def request(self, **kwargs: Any) -> Any:
        response = self._inner.request(**kwargs)
        self._flight_receipt.record(response)
        return response


def _chunk_index_for_time(chunk_plan: ChunkPlan, t: float) -> int:
    """The task chunk whose ``[start, end)`` window contains time ``t`` --
    a plain linear scan (a meeting has, at most, a few dozen chunks). Used
    only to attribute a transport SLICE (:mod:`meeting_minutes_agent.chunking.slicer`,
    meeting-level, built independently of the task-chunk walk) to its
    containing task chunk for per-slice dispatch (item 14). Clamped to the
    LAST chunk for any ``t`` at/after its end: an edge slice may be nudged
    a few seconds past its nominal span by the slicer's own snap margin
    (``chunking/slicer.py``'s ``build_turn_aware_slice_plan``, "the margin
    actually applied is ... room-aware"), and that overshoot must still
    resolve to a real chunk rather than raising."""

    if not chunk_plan.chunks:
        raise ValueError("_chunk_index_for_time: cannot map a slice time onto an empty chunk plan")
    for chunk in chunk_plan.chunks:
        if chunk.start <= t < chunk.end:
            return chunk.index
    return chunk_plan.chunks[-1].index


def run_episode(
    meeting_id: str,
    segments: Sequence[SegmentLike],
    *,
    audio_chunk_resolver: Callable[[Chunk], tuple[Path, float]],
    client: MeetingCoreClient,
    server_identity: ServerIdentity,
    config: EpisodeHarnessConfig = EpisodeHarnessConfig(),
    slice_plan: SlicePlan | None = None,
    audio_slice_resolver: Callable[[int], tuple[Path, float]] | None = None,
) -> EpisodeResult:
    """Run one episode end to end and return its :class:`EpisodeResult`.

    ``segments`` is any :class:`~meeting_minutes_agent.chunking.models.SegmentLike`
    sequence (a plain fixture's
    :class:`~meeting_minutes_agent.chunking.models.Segment` tuple, or an
    already-resolved E2 ``ResolvedMeeting.transcript`` -- used here only to
    build the chunk plan; the actual transcript content this episode acts
    on comes from the injected ``client``'s own replies).
    ``audio_chunk_resolver`` maps a chunk to the real ``(audio_path,
    audio_seconds)`` pair the frozen core is invoked with for that chunk;
    the harness never invents one itself (chunk timing is an
    approximation -- see :mod:`meeting_minutes_agent.controller.dispatcher`'s
    own docstring).

    ``slice_plan``/``audio_slice_resolver`` are the item-14 per-slice
    dispatch inputs (``docs/readiness/2026-08-18-chunk-slice-granularity-
    analysis.md`` list item 14): when ``slice_plan`` is given (typically
    built through the :class:`~meeting_minutes_agent.chunking.diarization.DiarizationBackend`
    seam -- :func:`~meeting_minutes_agent.chunking.diarization.build_turn_aware_slice_plan_for_resolved_meeting`
    or :func:`~meeting_minutes_agent.chunking.diarization.build_turn_aware_slice_plan_from_backend` --
    or by :mod:`meeting_minutes_agent.chunking.slicer`'s VAD/grid mode),
    the episode dispatches ONE ``transcribe_span`` task per SLICE instead
    of one per task chunk, and ``audio_slice_resolver`` (e.g.
    :func:`~meeting_minutes_agent.chunking.slicer.make_audio_chunk_resolver`
    over a materialized :class:`~meeting_minutes_agent.chunking.slicer.SliceManifest`)
    resolves each slice's own, narrower audio. ``summarize_section`` stays
    per task chunk and ``resolve_ledger`` stays per episode -- unchanged,
    exactly as before this deferred change (analysis list item 14's own
    wording). Both new parameters default to ``None``, which reproduces the
    pre-item-14 one-``transcribe_span``-per-CHUNK behaviour byte-for-byte;
    every existing caller keeps working unchanged."""

    config = config.validate()
    chunk_plan = build_chunk_plan(
        segments,
        meeting_id=meeting_id,
        target_chunk_s=config.target_chunk_s,
        min_chunk_s=config.min_chunk_s,
        max_chunk_s=config.max_chunk_s,
        topic_marks=config.topic_marks,
        boundary_provenance=config.boundary_provenance,
        allow_oracle_boundaries=config.allow_oracle_boundaries,
        mode=config.chunk_mode,
        allow_single_pass=config.allow_single_pass,
        slot_context=config.slot_context,
    )

    task_queue = TaskQueue()
    slice_bounds_by_index: dict[int, tuple[float, float]] | None = None
    if slice_plan is not None:
        if audio_slice_resolver is None:
            raise ValueError(
                "run_episode: slice_plan was given but audio_slice_resolver is None -- per-slice "
                "transcribe_span dispatch (item 14) needs a slice-indexed audio resolver, e.g. "
                "meeting_minutes_agent.chunking.slicer.make_audio_chunk_resolver"
            )
        if slice_plan.slices and not chunk_plan.chunks:
            raise ValueError(
                f"run_episode: slice_plan for meeting {meeting_id!r} carries "
                f"{len(slice_plan.slices)} slice(s) but the chunk plan built from `segments` is "
                "empty -- a slice cannot be dispatched with no task chunk to attribute it to"
            )
        slice_bounds_by_index = {sl.index: (sl.start, sl.end) for sl in slice_plan.slices}
        for sl in slice_plan.slices:
            chunk_index = _chunk_index_for_time(chunk_plan, sl.start)
            task_queue = task_queue.push(TaskKind.TRANSCRIBE_SPAN, chunk_index, payload={"slice_index": sl.index})
        transcribe_task_count = len(slice_plan.slices)
    else:
        for chunk in chunk_plan.chunks:
            task_queue = task_queue.push(TaskKind.TRANSCRIBE_SPAN, chunk.index)
        transcribe_task_count = len(chunk_plan.chunks)

    if chunk_plan.chunks:
        last_index = chunk_plan.chunks[-1].index
        task_queue = task_queue.push(TaskKind.SUMMARIZE_SECTION, last_index)
        task_queue = task_queue.push(TaskKind.RESOLVE_LEDGER, last_index)

    budget = CallBudget(BudgetLimits(max_calls=config.max_calls, max_audio_seconds=config.max_audio_seconds))
    flight_receipt = FlightReceipt(server_identity, budget)
    recording_client = _RecordingClient(client, flight_receipt)

    loop_state = EpisodeLoopState(
        meeting_id=meeting_id,
        chunk_plan=chunk_plan,
        supply_arm=config.supply_arm,
        glossary_arm=config.glossary_arm,
        decoding_params=dict(config.decoding_params),
        audio_chunk_resolver=audio_chunk_resolver,
        audio_slice_resolver=audio_slice_resolver,
        slice_bounds_by_index=slice_bounds_by_index,
        budget=budget,
        max_iterations=transcribe_task_count + 2 + config.max_iterations_headroom,
        task_queue=task_queue,
        episode_state=EpisodeState(),
    )
    run_episode_workflow(loop_state, recording_client, workflow_timeout_seconds=config.workflow_timeout_seconds)

    minutes_artifact = build_minutes_artifact(meeting_id, loop_state.minutes_parses)
    transcript_artifact = build_attributed_transcript_artifact(meeting_id, loop_state.resolved_segments)
    receipt = flight_receipt.build(run_id=meeting_id)

    return EpisodeResult(
        meeting_id=meeting_id,
        chunk_plan=chunk_plan,
        episode_state=loop_state.episode_state,
        minutes_artifact=minutes_artifact,
        transcript_artifact=transcript_artifact,
        flight_receipt=receipt,
        dispatch_log=tuple(loop_state.dispatch_log),
        budget_exhausted=loop_state.budget_exhausted,
    )
