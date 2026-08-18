"""``EpisodeState``: the single per-episode state aggregate (component C3,
``docs/plans/2026-08-18-agent-backbone-and-layout.md`` component inventory).

Three parts, none reimplemented here that already exist elsewhere:

- **glossary** -- a plain ``tuple[GlossaryEntry, ...]``, folded chunk by
  chunk via :func:`meeting_minutes_agent.glossary.accumulate.merge_entries`
  (reused, not duplicated).
- **speaker map** -- one
  :class:`~meeting_minutes_agent.chunking.state.GlossaryStateLog` (reused
  from the chunking module's generic append-only/content-hashed/
  supersede-by-hash state interface), storing one
  :class:`~.models.SpeakerBinding`'s fields per entry.
- **decision/action ledger** -- a second, independent
  :class:`~meeting_minutes_agent.chunking.state.GlossaryStateLog` instance,
  storing one :class:`~.models.LedgerRecord`'s fields per entry.

``EpisodeState`` is itself a frozen dataclass: every mutator (``with_*``,
``bind_speaker``, ``add_ledger_entry``) returns a NEW state, exactly the same
non-destructive discipline ``GlossaryStateLog.append`` already uses.
:meth:`content_hash` / :meth:`snapshot` give a content-hashable snapshot at
any chunk boundary; :meth:`to_dict` / :meth:`from_dict` round-trip the whole
aggregate through plain JSON-safe data.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..chunking.state import GlossaryStateLog, StateEntry
from ..glossary.accumulate import merge_entries
from ..glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag
from ..runreceipt import config_hash
from .models import LedgerEntryKind, LedgerRecord, SpeakerBinding, SpeakerEvidenceSource


def _state_entry_from_dict(d: Mapping[str, Any]) -> StateEntry:
    """Reconstruct a :class:`StateEntry` from its own ``to_dict()`` shape,
    WITHOUT recomputing ``entry_hash`` -- a round-trip must reproduce the
    exact stored hash, not merely a hash that would currently recompute the
    same way (the two coincide today, but reconstruction should not depend
    on that: it is loading a record, not re-deriving one)."""

    return StateEntry(
        seq=d["seq"],
        chunk_index=d["chunk_index"],
        payload=dict(d["payload"]),
        previous_hash=d["previous_hash"],
        supersedes=d["supersedes"],
        entry_hash=d["entry_hash"],
    )


def _glossary_entry_from_dict(d: Mapping[str, Any]) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=d["canonical_surface"],
        variants=tuple(d["variants"]),
        first_seen_chunk=d["first_seen_chunk"],
        evidence_count=d["evidence_count"],
        provenance=ProvenanceTag(d["provenance"]),
        leakage_tier=LeakageTier(d["leakage_tier"]),
        introduced_by=d.get("introduced_by"),
    )


@dataclass(frozen=True)
class EpisodeStateSnapshot:
    """A compact, content-hashable record of the episode state as of one
    chunk boundary -- cheap to log/compare per chunk without serializing the
    full aggregate every time."""

    chunk_index: int
    content_hash: str
    glossary_size: int
    speaker_binding_count: int
    ledger_entry_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "content_hash": self.content_hash,
            "glossary_size": self.glossary_size,
            "speaker_binding_count": self.speaker_binding_count,
            "ledger_entry_count": self.ledger_entry_count,
        }


@dataclass(frozen=True)
class EpisodeState:
    glossary: tuple[GlossaryEntry, ...] = ()
    speaker_log: GlossaryStateLog = field(default_factory=GlossaryStateLog)
    ledger_log: GlossaryStateLog = field(default_factory=GlossaryStateLog)

    # ------------------------------------------------------------------
    # glossary
    # ------------------------------------------------------------------

    def with_glossary_chunk(self, new_entries: Sequence[GlossaryEntry]) -> "EpisodeState":
        """Fold one chunk's freshly-gated entries into the accumulated
        glossary via :func:`~meeting_minutes_agent.glossary.accumulate.merge_entries`.
        Returns a NEW state; ``self`` is untouched."""

        merged = merge_entries(self.glossary, new_entries)
        return dataclasses.replace(self, glossary=merged)

    # ------------------------------------------------------------------
    # speaker map
    # ------------------------------------------------------------------

    def bind_speaker(
        self,
        *,
        cluster_id: str,
        roster_name: str,
        source: SpeakerEvidenceSource,
        chunk: int,
        quote: str,
        supersedes: str | None = None,
    ) -> "EpisodeState":
        """Append one speaker-map evidence record. ``supersedes``, when
        given, must name the ``entry_hash`` of a real prior speaker-log
        entry (``GlossaryStateLog.append``'s own fail-closed check) -- the
        way a wrong earlier binding is corrected, never overwritten."""

        payload = {
            "cluster_id": cluster_id,
            "roster_name": roster_name,
            "source": source.value,
            "quote": quote,
        }
        new_log = self.speaker_log.append(payload, chunk_index=chunk, supersedes=supersedes)
        return dataclasses.replace(self, speaker_log=new_log)

    def active_speaker_bindings(self) -> tuple[SpeakerBinding, ...]:
        """Every currently-active (not superseded) speaker-map entry, in
        append (``seq``) order."""

        return tuple(
            SpeakerBinding(
                cluster_id=e.payload["cluster_id"],
                roster_name=e.payload["roster_name"],
                source=SpeakerEvidenceSource(e.payload["source"]),
                chunk=e.chunk_index,
                quote=e.payload["quote"],
                entry_hash=e.entry_hash,
            )
            for e in self.speaker_log.active_entries()
        )

    def resolve_speaker(self, cluster_id: str) -> SpeakerBinding | None:
        """The current believed binding for ``cluster_id``, or ``None`` if
        no active entry names it.

        Resolution rule (a merge policy the mission spec left implicit for
        the case of two-or-more still-active bindings on the same cluster
        id -- resolved here, stated explicitly for coordinator review): the
        LATEST active entry (highest ``seq``) wins. This covers both
        legitimate uses uniformly -- repeated CONFIRMING evidence for the
        same name (harmless which one "wins", they agree) and an
        uncorrected CONFLICTING re-binding (the most recent read is taken
        as current). A binding believed genuinely wrong should be retracted
        with an explicit ``supersedes`` rather than left active to lose a
        recency tie silently.
        """

        matches = tuple(b for b in self.active_speaker_bindings() if b.cluster_id == cluster_id)
        return matches[-1] if matches else None

    # ------------------------------------------------------------------
    # decision / action ledger
    # ------------------------------------------------------------------

    def add_ledger_entry(
        self,
        *,
        kind: LedgerEntryKind,
        text: str,
        owner_speaker: str | None,
        chunk: int,
        evidence_span_refs: Sequence[str] = (),
        supersedes: str | None = None,
    ) -> "EpisodeState":
        """Append one decision/action ledger row."""

        payload = {
            "kind": kind.value,
            "text": text,
            "owner_speaker": owner_speaker,
            "evidence_span_refs": list(evidence_span_refs),
        }
        new_log = self.ledger_log.append(payload, chunk_index=chunk, supersedes=supersedes)
        return dataclasses.replace(self, ledger_log=new_log)

    def active_ledger_entries(self) -> tuple[LedgerRecord, ...]:
        """Every currently-active (not superseded) ledger entry, in append
        (``seq``) order."""

        return tuple(
            LedgerRecord(
                kind=LedgerEntryKind(e.payload["kind"]),
                text=e.payload["text"],
                owner_speaker=e.payload["owner_speaker"],
                chunk=e.chunk_index,
                evidence_span_refs=tuple(e.payload["evidence_span_refs"]),
                entry_hash=e.entry_hash,
            )
            for e in self.ledger_log.active_entries()
        )

    # ------------------------------------------------------------------
    # serialization / hashing
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "glossary": [e.to_dict() for e in self.glossary],
            "speaker_log": [e.to_dict() for e in self.speaker_log.entries],
            "ledger_log": [e.to_dict() for e in self.ledger_log.entries],
        }

    @staticmethod
    def from_dict(d: Mapping[str, Any]) -> "EpisodeState":
        glossary = tuple(_glossary_entry_from_dict(g) for g in d.get("glossary", ()))
        speaker_log = GlossaryStateLog(
            entries=tuple(_state_entry_from_dict(e) for e in d.get("speaker_log", ()))
        )
        ledger_log = GlossaryStateLog(
            entries=tuple(_state_entry_from_dict(e) for e in d.get("ledger_log", ()))
        )
        return EpisodeState(glossary=glossary, speaker_log=speaker_log, ledger_log=ledger_log)

    def content_hash(self) -> str:
        """SHA-256 over the canonical-JSON form of :meth:`to_dict` (via
        :func:`meeting_minutes_agent.runreceipt.config_hash`) -- the whole
        aggregate's content hash at this point in the episode."""

        return config_hash(self.to_dict())

    def snapshot(self, chunk_index: int) -> EpisodeStateSnapshot:
        """A compact :class:`EpisodeStateSnapshot` for chunk boundary
        ``chunk_index``, taken from this state's CURRENT content (the
        caller is responsible for calling this right after folding in that
        chunk's REVISE-stage output -- this method does not itself inspect
        which entries came from which chunk)."""

        return EpisodeStateSnapshot(
            chunk_index=chunk_index,
            content_hash=self.content_hash(),
            glossary_size=len(self.glossary),
            speaker_binding_count=len(self.active_speaker_bindings()),
            ledger_entry_count=len(self.active_ledger_entries()),
        )


__all__ = ["EpisodeState", "EpisodeStateSnapshot"]
