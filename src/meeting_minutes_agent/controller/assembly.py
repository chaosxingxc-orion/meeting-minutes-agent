"""Product assembly (component C7, backbone design doc SS5.1 "Product
assembly: the minutes state machine ... consuming the episode state and
head outputs"): folds accumulated
:class:`~meeting_minutes_agent.heads.minutes.MinutesParseResult`\\ s into
the four-section minutes artifact, and the accumulated resolved transcript
segments into the attributed-transcript artifact. Both are content-hashed
via :mod:`meeting_minutes_agent.runreceipt`.

Pure functions over plain data -- no openJiuwen import, no model contact,
no I/O. :mod:`.loop`/:mod:`meeting_minutes_agent.harness.episode` call
these once the episode workflow has produced its
:class:`~meeting_minutes_agent.heads.minutes.MinutesParseResult`\\ s and
resolved segments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..chunking.models import SegmentLike
from ..corpora.nxt.models import MINUTES_SECTIONS
from ..heads.minutes import MinutesBulletClaim, MinutesParseResult
from ..metrics.saer_m import SaerMReport, SpeakerAttributionPrediction, compute_saer_m
from ..runreceipt import config_hash


@dataclass(frozen=True)
class MinutesArtifact:
    """The four-section minutes artifact: one bullet tuple per section (in
    :data:`~meeting_minutes_agent.corpora.nxt.models.MINUTES_SECTIONS`
    order), plus the exact
    :class:`~meeting_minutes_agent.metrics.saer_m.SpeakerAttributionPrediction`
    projection every bullet's evidence-link claim already IS (this artifact
    is ``metrics.saer_m``-compatible by construction, not by a separate
    conversion step a caller could forget)."""

    meeting_id: str
    sections: Mapping[str, tuple[MinutesBulletClaim, ...]]
    speaker_attribution_predictions: tuple[SpeakerAttributionPrediction, ...]
    content_hash: str

    def bullets(self) -> tuple[MinutesBulletClaim, ...]:
        return tuple(b for section in MINUTES_SECTIONS for b in self.sections.get(section, ()))

    def score_against(self, evidence_links: Sequence) -> SaerMReport:
        """Convenience: score this artifact's own speaker-attribution
        claims against externally-supplied gold ``evidence_links`` via
        :func:`meeting_minutes_agent.metrics.saer_m.compute_saer_m`."""

        return compute_saer_m(evidence_links, self.speaker_attribution_predictions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "sections": {section: [b.to_dict() for b in bullets] for section, bullets in self.sections.items()},
            "content_hash": self.content_hash,
        }


def build_minutes_artifact(meeting_id: str, minutes_parses: Sequence[MinutesParseResult]) -> MinutesArtifact:
    """Fold zero or more per-task
    :class:`~meeting_minutes_agent.heads.minutes.MinutesParseResult`\\ s
    (v1's loop produces exactly one, from the single ``summarize_section``
    task; the fold itself is written generically -- concatenating each
    section's bullets in ``minutes_parses`` order -- so a future multi-pass
    summarize design needs no change here) into one
    :class:`MinutesArtifact`, deterministically ordered by
    :data:`~meeting_minutes_agent.corpora.nxt.models.MINUTES_SECTIONS`."""

    sections: dict[str, list[MinutesBulletClaim]] = {section: [] for section in MINUTES_SECTIONS}
    for parse in minutes_parses:
        for bullet in parse.bullets:
            if bullet.section in sections:
                sections[bullet.section].append(bullet)

    resolved_sections = {section: tuple(bullets) for section, bullets in sections.items()}
    predictions = tuple(
        SpeakerAttributionPrediction(sentence_id=b.sentence_id, predicted_speaker=b.claimed_speaker)
        for section in MINUTES_SECTIONS
        for b in resolved_sections[section]
    )
    payload = {
        "meeting_id": meeting_id,
        "sections": {section: [b.to_dict() for b in resolved_sections[section]] for section in MINUTES_SECTIONS},
    }
    return MinutesArtifact(
        meeting_id=meeting_id,
        sections=resolved_sections,
        speaker_attribution_predictions=predictions,
        content_hash=config_hash(payload),
    )


@dataclass(frozen=True)
class AttributedTranscriptArtifact:
    """The speaker-attributed transcript artifact: every resolved segment
    accumulated across the episode, in resolution order."""

    meeting_id: str
    segments: tuple[Mapping[str, Any], ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "segments": [dict(s) for s in self.segments],
            "content_hash": self.content_hash,
        }


def build_attributed_transcript_artifact(
    meeting_id: str, resolved_segments: Sequence[SegmentLike]
) -> AttributedTranscriptArtifact:
    """Build the attributed-transcript artifact from every segment resolved
    so far (in resolution order -- the order they were folded into the
    episode, not re-sorted here)."""

    rows = tuple(
        {"id": s.id, "speaker": s.speaker, "start": s.start, "end": s.end, "text": s.text}
        for s in resolved_segments
    )
    payload = {"meeting_id": meeting_id, "segments": [dict(r) for r in rows]}
    return AttributedTranscriptArtifact(
        meeting_id=meeting_id,
        segments=rows,
        content_hash=config_hash(payload),
    )


__all__ = [
    "MinutesArtifact",
    "build_minutes_artifact",
    "AttributedTranscriptArtifact",
    "build_attributed_transcript_artifact",
]
