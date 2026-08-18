"""Resolved record shapes for the episode state store.

Two typed views the episode holds, both built on top of the SAME generic,
append-only, content-hashed log primitive
:class:`meeting_minutes_agent.chunking.state.GlossaryStateLog` (that module's
own docstring: "generic over an opaque JSON-serializable payload"; the
episode state store reuses it rather than reimplementing the append-only /
supersede-by-hash discipline a second time):

- **speaker map**: cluster id <-> roster name bindings, each carrying one
  evidence record (``source``, ``chunk``, ``quote``). A binding is one log
  entry; the log's own supersede-by-hash mechanism is how a wrong binding
  is corrected.
- **decision/action ledger**: typed entries (``kind``, ``text``,
  ``owner_speaker``, ``chunk``, ``evidence_span_refs``), append-only the
  same way.

:class:`SpeakerBinding` and :class:`LedgerRecord` are the RESOLVED, read-only
views :mod:`.episode` reconstructs from active log entries; they are never
constructed directly from user input and never themselves appended to a log
(the log stores their fields as a plain JSON-safe payload dict instead --
see :meth:`.episode.EpisodeState.bind_speaker` /
:meth:`.episode.EpisodeState.add_ledger_entry`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SpeakerEvidenceSource(str, Enum):
    """Where a speaker-map binding's evidence came from."""

    SELF_INTRODUCTION = "self-introduction"
    ROSTER_MATCH = "roster-match"
    MANUAL = "manual"


@dataclass(frozen=True)
class SpeakerBinding:
    """One resolved cluster-id -> roster-name assertion, reconstructed from
    one ACTIVE speaker-log entry. ``entry_hash`` is that entry's own hash --
    the value a later correction's ``supersedes`` would name to retract this
    exact binding."""

    cluster_id: str
    roster_name: str
    source: SpeakerEvidenceSource
    chunk: int
    quote: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "roster_name": self.roster_name,
            "source": self.source.value,
            "chunk": self.chunk,
            "quote": self.quote,
            "entry_hash": self.entry_hash,
        }


class LedgerEntryKind(str, Enum):
    """The two typed rows the decision/action ledger holds."""

    DECISION = "decision"
    ACTION = "action"


@dataclass(frozen=True)
class LedgerRecord:
    """One resolved decision/action ledger row, reconstructed from one
    ACTIVE ledger-log entry. ``evidence_span_refs`` names the transcript
    span id(s) (e.g. chunking ``Segment.id`` / corpora ``Utterance.id``)
    that support this record; it may be empty when no single span was
    identified."""

    kind: LedgerEntryKind
    text: str
    owner_speaker: str | None
    chunk: int
    evidence_span_refs: tuple[str, ...]
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "owner_speaker": self.owner_speaker,
            "chunk": self.chunk,
            "evidence_span_refs": list(self.evidence_span_refs),
            "entry_hash": self.entry_hash,
        }


__all__ = [
    "SpeakerEvidenceSource",
    "SpeakerBinding",
    "LedgerEntryKind",
    "LedgerRecord",
]
