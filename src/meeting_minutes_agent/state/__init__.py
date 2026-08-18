"""E7a -- episode state store (component C3).

A single :class:`~.episode.EpisodeState` aggregate holding the glossary
accumulation (reusing :mod:`meeting_minutes_agent.glossary`), the speaker
map, and the decision/action ledger. The speaker map and ledger both reuse
:class:`meeting_minutes_agent.chunking.state.GlossaryStateLog` -- the
append-only, content-hashed, supersede-by-hash log the chunking module
already defines generically -- rather than a second implementation of the
same discipline. See :mod:`.models` for the resolved record shapes and
:mod:`.episode` for the aggregate itself.
"""

from __future__ import annotations

from .episode import EpisodeState, EpisodeStateSnapshot
from .models import LedgerEntryKind, LedgerRecord, SpeakerBinding, SpeakerEvidenceSource

__all__ = [
    "EpisodeState",
    "EpisodeStateSnapshot",
    "LedgerEntryKind",
    "LedgerRecord",
    "SpeakerBinding",
    "SpeakerEvidenceSource",
]
