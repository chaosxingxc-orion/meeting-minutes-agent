"""Typed task model + the deterministic ``TaskQueue`` (component C7, backbone
design doc SS5.1 "Task queue + dispatcher": "typed tasks ... rule-routed to
the perception loop or to task heads; scheduling is deterministic (priority
+ order rules as data, never model-decided in v1)").

Five declared task kinds. Three are real, dispatchable in v1
(:mod:`.dispatcher`): ``transcribe_span`` (LISTEN-stage per-chunk
transcribe+attribute), ``summarize_section`` (the minutes head over the
episode so far), ``resolve_ledger`` (a LOCAL fold -- no core call -- of the
most recently produced minutes bullets' ACTIONS/DECISIONS sections into the
episode's decision/action ledger; see :mod:`.dispatcher`'s module docstring
for why this one task kind never touches the frozen core). Two,
``re_listen`` and ``answer_question``, are declared enum members ONLY --
honest stubs, mirroring :mod:`meeting_minutes_agent.heads.qa`'s own stub
discipline: they exist so a caller can reference/queue them today, but
:func:`meeting_minutes_agent.controller.dispatcher.build_dispatch_unit`
refuses to dispatch either, raising :class:`TaskDispatchNotImplementedError`
naming the precondition, rather than silently no-opping or guessing at a
request shape nothing has designed yet (``re_listen`` needs the DIARIZE/
re-ask apparatus backbone design doc SS5.3 reserves for a future
model-invoked arm; ``answer_question`` needs the MeetingQA-floor
measurement :mod:`meeting_minutes_agent.heads.qa` itself is stubbed behind).

Ordering rule (explicit data, never wall-clock, never randomness): a
:class:`TaskQueue` is always kept sorted by ``(priority ascending, seq
ascending)`` -- lower ``priority`` dispatches first; among equal
priorities, earlier-inserted (lower ``seq``) dispatches first (FIFO
tie-break). :data:`DEFAULT_TASK_PRIORITY` is the priority-by-kind table a
caller may rely on via :meth:`TaskQueue.push`'s default, or override
per-push for a registered scheduling arm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class TaskKind(str, Enum):
    TRANSCRIBE_SPAN = "transcribe_span"
    SUMMARIZE_SECTION = "summarize_section"
    RESOLVE_LEDGER = "resolve_ledger"
    RE_LISTEN = "re_listen"
    ANSWER_QUESTION = "answer_question"


# The priority-by-kind table (module docstring "Ordering rule"): lower value
# dispatches first. TRANSCRIBE_SPAN must complete (for every chunk) before
# SUMMARIZE_SECTION reads the accumulated transcript, which must complete
# before RESOLVE_LEDGER folds its bullets -- expressed here as plain
# ascending data, not as code that special-cases task kinds at pop time.
# RE_LISTEN/ANSWER_QUESTION carry provisional priorities so a caller CAN
# queue them (module docstring); dispatch itself refuses either regardless
# of where they sort.
DEFAULT_TASK_PRIORITY: Mapping[TaskKind, int] = {
    TaskKind.TRANSCRIBE_SPAN: 0,
    TaskKind.RE_LISTEN: 5,
    TaskKind.SUMMARIZE_SECTION: 10,
    TaskKind.RESOLVE_LEDGER: 20,
    TaskKind.ANSWER_QUESTION: 30,
}


@dataclass(frozen=True)
class Task:
    """One queued unit of work. ``seq`` is assigned by
    :meth:`TaskQueue.push` at insertion time (never by the caller) -- it is
    the tie-break half of the ordering rule, not a caller-chosen field."""

    kind: TaskKind
    chunk_index: int
    priority: int
    seq: int
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "chunk_index": self.chunk_index,
            "priority": self.priority,
            "seq": self.seq,
            "payload": dict(self.payload),
        }


class TaskQueueEmptyError(RuntimeError):
    """Raised by :meth:`TaskQueue.pop`/:meth:`TaskQueue.peek` on an empty
    queue -- fail-closed rather than returning a sentinel a caller could
    mistake for a real task."""


@dataclass(frozen=True)
class TaskQueue:
    """An immutable, deterministically-ordered task queue. Every mutator
    (:meth:`push`, :meth:`push_many`, :meth:`pop`) returns a NEW queue (or a
    ``(task, new_queue)`` pair for ``pop``); ``self`` is never mutated --
    the same non-destructive discipline
    :class:`meeting_minutes_agent.chunking.state.GlossaryStateLog` already
    uses. ``tasks`` is always kept sorted by the module docstring's ordering
    rule, so :meth:`peek`/:meth:`pop` are simply "the first element"."""

    tasks: tuple[Task, ...] = ()
    next_seq: int = 0

    def __len__(self) -> int:
        return len(self.tasks)

    def is_empty(self) -> bool:
        return len(self.tasks) == 0

    def push(
        self,
        kind: TaskKind,
        chunk_index: int,
        *,
        priority: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> "TaskQueue":
        """Return a NEW queue with one more task appended and re-sorted by
        the ordering rule. ``priority`` defaults to
        :data:`DEFAULT_TASK_PRIORITY` for ``kind``; pass an explicit value
        to realize a registered scheduling-arm override."""

        resolved_priority = DEFAULT_TASK_PRIORITY[kind] if priority is None else priority
        task = Task(
            kind=kind,
            chunk_index=chunk_index,
            priority=resolved_priority,
            seq=self.next_seq,
            payload=dict(payload or {}),
        )
        ordered = tuple(sorted((*self.tasks, task), key=lambda t: (t.priority, t.seq)))
        return TaskQueue(tasks=ordered, next_seq=self.next_seq + 1)

    def push_many(
        self, specs: Sequence[tuple[TaskKind, int]] | Sequence[Mapping[str, Any]]
    ) -> "TaskQueue":
        """Push a sequence of tasks in ``specs`` order (insertion order
        decides the ``seq`` tie-break among any pushed at equal priority).
        Each element is either a ``(kind, chunk_index)`` pair or a mapping
        with keys ``kind``, ``chunk_index`` and optionally ``priority``/
        ``payload``."""

        queue = self
        for spec in specs:
            if isinstance(spec, Mapping):
                queue = queue.push(
                    spec["kind"],
                    spec["chunk_index"],
                    priority=spec.get("priority"),
                    payload=spec.get("payload"),
                )
            else:
                kind, chunk_index = spec
                queue = queue.push(kind, chunk_index)
        return queue

    def peek(self) -> Task:
        if not self.tasks:
            raise TaskQueueEmptyError("cannot peek: TaskQueue is empty")
        return self.tasks[0]

    def pop(self) -> tuple[Task, "TaskQueue"]:
        """Return ``(the first task in order, a NEW queue without it)``."""

        if not self.tasks:
            raise TaskQueueEmptyError("cannot pop: TaskQueue is empty")
        task = self.tasks[0]
        return task, TaskQueue(tasks=self.tasks[1:], next_seq=self.next_seq)


__all__ = [
    "TaskKind",
    "DEFAULT_TASK_PRIORITY",
    "Task",
    "TaskQueue",
    "TaskQueueEmptyError",
]
