"""``minutes`` head: the four-section minutes request builder + parser
(component C6). Builds the minutes request over the accumulated
:class:`~meeting_minutes_agent.state.episode.EpisodeState` plus the
resolved transcript, and parses the reply's abstract/actions/decisions/
problems sections and per-bullet evidence-link claims into
:mod:`meeting_minutes_agent.metrics.saer_m`-compatible structures.

Section names/order are reused directly from
:data:`meeting_minutes_agent.corpora.nxt.models.MINUTES_SECTIONS` -- the
same four-section vocabulary the NXT corpus reader already resolves gold
minutes into -- rather than a second, possibly-drifting definition of what
the four sections are called.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from ..chunking.models import SegmentLike
from ..corpora.nxt.models import MINUTES_SECTIONS
from ..metrics.saer_m import SpeakerAttributionPrediction
from ..runreceipt import config_hash
from .request import HeadRequest, build_supplied_text

TEMPLATE_ID = "minutes-v1"

SECTION_HEADERS: dict[str, str] = {
    "abstract": "ABSTRACT:",
    "actions": "ACTIONS:",
    "decisions": "DECISIONS:",
    "problems": "PROBLEMS:",
}
assert tuple(SECTION_HEADERS) == MINUTES_SECTIONS

_HEADER_TO_SECTION = {header: section for section, header in SECTION_HEADERS.items()}

SYSTEM_INSTRUCTION_TEMPLATE = (
    "Produce meeting minutes for the episode so far from the resolved "
    "transcript and the known terms / speaker map supplied below. Output "
    "EXACTLY four sections, each starting on its own line with one of "
    "these exact headers, in this order: "
    "ABSTRACT:, ACTIONS:, DECISIONS:, PROBLEMS:. Under each header, list "
    "one bullet per line starting with '- '. End every bullet line with an "
    "evidence tag in the exact form ' [evidence: <speaker>|<span_id>]' "
    "naming the speaker and transcript span id that supports the "
    "statement, or ' [evidence: none]' if no single span supports it. "
    "Output ONLY the four sections; no extra commentary."
)

TEMPLATE_SHA256 = config_hash({"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION_TEMPLATE})

TRANSCRIPT_SECTION_HEADER = "=== TRANSCRIPT ==="


@dataclass(frozen=True)
class MinutesBulletClaim:
    """One parsed minutes bullet. ``sentence_id`` is synthesized as
    ``"<section>-<index>"`` (0-based, per-section index in reply order) --
    this head's own minutes have no corpus-assigned sentence id yet, unlike
    :class:`~meeting_minutes_agent.corpora.nxt.models.MinutesSentence`.
    ``claimed_speaker`` / ``claimed_span_id`` come from the bullet's own
    evidence tag; either may be ``None`` (an explicit ``none`` tag, or a
    bullet with no parseable tag at all)."""

    section: str
    sentence_id: str
    text: str
    claimed_speaker: str | None
    claimed_span_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "sentence_id": self.sentence_id,
            "text": self.text,
            "claimed_speaker": self.claimed_speaker,
            "claimed_span_id": self.claimed_span_id,
        }


@dataclass(frozen=True)
class MinutesParseResult:
    """``parse_mode`` is ``"strict"`` when all four section headers were
    seen, every non-blank line under a header parsed as a bullet, and no
    content appeared before the first header; ``"lenient"`` when at least
    one bullet parsed despite some imperfection (a missing section, a
    malformed line, content before the first header); ``"failed"`` when no
    bullet parsed at all. Never raises."""

    bullets: tuple[MinutesBulletClaim, ...]
    parse_mode: str  # "strict" | "lenient" | "failed"
    malformed_lines: tuple[str, ...]
    missing_sections: tuple[str, ...]
    raw_text: str

    def speaker_attribution_predictions(self) -> tuple[SpeakerAttributionPrediction, ...]:
        """This parse result's bullets ARE
        :mod:`meeting_minutes_agent.metrics.saer_m`'s prediction input, by
        construction: one :class:`SpeakerAttributionPrediction` per bullet,
        naming its claimed speaker (``None`` if the bullet made no
        attribution claim) and carrying its own bullet ``text`` (SAER-M
        definition v1.1: this head's ``sentence_id`` is a synthesized
        ``"<section>-<index>"``, never a corpus id, so ``text`` is what
        ``metrics.saer_m.align_predictions_to_gold_sentences`` content-
        matches against a gold sentence -- see that module's docstring)."""

        return tuple(
            SpeakerAttributionPrediction(sentence_id=b.sentence_id, predicted_speaker=b.claimed_speaker, text=b.text)
            for b in self.bullets
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bullets": [b.to_dict() for b in self.bullets],
            "parse_mode": self.parse_mode,
            "malformed_lines": list(self.malformed_lines),
            "missing_sections": list(self.missing_sections),
            "raw_text": self.raw_text,
        }


def build_minutes_request(
    *,
    supply_text: str,
    resolved_transcript: Sequence[SegmentLike] = (),
    decoding_params: dict[str, object] | None = None,
) -> HeadRequest:
    """``supply_text`` is the rendered
    :class:`meeting_minutes_agent.supply.render.SupplyBlock`'s ``.text``
    (accepted pre-rendered, same dependency-direction reasoning as
    :mod:`.transcribe_attribute`). ``resolved_transcript`` supplies each
    span's id and speaker so the requested evidence tags
    (``speaker|span_id``) can name something real; any
    :class:`~meeting_minutes_agent.chunking.models.SegmentLike` sequence
    works, including an already-resolved
    :class:`~meeting_minutes_agent.corpora.nxt.models.Utterance` sequence."""

    transcript_lines = [f"[{u.id}|{u.speaker}] {u.text}" for u in resolved_transcript]
    transcript_block = (TRANSCRIPT_SECTION_HEADER + "\n" + "\n".join(transcript_lines)) if transcript_lines else None
    supplied_text = build_supplied_text(supply_text, transcript_block)
    return HeadRequest(
        task_instruction=SYSTEM_INSTRUCTION_TEMPLATE,
        supplied_text=supplied_text,
        decoding_params=dict(decoding_params or {}),
        template_id=TEMPLATE_ID,
        template_sha256=TEMPLATE_SHA256,
    )


_BULLET_RE = re.compile(r"^-\s*(?P<body>.+)$")
_EVIDENCE_RE = re.compile(r"\[evidence:\s*(?P<value>[^\]]*)\]\s*$")


def _parse_bullet_body(body: str) -> tuple[str, str | None, str | None]:
    """Split ``body`` (the bullet text after ``'- '``) into
    ``(text, claimed_speaker, claimed_span_id)``. A missing or malformed
    evidence tag degrades to ``(body, None, None)`` rather than failing the
    whole bullet -- text with no evidence claim is still a real bullet."""

    match = _EVIDENCE_RE.search(body)
    if not match:
        return body.strip(), None, None
    text = body[: match.start()].strip()
    value = match.group("value").strip()
    if not value or value == "none":
        return text, None, None
    if "|" in value:
        speaker, _, span_id = value.partition("|")
        return text, (speaker.strip() or None), (span_id.strip() or None)
    return text, value, None


def parse_minutes_response(raw_text: str) -> MinutesParseResult:
    """Never raises. Scans line by line: a line that exactly matches (after
    stripping) one of :data:`SECTION_HEADERS`'s values switches the current
    section; a bullet line (``'- ...'``) under a current section parses via
    :func:`_parse_bullet_body`; anything else (a non-bullet line under a
    section, or ANY non-blank line before the first header) is recorded in
    ``malformed_lines``, never raised."""

    current_section: str | None = None
    seen_sections: set[str] = set()
    counters: dict[str, int] = {}
    bullets: list[MinutesBulletClaim] = []
    malformed: list[str] = []
    had_violation = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in _HEADER_TO_SECTION:
            current_section = _HEADER_TO_SECTION[line]
            seen_sections.add(current_section)
            counters.setdefault(current_section, 0)
            continue
        if current_section is None:
            malformed.append(raw_line)
            had_violation = True
            continue
        bullet_match = _BULLET_RE.match(line)
        if not bullet_match:
            malformed.append(raw_line)
            had_violation = True
            continue
        text, speaker, span_id = _parse_bullet_body(bullet_match.group("body"))
        index = counters[current_section]
        counters[current_section] = index + 1
        bullets.append(
            MinutesBulletClaim(
                section=current_section,
                sentence_id=f"{current_section}-{index}",
                text=text,
                claimed_speaker=speaker,
                claimed_span_id=span_id,
            )
        )

    missing_sections = tuple(s for s in MINUTES_SECTIONS if s not in seen_sections)
    if missing_sections:
        had_violation = True

    if bullets and not had_violation:
        mode = "strict"
    elif bullets:
        mode = "lenient"
    else:
        mode = "failed"

    return MinutesParseResult(
        bullets=tuple(bullets),
        parse_mode=mode,
        malformed_lines=tuple(malformed),
        missing_sections=missing_sections,
        raw_text=raw_text,
    )


__all__ = [
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "SECTION_HEADERS",
    "MinutesBulletClaim",
    "MinutesParseResult",
    "build_minutes_request",
    "parse_minutes_response",
]
