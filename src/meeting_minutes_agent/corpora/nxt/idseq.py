"""Document-order id index for one parsed NXT stand-off file.

``id(a)..id(b)`` range pointers (see :mod:`pointers`) are resolved by
POSITION in document order -- the index of ``a`` through the index of ``b``,
inclusive -- never by parsing a trailing integer out of the id string. AMI's
ids happen to end in a running number (``...words12``), but nothing in the
NXT format guarantees that, and depending on it would silently break on a
corpus (e.g. ICSI) whose ids don't follow the same convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RangeExpansion:
    """``indices`` are positions into the sequence ``IdSequence`` was built
    from, in increasing document order. ``missing_ids`` is non-empty (and
    ``indices`` empty) when either endpoint isn't in this file at all --
    the caller's signal to record an orphan pointer rather than guess."""

    indices: tuple[int, ...]
    missing_ids: tuple[str, ...]


class IdSequence:
    def __init__(self, ids: Iterable[str]):
        self._ids: tuple[str, ...] = tuple(ids)
        self._index: dict[str, int] = {identifier: position for position, identifier in enumerate(self._ids)}

    def __len__(self) -> int:
        return len(self._ids)

    def position(self, identifier: str) -> int | None:
        return self._index.get(identifier)

    def expand(self, start_id: str, end_id: str | None) -> RangeExpansion:
        """Inclusive range from ``start_id`` to ``end_id`` (or just
        ``start_id`` alone when ``end_id`` is None). A reversed pair (end
        before start in document order) is swapped defensively rather than
        producing an empty range -- not observed in AMI, but cheap to not
        silently drop data over."""

        missing = tuple(i for i in (start_id, end_id) if i is not None and i not in self._index)
        if missing:
            return RangeExpansion(indices=(), missing_ids=missing)
        start = self._index[start_id]
        end = self._index[end_id] if end_id is not None else start
        if end < start:
            start, end = end, start
        return RangeExpansion(indices=tuple(range(start, end + 1)), missing_ids=())

    @classmethod
    def from_ids(cls, ids: Sequence[str]) -> "IdSequence":
        return cls(ids)
