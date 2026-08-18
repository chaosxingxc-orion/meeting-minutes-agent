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
``transcribe_span`` task per chunk plan chunk, in chunk order, followed by
exactly one ``summarize_section`` and one ``resolve_ledger`` task both
targeting the LAST chunk index. :data:`~meeting_minutes_agent.controller.
tasks.DEFAULT_TASK_PRIORITY` already orders these correctly (transcribe <
summarize < resolve-ledger) regardless of push order, but they are pushed
in that same natural order here for readability.

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

from ..chunking.models import Chunk, ChunkPlan, SegmentLike
from ..chunking.planner import DEFAULT_WINDOW_CAP_S, build_chunk_plan
from ..client.budgets import BudgetLimits, CallBudget
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

    window_cap_s: float = DEFAULT_WINDOW_CAP_S
    chunk_mode: str = "auto"
    topic_marks: tuple[float, ...] = ()
    supply_arm: SupplyArmConfig = field(default_factory=SupplyArmConfig)
    glossary_arm: ArmKind = ArmKind.GATED
    max_calls: int = 50
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


def run_episode(
    meeting_id: str,
    segments: Sequence[SegmentLike],
    *,
    audio_chunk_resolver: Callable[[Chunk], tuple[Path, float]],
    client: MeetingCoreClient,
    server_identity: ServerIdentity,
    config: EpisodeHarnessConfig = EpisodeHarnessConfig(),
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
    own docstring)."""

    config = config.validate()
    chunk_plan = build_chunk_plan(
        segments,
        meeting_id=meeting_id,
        window_cap_s=config.window_cap_s,
        topic_marks=config.topic_marks,
        mode=config.chunk_mode,
    )

    task_queue = TaskQueue()
    for chunk in chunk_plan.chunks:
        task_queue = task_queue.push(TaskKind.TRANSCRIBE_SPAN, chunk.index)
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
        budget=budget,
        max_iterations=len(chunk_plan.chunks) + 2 + config.max_iterations_headroom,
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
