"""The openJiuwen episode workflow (component C7, the true spine -- backbone
design doc SS5.3 mapping table): outer ``Workflow`` (Start -> episode loop
-> End); the loop is an ``AdvancedLoopComponent`` with a ``FuncCondition``
(queue non-empty AND budgets hold AND no runaway) over a LINEAR body chain
of exactly three ``WorkflowComponent`` nodes: ``next_task`` (pop one task,
build its :class:`~.dispatcher.DispatchUnit` via
:func:`~.dispatcher.build_dispatch_unit`) -> ``execute`` (invoke
:class:`meeting_minutes_agent.client.component.FrozenMeetingCore`, composed
directly and skipped in-component for a local-fold task) ->
``fold_state`` (parse + fold via :func:`~.dispatcher.fold_dispatch_result`).

**DETERMINISM BY CONSTRUCTION (mandated design ruling, backbone design doc
SS5.3 verbatim):** v1 selects exactly ONE task per iteration -- the loop
body stays a linear chain, inheriting the SAEA study's linear-chain Pregel
determinism argument (``docs/readiness/2026-08-08-ojw-rebuild-notes.md``
SS"Determinism findings": "the loop body is a LINEAR four-node chain inside
``AdvancedLoopComponent``'s Pregel graph, so every super-step has exactly
one ready node"). Parallel branches are DEFERRED; the branch-ordering
determinism proof obligation that design doc records stays open for
whoever adds them.

Lineage (recorded cross-repo import; the SAEA study's ``reproduction/ojw``
package, studies/speech-aware-evidence-acquisition, umbrella commit range
including ``12590d4`` -- the second reuse of that pattern in this
repository, after :mod:`meeting_minutes_agent.client.component`): the
outer-graph shape (``Workflow``/``Start``/``End``/``create_workflow_session``
with a ``WORKFLOW_EXECUTE_TIMEOUT`` env override), the loop shape
(``AdvancedLoopComponent`` + ``FuncCondition`` over a ``LoopGroup`` linear
chain, composed directly because ``LoopComponent``'s own wrapper only
admits static loop types), the "build inside the running loop" discipline,
and the None-deletion session-state read convention are all reimplemented
here, small, following ``reproduction/ojw/runner.py``,
``reproduction/ojw/components.py`` and ``reproduction/ojw/state.py``'s
documented shapes. No code is imported from that study. This repository's
own loop-carried Python state
(:class:`EpisodeLoopState`, this module's equivalent of that study's
``ObsSampleState``) and task-manager logic are new, not reused.

Session global state carries the loop's genuinely small, cross-iteration
state (:data:`DISPATCH_LOG_KEY` -- one small dict per dispatched task,
read back the None-deletion-safe way: a task that made no core call omits
``response_text_sha256`` entirely rather than writing it as ``None``,
because the framework's session-state merge treats a ``None`` value as a
key DELETION -- SAEA rebuild-notes "Framework findings" SS1). Heavy,
non-serializable objects (the chunk plan, the accumulated
:class:`~meeting_minutes_agent.state.episode.EpisodeState`, the task
queue, the call budget) are constructor-injected on :class:`EpisodeLoopState`
and never touch session state, mirroring that same study's own "heavy
objects... constructor-injected, never session state" discipline
(backbone design doc SS5.3 mapping table, last row).

Import discipline (zero-dependency gate, carried over verbatim from
:mod:`meeting_minutes_agent.client.component`): openjiuwen NEVER enters
this repository's ``pyproject.toml``. This module imports openjiuwen at
import time; importing it without openjiuwen installed raises
``ImportError`` naming :data:`OJW_INSTALL_HINT`, which
``pytest.importorskip("meeting_minutes_agent.controller.loop")`` turns into
a clean skip for every test in this module's own test file. This module
must be imported explicitly by a caller that needs it -- never through
``meeting_minutes_agent.controller``'s own ``__init__``, so the rest of
that package (:mod:`.tasks`, :mod:`.dispatcher`, :mod:`.assembly`) and the
whole repository test suite stay importable with openjiuwen absent.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

OJW_INSTALL_HINT = (
    "meeting_minutes_agent.controller.loop requires the openjiuwen framework, which is not "
    "importable in this environment; install the pinned openjiuwen==0.1.16.post2 into the "
    "shared WSL research venv (see docs/plans/2026-08-18-agent-backbone-and-layout.md SS5.3) -- "
    "openjiuwen never enters pyproject.toml (zero-dependency gate), and this module cannot be "
    "used without it."
)

try:
    from openjiuwen.core.common.exception.codes import StatusCode
    from openjiuwen.core.common.exception.errors import BaseError
    from openjiuwen.core.context_engine import ModelContext
    from openjiuwen.core.graph.executable import Input, Output
    from openjiuwen.core.session import WORKFLOW_EXECUTE_TIMEOUT
    from openjiuwen.core.session.node import Session
    from openjiuwen.core.workflow import (
        End,
        FuncCondition,
        LoopGroup,
        Start,
        Workflow,
        WorkflowComponent,
        create_workflow_session,
    )
    from openjiuwen.core.workflow.components.flow.loop.loop_comp import AdvancedLoopComponent
except ImportError as error:  # pragma: no cover - exercised via importorskip
    raise ImportError(OJW_INSTALL_HINT) from error

from ..chunking.models import Chunk, ChunkPlan, SegmentLike
from ..client.budgets import CallBudget
from ..client.component import FrozenMeetingCore, MeetingCoreClient
from ..glossary.arms import ArmKind
from ..heads.minutes import MinutesBulletClaim, MinutesParseResult
from ..state.episode import EpisodeState
from ..supply.config import SupplyArmConfig
from .dispatcher import DispatchUnit, build_dispatch_unit, fold_dispatch_result
from .tasks import Task, TaskKind, TaskQueue

__all__ = [
    "OJW_INSTALL_HINT",
    "EpisodeLoopError",
    "EpisodeLoopState",
    "DISPATCH_LOG_KEY",
    "NextTask",
    "ExecuteViaFrozenCore",
    "FoldState",
    "build_episode_workflow",
    "run_episode_workflow",
    "DEFAULT_WORKFLOW_TIMEOUT_SECONDS",
]

DEFAULT_WORKFLOW_TIMEOUT_SECONDS = 21600.0  # 6h backstop, mirrors the SAEA study's own default

NEXT_TASK_NODE_ID = "next_task"
EXECUTE_NODE_ID = "execute"
FOLD_STATE_NODE_ID = "fold_state"
LOOP_NODE_ID = "episode_loop"
START_NODE_ID = "start"
END_NODE_ID = "end"

# Session GLOBAL-state key for the loop-carried dispatch log (module
# docstring). Flat underscore name -- the framework's nested-path split is
# ".", so a dotted key would be misread as a path (mirrors both this
# repository's own client.component.RESPONSE_LOG_KEY and the SAEA study's
# ACCEPTED_SPANS_KEY convention).
DISPATCH_LOG_KEY = "episode_dispatch_log"


class EpisodeLoopError(RuntimeError):
    """The episode workflow refused or was killed: a runaway loop
    (iteration count exceeded ``max_iterations``), a per-episode timeout
    kill translated from the framework's own ``WORKFLOW_EXECUTION_TIMEOUT``,
    or a component ran out of the LINEAR-chain invariant order."""


@dataclass
class EpisodeLoopState:
    """The loop's Python-side driver state -- this module's equivalent of
    the SAEA study's ``ObsSampleState`` (module docstring). NOT a frozen
    dataclass: fields carrying the episode's accumulated results are
    reassigned in place across iterations by the loop-body components
    (single writer per field, documented at each field below), exactly as
    that study's own state object is. Every FIELD that itself holds
    immutable data (``episode_state``, ``task_queue``) still follows the
    non-destructive discipline those types already guarantee (a `with_*`/
    `push`/`pop` call returns a NEW value, which this object's owning
    component then reassigns onto the corresponding attribute) --
    "mutation" here means "this Python attribute now names a new value",
    never in-place edits to the value itself."""

    # -- frozen-per-episode facts (set once, never reassigned) -------------
    meeting_id: str
    chunk_plan: ChunkPlan
    supply_arm: SupplyArmConfig
    glossary_arm: ArmKind
    decoding_params: Mapping[str, object]
    audio_chunk_resolver: Callable[[Chunk], tuple[Path, float]]
    budget: CallBudget
    max_iterations: int

    # -- loop-carried state (single writer per field, see each component) --
    task_queue: TaskQueue
    episode_state: EpisodeState
    resolved_segments: tuple[SegmentLike, ...] = ()
    pending_ledger_bullets: tuple[MinutesBulletClaim, ...] = ()
    minutes_parses: list[MinutesParseResult] = field(default_factory=list)
    dispatch_log: list[dict] = field(default_factory=list)
    iteration: int = 0
    runaway: bool = False
    budget_exhausted: bool = False
    # Transient, one-iteration handoff: written by NextTask, read by
    # ExecuteViaFrozenCore and FoldState, cleared by FoldState at the end of
    # every iteration -- never carries across a loop round.
    current_unit: DispatchUnit | None = None

    def should_continue(self) -> bool:
        """The ``FuncCondition`` callable (module docstring): queue
        non-empty AND budgets hold AND no runaway.

        The budget check is a PRE-CHECK against ``self.budget.totals`` (a
        read-only snapshot -- this method never itself reserves budget;
        real reservation is the injected client's own responsibility,
        exactly as :class:`meeting_minutes_agent.client.transport.
        LlamaServerTransport` already does before every transport call). It
        only applies to task kinds that would actually call the core
        (``transcribe_span``/``summarize_section``); a local-fold
        ``resolve_ledger`` task never needs budget headroom."""

        if self.iteration >= self.max_iterations:
            self.runaway = True
            return False
        if self.task_queue.is_empty():
            return False
        peek = self.task_queue.peek()
        if peek.kind in (TaskKind.TRANSCRIBE_SPAN, TaskKind.SUMMARIZE_SECTION):
            chunk = self.chunk_plan.chunks[peek.chunk_index]
            needed_seconds = max(chunk.end - chunk.start, 0.0)
            totals = self.budget.totals
            if totals["calls_used"] + 1 > totals["max_calls"]:
                self.budget_exhausted = True
                return False
            if totals["audio_seconds_used"] + needed_seconds > totals["max_audio_seconds"]:
                self.budget_exhausted = True
                return False
        return True


class NextTask(WorkflowComponent):
    """Loop body step 1: pop one task (deterministic order,
    :meth:`~meeting_minutes_agent.controller.tasks.TaskQueue.pop`) and build
    its executable :class:`~.dispatcher.DispatchUnit`, staged on
    ``state.current_unit`` for the next two nodes in this SAME iteration."""

    def __init__(self, state: EpisodeLoopState) -> None:
        super().__init__()
        self._state = state

    async def invoke(self, inputs: Input, session: Session, context: ModelContext) -> Output:
        state = self._state
        task: Task
        task, state.task_queue = state.task_queue.pop()
        unit = build_dispatch_unit(
            task,
            episode_state=state.episode_state,
            chunk_plan=state.chunk_plan,
            resolved_segments=state.resolved_segments,
            supply_arm=state.supply_arm,
            decoding_params=state.decoding_params,
            pending_ledger_bullets=state.pending_ledger_bullets,
        )
        state.current_unit = unit
        return {
            "task_kind": task.kind.value,
            "chunk_index": task.chunk_index,
            "requires_core_call": unit.requires_core_call,
        }


class ExecuteViaFrozenCore(WorkflowComponent):
    """Loop body step 2: ``execute-via-FrozenMeetingCore``. Wraps a
    constructor-injected :class:`~meeting_minutes_agent.client.component.
    FrozenMeetingCore` -- COMPOSED (its ``invoke`` coroutine called
    directly), never re-subclassed -- and skips the call entirely for a
    local-fold task (``requires_core_call=False``) via a plain Python
    conditional INSIDE this one component's own ``invoke``. This keeps the
    loop body a single linear chain of exactly three graph nodes regardless
    of task kind (module docstring, "DETERMINISM BY CONSTRUCTION") -- the
    branch lives inside a node's logic, never as a second graph edge."""

    def __init__(self, core: FrozenMeetingCore, state: EpisodeLoopState) -> None:
        super().__init__()
        self._core = core
        self._state = state

    async def invoke(self, inputs: Input, session: Session, context: ModelContext) -> Output:
        state = self._state
        unit = state.current_unit
        if unit is None:
            raise EpisodeLoopError(
                "ExecuteViaFrozenCore ran with no staged DispatchUnit; NextTask must run first "
                "in the same loop iteration (LINEAR chain invariant violated)"
            )
        if not unit.requires_core_call:
            return {"raw_text": "", "response_request_id": unit.request_id, "called_core": False}

        if unit.chunk is None or unit.head_request is None:
            raise EpisodeLoopError(
                f"DispatchUnit for task {unit.task.to_dict()!r} requires a core call but is "
                "missing chunk/head_request; this is a controller.dispatcher bug, not a runtime "
                "condition this loop should paper over"
            )
        audio_path, audio_seconds = state.audio_chunk_resolver(unit.chunk)
        core_inputs = unit.head_request.to_transport_kwargs(
            request_id=unit.request_id, audio_path=audio_path, audio_seconds=audio_seconds
        )
        core_output = await self._core.invoke(core_inputs, session, context)
        return {
            "raw_text": core_output["text"],
            "response_request_id": core_output["request_id"],
            "called_core": True,
        }


class FoldState(WorkflowComponent):
    """Loop body step 3: parse the response and fold it into the episode
    state via :func:`~.dispatcher.fold_dispatch_result`; appends one small
    dispatch-log entry to BOTH session global state
    (:data:`DISPATCH_LOG_KEY`) and ``state.dispatch_log`` (two homes, same
    reasoning as :mod:`meeting_minutes_agent.client.component`'s own
    response log: the post-workflow driver code that builds artifacts runs
    after the session is gone)."""

    def __init__(self, state: EpisodeLoopState) -> None:
        super().__init__()
        self._state = state

    async def invoke(self, inputs: Input, session: Session, context: ModelContext) -> Output:
        state = self._state
        unit = state.current_unit
        if unit is None:
            raise EpisodeLoopError("FoldState ran with no staged DispatchUnit")

        # None-deletion discipline (module docstring): a missing key here IS
        # the None/absent value ExecuteViaFrozenCore set (or never set, on
        # the local-fold path).
        raw_text = inputs.get("raw_text") or ""
        called_core = bool(inputs.get("called_core"))

        result = fold_dispatch_result(
            unit,
            raw_text,
            episode_state=state.episode_state,
            glossary_arm=state.glossary_arm,
            pending_ledger_bullets=state.pending_ledger_bullets,
        )
        state.episode_state = result.episode_state
        state.resolved_segments = state.resolved_segments + result.new_resolved_segments
        if result.minutes_parse is not None:
            state.minutes_parses.append(result.minutes_parse)
        state.pending_ledger_bullets = result.pending_ledger_bullets

        entry: dict[str, object] = {
            "seq": len(state.dispatch_log),
            "task_kind": unit.task.kind.value,
            "chunk_index": unit.task.chunk_index,
            "request_id": unit.request_id,
            "called_core": called_core,
        }
        if called_core:
            entry["response_text_sha256"] = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        log = list(session.get_global_state(DISPATCH_LOG_KEY) or [])
        log.append(entry)
        session.update_global_state({DISPATCH_LOG_KEY: log})
        state.dispatch_log.append(entry)

        state.current_unit = None
        state.iteration += 1
        return {"dispatch_count": len(log)}


def build_episode_workflow(state: EpisodeLoopState, client: MeetingCoreClient) -> Workflow:
    """The episode graph (module docstring): ``Start -> episode_loop ->
    End``, ``episode_loop = AdvancedLoopComponent(LoopGroup[next_task ->
    execute -> fold_state], FuncCondition(state.should_continue))``. Must be
    called from inside a running asyncio event loop (SAEA rebuild-notes
    "Framework findings" SS2, carried over by
    :func:`meeting_minutes_agent.client.component.build_single_request_workflow`'s
    own docstring) -- see :func:`_build_and_invoke`."""

    core = FrozenMeetingCore(client)

    loop_group = LoopGroup()
    loop_group.add_workflow_comp(NEXT_TASK_NODE_ID, NextTask(state))
    loop_group.add_workflow_comp(
        EXECUTE_NODE_ID,
        ExecuteViaFrozenCore(core, state),
        inputs_schema={"task_kind": f"${{{NEXT_TASK_NODE_ID}.task_kind}}"},
    )
    loop_group.add_workflow_comp(
        FOLD_STATE_NODE_ID,
        FoldState(state),
        inputs_schema={
            "raw_text": f"${{{EXECUTE_NODE_ID}.raw_text}}",
            "called_core": f"${{{EXECUTE_NODE_ID}.called_core}}",
        },
    )
    loop_group.start_nodes([NEXT_TASK_NODE_ID])
    loop_group.end_nodes([FOLD_STATE_NODE_ID])
    loop_group.add_connection(NEXT_TASK_NODE_ID, EXECUTE_NODE_ID)
    loop_group.add_connection(EXECUTE_NODE_ID, FOLD_STATE_NODE_ID)

    loop_node = AdvancedLoopComponent(loop_group, FuncCondition(state.should_continue))

    flow = Workflow()
    flow.set_start_comp(START_NODE_ID, Start(), inputs_schema={"meeting_id": "${meeting_id}"})
    flow.set_end_comp(END_NODE_ID, End(), inputs_schema={"loop": f"${{{LOOP_NODE_ID}}}"})
    flow.add_workflow_comp(LOOP_NODE_ID, loop_node)
    flow.add_connection(START_NODE_ID, LOOP_NODE_ID)
    flow.add_connection(LOOP_NODE_ID, END_NODE_ID)
    return flow


async def _build_and_invoke(
    state: EpisodeLoopState, client: MeetingCoreClient, workflow_timeout_seconds: float
) -> None:
    # Built INSIDE the running loop (module docstring).
    flow = build_episode_workflow(state, client)
    session = create_workflow_session(envs={WORKFLOW_EXECUTE_TIMEOUT: float(workflow_timeout_seconds)})
    try:
        await flow.invoke(inputs={"meeting_id": state.meeting_id}, session=session)
    except BaseError as error:
        if getattr(error, "code", None) == StatusCode.WORKFLOW_EXECUTION_TIMEOUT.code:
            raise EpisodeLoopError(
                f"openJiuwen killed episode {state.meeting_id!r} at the per-episode workflow "
                f"ceiling ({workflow_timeout_seconds} s); raise workflow_timeout_seconds if the "
                "episode legitimately needs longer (<= 0 disables the limit, framework convention)"
            ) from error
        raise


def run_episode_workflow(
    state: EpisodeLoopState,
    client: MeetingCoreClient,
    *,
    workflow_timeout_seconds: float = DEFAULT_WORKFLOW_TIMEOUT_SECONDS,
) -> None:
    """Build the graph and drive it to completion, mutating ``state`` in
    place across iterations. Raises :class:`EpisodeLoopError` if the loop
    ran away (``state.max_iterations`` exceeded) -- this should never
    happen for a task set the harness itself constructed (exactly
    ``len(chunk_plan.chunks) + 2`` tasks against a headroom-padded ceiling),
    so a runaway here signals a real bug, not an expected stop condition
    (unlike ``state.budget_exhausted``, which is an intentional, non-raising
    stop -- inspect it on ``state`` after this returns)."""

    asyncio.run(_build_and_invoke(state, client, workflow_timeout_seconds))
    if state.runaway:
        raise EpisodeLoopError(
            f"episode {state.meeting_id!r} exceeded {state.max_iterations} loop iterations; "
            "refusing a runaway loop"
        )
