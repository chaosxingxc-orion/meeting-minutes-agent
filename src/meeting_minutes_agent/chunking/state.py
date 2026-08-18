"""Inter-chunk glossary-state interface.

An episode-local, APPEND-ONLY sequence of content-hashed state entries
(standard-scheme SS4.6 discipline: never rewrite; a correction appends a
successor entry naming the hash of the entry it supersedes). This module
owns the append-only discipline and the hash chain; it is generic over an
opaque JSON-serializable ``payload`` -- the glossary module decides what a
payload actually contains (e.g. a serialized set of
``glossary.models.GlossaryEntry`` dicts).

``GlossaryStateLog`` is itself an immutable, frozen dataclass: ``append``
never mutates ``self``, it returns a NEW log with one more entry. There is
no method that removes or edits an existing entry, and ``entries`` is a
plain tuple, so both direct item assignment and reassigning the ``entries``
field raise on their own -- "append-only" is a structural guarantee, not a
convention enforced by discipline alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..runreceipt import config_hash


def _entry_hash(
    seq: int,
    chunk_index: int,
    payload: Mapping[str, Any],
    previous_hash: str | None,
    supersedes: str | None,
) -> str:
    return config_hash(
        {
            "seq": seq,
            "chunk_index": chunk_index,
            "payload": dict(payload),
            "previous_hash": previous_hash,
            "supersedes": supersedes,
        }
    )


@dataclass(frozen=True)
class StateEntry:
    seq: int
    chunk_index: int
    payload: Mapping[str, Any]
    previous_hash: str | None
    supersedes: str | None
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "chunk_index": self.chunk_index,
            "payload": dict(self.payload),
            "previous_hash": self.previous_hash,
            "supersedes": self.supersedes,
            "entry_hash": self.entry_hash,
        }


@dataclass(frozen=True)
class GlossaryStateLog:
    entries: tuple[StateEntry, ...] = field(default_factory=tuple)

    def append(
        self,
        payload: Mapping[str, Any],
        *,
        chunk_index: int,
        supersedes: str | None = None,
    ) -> "GlossaryStateLog":
        """Return a NEW log with one more entry. If ``supersedes`` is
        given, it must name an existing entry's ``entry_hash`` -- a
        correction can only supersede a real prior entry, never rewrite
        one, and never dangle."""

        if supersedes is not None:
            known = {e.entry_hash for e in self.entries}
            if supersedes not in known:
                raise ValueError(f"cannot supersede unknown entry hash: {supersedes!r}")

        seq = len(self.entries)
        previous_hash = self.entries[-1].entry_hash if self.entries else None
        entry_hash = _entry_hash(seq, chunk_index, payload, previous_hash, supersedes)
        new_entry = StateEntry(
            seq=seq,
            chunk_index=chunk_index,
            payload=dict(payload),
            previous_hash=previous_hash,
            supersedes=supersedes,
            entry_hash=entry_hash,
        )
        return GlossaryStateLog(entries=self.entries + (new_entry,))

    def active_entries(self) -> tuple[StateEntry, ...]:
        """Entries not named as ``supersedes`` by any later entry, in
        append order -- the resolved state after every correction so far."""

        superseded = {e.supersedes for e in self.entries if e.supersedes is not None}
        return tuple(e for e in self.entries if e.entry_hash not in superseded)

    def verify_chain(self) -> bool:
        """True iff every entry's ``previous_hash`` matches the prior
        entry's ``entry_hash`` and every ``entry_hash`` recomputes
        correctly from its own fields -- a tamper/consistency check."""

        prev_hash: str | None = None
        for e in self.entries:
            if e.previous_hash != prev_hash:
                return False
            if _entry_hash(e.seq, e.chunk_index, e.payload, e.previous_hash, e.supersedes) != e.entry_hash:
                return False
            prev_hash = e.entry_hash
        return True
