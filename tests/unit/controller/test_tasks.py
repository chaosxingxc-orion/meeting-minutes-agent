"""Tests for :mod:`meeting_minutes_agent.controller.tasks`: the typed task
model and the deterministic ``TaskQueue`` (priority + insertion-order
sorting, no wall-clock, no randomness)."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.controller.tasks import (
    DEFAULT_TASK_PRIORITY,
    Task,
    TaskKind,
    TaskQueue,
    TaskQueueEmptyError,
)

# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


def test_declared_task_kinds_are_exactly_five():
    assert {k.value for k in TaskKind} == {
        "transcribe_span",
        "summarize_section",
        "resolve_ledger",
        "re_listen",
        "answer_question",
    }


def test_default_priority_table_covers_every_kind():
    assert set(DEFAULT_TASK_PRIORITY) == set(TaskKind)


def test_task_to_dict_round_trips_fields():
    task = Task(kind=TaskKind.TRANSCRIBE_SPAN, chunk_index=3, priority=0, seq=7, payload={"x": 1})
    assert task.to_dict() == {
        "kind": "transcribe_span",
        "chunk_index": 3,
        "priority": 0,
        "seq": 7,
        "payload": {"x": 1},
    }


# ---------------------------------------------------------------------------
# TaskQueue: empty-queue behaviour
# ---------------------------------------------------------------------------


def test_fresh_queue_is_empty():
    queue = TaskQueue()
    assert queue.is_empty()
    assert len(queue) == 0


def test_peek_on_empty_queue_raises():
    with pytest.raises(TaskQueueEmptyError):
        TaskQueue().peek()


def test_pop_on_empty_queue_raises():
    with pytest.raises(TaskQueueEmptyError):
        TaskQueue().pop()


# ---------------------------------------------------------------------------
# TaskQueue: non-destructive discipline
# ---------------------------------------------------------------------------


def test_push_returns_a_new_queue_and_does_not_mutate_self():
    empty = TaskQueue()
    pushed = empty.push(TaskKind.TRANSCRIBE_SPAN, 0)
    assert empty.is_empty()  # original untouched
    assert len(pushed) == 1


def test_pop_returns_a_new_queue_and_does_not_mutate_self():
    queue = TaskQueue().push(TaskKind.TRANSCRIBE_SPAN, 0)
    task, new_queue = queue.pop()
    assert len(queue) == 1  # original untouched
    assert new_queue.is_empty()
    assert task.kind is TaskKind.TRANSCRIBE_SPAN


# ---------------------------------------------------------------------------
# TaskQueue: ordering rule -- (priority ascending, seq ascending)
# ---------------------------------------------------------------------------


def test_default_priority_orders_transcribe_before_summarize_before_ledger():
    queue = (
        TaskQueue()
        .push(TaskKind.RESOLVE_LEDGER, 0)
        .push(TaskKind.SUMMARIZE_SECTION, 0)
        .push(TaskKind.TRANSCRIBE_SPAN, 0)
    )
    kinds = []
    while not queue.is_empty():
        task, queue = queue.pop()
        kinds.append(task.kind)
    assert kinds == [TaskKind.TRANSCRIBE_SPAN, TaskKind.SUMMARIZE_SECTION, TaskKind.RESOLVE_LEDGER]


def test_equal_priority_ties_break_fifo_by_insertion_order():
    queue = (
        TaskQueue()
        .push(TaskKind.TRANSCRIBE_SPAN, 2)
        .push(TaskKind.TRANSCRIBE_SPAN, 0)
        .push(TaskKind.TRANSCRIBE_SPAN, 1)
    )
    chunk_indices = []
    while not queue.is_empty():
        task, queue = queue.pop()
        chunk_indices.append(task.chunk_index)
    # all same (default) priority -> pure insertion order, never re-sorted
    # by chunk_index or any other field
    assert chunk_indices == [2, 0, 1]


def test_explicit_priority_override_wins_over_the_default_table():
    # A re_listen task (default priority 5) pushed with an explicit lower
    # priority dispatches before a transcribe_span (default priority 0).
    queue = TaskQueue().push(TaskKind.TRANSCRIBE_SPAN, 0).push(TaskKind.RE_LISTEN, 0, priority=-1)
    task, _ = queue.pop()
    assert task.kind is TaskKind.RE_LISTEN


def test_mixed_priority_and_insertion_order_is_fully_deterministic():
    queue = (
        TaskQueue()
        .push(TaskKind.SUMMARIZE_SECTION, 0)  # priority 10, seq 0
        .push(TaskKind.TRANSCRIBE_SPAN, 1)  # priority 0, seq 1
        .push(TaskKind.TRANSCRIBE_SPAN, 0)  # priority 0, seq 2
        .push(TaskKind.RESOLVE_LEDGER, 0)  # priority 20, seq 3
    )
    order = []
    while not queue.is_empty():
        task, queue = queue.pop()
        order.append((task.kind, task.chunk_index))
    assert order == [
        (TaskKind.TRANSCRIBE_SPAN, 1),
        (TaskKind.TRANSCRIBE_SPAN, 0),
        (TaskKind.SUMMARIZE_SECTION, 0),
        (TaskKind.RESOLVE_LEDGER, 0),
    ]


def test_seq_assigned_by_push_is_monotonic_and_never_caller_chosen():
    queue = TaskQueue().push(TaskKind.TRANSCRIBE_SPAN, 0).push(TaskKind.TRANSCRIBE_SPAN, 1)
    assert [t.seq for t in queue.tasks] == [0, 1]


# ---------------------------------------------------------------------------
# TaskQueue: determinism -- the same push sequence always yields the same
# resulting queue and the same pop order, run repeatedly
# ---------------------------------------------------------------------------


def _build_mixed_queue() -> TaskQueue:
    return (
        TaskQueue()
        .push(TaskKind.TRANSCRIBE_SPAN, 0)
        .push(TaskKind.TRANSCRIBE_SPAN, 1)
        .push(TaskKind.TRANSCRIBE_SPAN, 2)
        .push(TaskKind.SUMMARIZE_SECTION, 2)
        .push(TaskKind.RESOLVE_LEDGER, 2)
    )


def test_identical_push_sequences_yield_structurally_equal_queues():
    a = _build_mixed_queue()
    b = _build_mixed_queue()
    assert a == b  # frozen dataclass structural equality


def test_pop_order_is_identical_across_five_fresh_builds():
    orders = []
    for _ in range(5):
        queue = _build_mixed_queue()
        order = []
        while not queue.is_empty():
            task, queue = queue.pop()
            order.append(task.to_dict())
        orders.append(order)
    assert all(order == orders[0] for order in orders)
    assert [t["kind"] for t in orders[0]] == [
        "transcribe_span",
        "transcribe_span",
        "transcribe_span",
        "summarize_section",
        "resolve_ledger",
    ]


def test_push_many_preserves_spec_order_as_insertion_order():
    queue = TaskQueue().push_many(
        [
            {"kind": TaskKind.TRANSCRIBE_SPAN, "chunk_index": 5},
            {"kind": TaskKind.TRANSCRIBE_SPAN, "chunk_index": 1},
            {"kind": TaskKind.TRANSCRIBE_SPAN, "chunk_index": 3},
        ]
    )
    order = [t.chunk_index for t in queue.tasks]
    assert order == [5, 1, 3]  # same priority -> pure spec order


def test_push_many_accepts_plain_kind_chunk_index_pairs():
    queue = TaskQueue().push_many(
        [(TaskKind.TRANSCRIBE_SPAN, 0), (TaskKind.TRANSCRIBE_SPAN, 1)]
    )
    assert [t.chunk_index for t in queue.tasks] == [0, 1]


def test_push_many_honors_per_spec_priority_and_payload_overrides():
    queue = TaskQueue().push_many(
        [
            {"kind": TaskKind.RE_LISTEN, "chunk_index": 0, "priority": -5, "payload": {"reason": "noisy"}},
            {"kind": TaskKind.TRANSCRIBE_SPAN, "chunk_index": 0},
        ]
    )
    first, _ = queue.pop()
    assert first.kind is TaskKind.RE_LISTEN
    assert first.priority == -5
    assert first.payload == {"reason": "noisy"}
