"""``transcribe_attribute`` head: the LISTEN-stage request builder + parser
(component C6). Builds the per-chunk transcribe+attribute request (system
instruction + supply block + speaker-tagged span context) and parses the
core's reply into per-segment ``{speaker, text}`` records.

Parsing is a strict-parse + lenient-fallback PAIR, per mission scope: a
malformed reply is DATA on the returned :class:`TranscribeAttributeParseResult`
(``malformed_lines``), never a raised exception -- a head has no business
deciding that one bad line should abort an entire chunk's transcript; that
policy call belongs to whatever consumes the parse result (a future E7
controller).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from ..chunking.models import SegmentLike
from ..runreceipt import config_hash
from .request import HeadRequest, build_supplied_text

TEMPLATE_ID = "transcribe-attribute-v1"

SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are transcribing and attributing one chunk of a multi-speaker "
    "meeting recording. Produce one line per speech segment in EXACTLY "
    "this format:\n"
    "<speaker>|<text>\n"
    "Use the KNOWN TERMS spelling and SPEAKER MAP roster names supplied "
    "below when confident; otherwise use the raw speaker cluster id from "
    "the CONTEXT section. Output ONLY these lines, one segment per line, "
    "with no extra commentary before, between, or after them."
)

TEMPLATE_SHA256 = config_hash({"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION_TEMPLATE})

CONTEXT_SECTION_HEADER = "=== CONTEXT (prior spans) ==="


@dataclass(frozen=True)
class TranscribedSegment:
    speaker: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"speaker": self.speaker, "text": self.text}


@dataclass(frozen=True)
class TranscribeAttributeParseResult:
    """``parse_mode`` is ``"strict"`` when every non-empty line parsed under
    the strict ``speaker|text`` grammar; ``"lenient"`` when at least one
    segment parsed but only via a fallback pattern or after skipping some
    lines; ``"failed"`` when nothing parsed at all. ``malformed_lines`` is
    always the exact set of input lines that could not be parsed even
    leniently -- present regardless of ``parse_mode``, so a caller can
    inspect near-misses even on an overall ``"strict"`` result (there are
    none, by definition of strict) or a ``"lenient"`` one."""

    segments: tuple[TranscribedSegment, ...]
    parse_mode: str  # "strict" | "lenient" | "failed"
    malformed_lines: tuple[str, ...]
    raw_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "parse_mode": self.parse_mode,
            "malformed_lines": list(self.malformed_lines),
            "raw_text": self.raw_text,
        }


def build_transcribe_attribute_request(
    *,
    supply_text: str,
    span_context: Sequence[SegmentLike] = (),
    decoding_params: dict[str, object] | None = None,
) -> HeadRequest:
    """``supply_text`` is the rendered
    :class:`meeting_minutes_agent.supply.render.SupplyBlock`'s ``.text``
    (this head does not import :mod:`meeting_minutes_agent.supply` itself --
    it accepts the already-rendered string, keeping the dependency direction
    supply -> heads, never the reverse). ``span_context`` is prior
    speaker-tagged spans (e.g. the chunking module's own ``Segment``, or any
    other :class:`~meeting_minutes_agent.chunking.models.SegmentLike`) given
    as context for continuity across a chunk boundary."""

    context_lines = [f"[{s.speaker}] {s.text}" for s in span_context]
    context_block = (CONTEXT_SECTION_HEADER + "\n" + "\n".join(context_lines)) if context_lines else None
    supplied_text = build_supplied_text(supply_text, context_block)
    return HeadRequest(
        task_instruction=SYSTEM_INSTRUCTION_TEMPLATE,
        supplied_text=supplied_text,
        decoding_params=dict(decoding_params or {}),
        template_id=TEMPLATE_ID,
        template_sha256=TEMPLATE_SHA256,
    )


_STRICT_LINE_RE = re.compile(r"^(?P<speaker>[^|]+)\|(?P<text>.+)$")
_LENIENT_BRACKET_RE = re.compile(r"^\[(?P<speaker>[^\]]+)\]\s*(?P<text>.+)$")
_LENIENT_COLON_RE = re.compile(r"^(?P<speaker>[A-Za-z0-9 _.\-]{1,40}?):\s*(?P<text>.+)$")


def _strict_parse_line(line: str) -> TranscribedSegment | None:
    match = _STRICT_LINE_RE.match(line)
    if not match:
        return None
    speaker = match.group("speaker").strip()
    text = match.group("text").strip()
    if not speaker or not text:
        return None
    return TranscribedSegment(speaker=speaker, text=text)


def _lenient_parse_line(line: str) -> TranscribedSegment | None:
    for pattern in (_LENIENT_BRACKET_RE, _LENIENT_COLON_RE):
        match = pattern.match(line)
        if match:
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            if speaker and text:
                return TranscribedSegment(speaker=speaker, text=text)
    return None


def parse_transcribe_attribute_response(raw_text: str) -> TranscribeAttributeParseResult:
    """Never raises. Tries the strict ``speaker|text`` grammar on every
    non-blank line first; if that fully succeeds (and produced at least one
    segment), returns ``parse_mode="strict"``. Otherwise re-parses every
    line with strict-then-lenient fallback, collecting whatever DID parse
    into ``segments`` and whatever did NOT into ``malformed_lines``
    (returned as data)."""

    lines = [line for line in raw_text.splitlines() if line.strip()]

    strict_segments: list[TranscribedSegment] = []
    strict_ok = True
    for line in lines:
        segment = _strict_parse_line(line)
        if segment is None:
            strict_ok = False
            break
        strict_segments.append(segment)

    if strict_ok and strict_segments:
        return TranscribeAttributeParseResult(
            segments=tuple(strict_segments), parse_mode="strict", malformed_lines=(), raw_text=raw_text
        )

    lenient_segments: list[TranscribedSegment] = []
    malformed: list[str] = []
    for line in lines:
        segment = _strict_parse_line(line) or _lenient_parse_line(line)
        if segment is not None:
            lenient_segments.append(segment)
        else:
            malformed.append(line)

    mode = "lenient" if lenient_segments else "failed"
    return TranscribeAttributeParseResult(
        segments=tuple(lenient_segments), parse_mode=mode, malformed_lines=tuple(malformed), raw_text=raw_text
    )


__all__ = [
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "TranscribedSegment",
    "TranscribeAttributeParseResult",
    "build_transcribe_attribute_request",
    "parse_transcribe_attribute_response",
]
