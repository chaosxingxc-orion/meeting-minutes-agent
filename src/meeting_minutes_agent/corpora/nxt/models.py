"""Record shapes for the NXT reader.

Two tiers:

- "Raw" models are the direct, single-file parse result: ids and unresolved
  :class:`~meeting_minutes_agent.corpora.nxt.pointers.NitePointer`\\ s, no
  cross-file lookups performed yet. Produced by :mod:`parsers`.
- Resolved models (``Word``, ``Utterance``, ``MinutesSentence``,
  ``MinutesStructure``, ``Topic``, ``EvidenceLink``, ``OrphanPointer``,
  ``ResolvedMeeting``) carry concrete text/times after
  :mod:`resolver` has expanded every pointer against the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .pointers import NitePointer

# ---------------------------------------------------------------------------
# Word layer (also the resolved model -- a Word is already fully concrete
# once parsed; there is nothing further to resolve for it).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Word:
    """One id-bearing child of a ``words.xml`` file. ``kind`` is the XML tag
    name (``w``, ``disfmarker``, ``gap``, ``vocalsound``, or -- forward
    compatibly -- whatever else appears); only ``kind == "w"`` carries
    lexical ``text``. Every kind still occupies one slot in the file's id
    sequence, which matters for range expansion (see :mod:`idseq`)."""

    id: str
    kind: str
    text: str | None
    start: float | None
    end: float | None
    punc: bool = False
    vocal_type: str | None = None


# ---------------------------------------------------------------------------
# Raw (single-file, pointer-unresolved) layers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentRaw:
    id: str
    channel: str | None
    start: float | None
    end: float | None
    word_pointers: tuple[NitePointer, ...]


@dataclass(frozen=True)
class DialogueActRaw:
    id: str
    da_type_href: str | None
    word_pointers: tuple[NitePointer, ...]


@dataclass(frozen=True)
class TopicNode:
    """A (possibly nested) raw topic. ``word_pointers`` are this node's OWN
    direct word-range pointers, not including any ``children``'s pointers."""

    id: str
    description: str | None
    type_href: str | None
    word_pointers: tuple[NitePointer, ...]
    children: tuple["TopicNode", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SummlinkRaw:
    id: str
    extractive: NitePointer | None
    abstractive: NitePointer | None


# ---------------------------------------------------------------------------
# Abstractive minutes (no pointers to resolve -- authored text directly)
# ---------------------------------------------------------------------------

MINUTES_SECTIONS: tuple[str, ...] = ("abstract", "actions", "decisions", "problems")


@dataclass(frozen=True)
class MinutesSentence:
    id: str
    section: str
    text: str


@dataclass(frozen=True)
class MinutesStructure:
    meeting_id: str
    sections: Mapping[str, tuple[MinutesSentence, ...]]

    def all_sentences(self) -> tuple[MinutesSentence, ...]:
        out: list[MinutesSentence] = []
        for section in MINUTES_SECTIONS:
            out.extend(self.sections.get(section, ()))
        return tuple(out)


# ---------------------------------------------------------------------------
# Resolved (cross-file, pointer-expanded) models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Utterance:
    """One resolved segment or dialogue act: a speaker-attributed span of
    text with times, reconstructed from its word range(s). Used for both
    the segment-level transcript and the dialogue-act-level transcript --
    the two layers share this shape; ``meta`` carries the layer-specific
    extras (segment ``channel``, or DA ``da_type_href``)."""

    id: str
    speaker: str
    start: float | None
    end: float | None
    text: str
    word_ids: tuple[str, ...]
    meta: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Topic:
    id: str
    description: str | None
    type_href: str | None
    start: float | None
    end: float | None
    text: str
    word_ids: tuple[str, ...]
    children: tuple["Topic", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceLink:
    """One ``summlink`` entry resolved end to end: an abstractive minutes
    sentence, and the extractive dialogue act(s) (usually exactly one --
    AMI's summlink pointers are never observed as ranges, but the extractive
    side is modelled as a tuple defensively) that support it, expanded down
    to their supporting word span."""

    id: str
    sentence_id: str
    section: str
    sentence_text: str
    da_ids: tuple[str, ...]
    speaker: str
    start: float | None
    end: float | None
    text: str
    word_ids: tuple[str, ...]


@dataclass(frozen=True)
class OrphanPointer:
    """A pointer that failed to resolve: either the target file was not
    found under the corpus root, or an id inside it was not found. Recorded
    rather than raised, so a caller can assert "zero orphans" as a fact
    about the meetings it resolves instead of the resolver being fragile to
    isolated corpus gaps elsewhere."""

    source_file: str
    source_id: str
    target_href: str
    reason: str


@dataclass(frozen=True)
class ResolvedMeeting:
    meeting_id: str
    transcript: tuple[Utterance, ...]
    dialogue_acts: tuple[Utterance, ...]
    minutes: MinutesStructure | None
    evidence_links: tuple[EvidenceLink, ...]
    topics: tuple[Topic, ...]
    orphans: tuple[OrphanPointer, ...]
