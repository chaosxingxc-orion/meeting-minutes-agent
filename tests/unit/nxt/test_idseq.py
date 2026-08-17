from __future__ import annotations

from meeting_minutes_agent.corpora.nxt.idseq import IdSequence


def test_expand_single_id():
    seq = IdSequence(["a", "b", "c"])
    expansion = seq.expand("b", None)
    assert expansion.indices == (1,)
    assert expansion.missing_ids == ()


def test_expand_range():
    seq = IdSequence(["a", "b", "c", "d", "e"])
    expansion = seq.expand("b", "d")
    assert expansion.indices == (1, 2, 3)
    assert expansion.missing_ids == ()


def test_expand_range_covering_whole_sequence():
    seq = IdSequence(["a", "b", "c"])
    expansion = seq.expand("a", "c")
    assert expansion.indices == (0, 1, 2)


def test_expand_missing_start_id():
    seq = IdSequence(["a", "b", "c"])
    expansion = seq.expand("zzz", "c")
    assert expansion.indices == ()
    assert expansion.missing_ids == ("zzz",)


def test_expand_missing_end_id():
    seq = IdSequence(["a", "b", "c"])
    expansion = seq.expand("a", "zzz")
    assert expansion.indices == ()
    assert expansion.missing_ids == ("zzz",)


def test_expand_both_missing_reports_both():
    seq = IdSequence(["a", "b", "c"])
    expansion = seq.expand("zzz", "yyy")
    assert set(expansion.missing_ids) == {"zzz", "yyy"}


def test_expand_reversed_pair_is_swapped_defensively():
    seq = IdSequence(["a", "b", "c", "d"])
    expansion = seq.expand("d", "b")
    assert expansion.indices == (1, 2, 3)


def test_position_and_len():
    seq = IdSequence(["a", "b"])
    assert len(seq) == 2
    assert seq.position("a") == 0
    assert seq.position("nope") is None


def test_expand_does_not_rely_on_trailing_integer_naming():
    # ids that do NOT end in a running integer must still resolve correctly
    # by document position -- range math must never parse a suffix number.
    seq = IdSequence(["alpha", "beta", "gamma", "delta"])
    expansion = seq.expand("beta", "delta")
    assert expansion.indices == (1, 2, 3)
