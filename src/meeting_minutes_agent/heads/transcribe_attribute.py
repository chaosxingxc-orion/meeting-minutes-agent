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

Two additional pieces support the P-ATTR capability smoke
(``docs/readiness/2026-08-18-g1-preregistration-draft.md`` SS0,
:mod:`meeting_minutes_agent.probes.pattr`):

- :func:`build_declared_grid_block` / the ``declared_grid_turns`` parameter
  on :func:`build_transcribe_attribute_request` -- an OPTIONAL, additional
  supplied-text part carrying the declared per-slice turn/speaker grid (the
  A-grid arm). Deliberately NOT folded into ``SYSTEM_INSTRUCTION_TEMPLATE``
  itself (that would change ``TEMPLATE_ID``/``TEMPLATE_SHA256``, which are
  pinned by :mod:`tests.unit.heads.test_transcribe_attribute`): the grid is
  just another supplied-text block, exactly like the context block below,
  so A-grid and A-free share one template identity and differ ONLY in
  whether this block is present -- the smoke's entire point.
- :data:`TRANSCRIBE_ONLY_TEMPLATE_ID` / :func:`build_transcribe_only_request`
  / :func:`parse_transcribe_only_response` -- a separate, simpler template
  variant with NO attribution instruction at all (the A-turn arm): the
  caller already knows the single speaker for a per-turn audio cut from the
  frozen manifest, by construction, so the model is asked to transcribe
  only, never to label a speaker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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

DECLARED_GRID_SECTION_HEADER = (
    "=== DECLARED SPEAKER GRID (attribute the segments you produce to these "
    "speaker labels, in this order) ==="
)


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


def build_declared_grid_block(turns: Sequence[Mapping[str, Any]]) -> str | None:
    """Render the P-ATTR A-grid arm's declared per-slice turn/speaker grid
    as one supplied-text block, or ``None`` for an empty/absent grid (the
    A-free arm's own "minus the grid" case). ``turns`` is the manifest's
    own per-slice turn-table shape (``{"speaker", "slice_offset_start",
    "slice_offset_end", ...}``, exactly
    :meth:`meeting_minutes_agent.chunking.slicer.SliceTurnEntry.to_dict`'s
    output, or any mapping carrying those three keys) -- this function
    takes plain mappings, not the slicer's own dataclass, so this module
    stays decoupled from :mod:`meeting_minutes_agent.chunking.slicer`.

    Lines are numbered by POSITION/ORDER, not by any id in ``turns`` --
    that ordering is exactly what
    :func:`meeting_minutes_agent.probes.pattr_scoring.boundary_respect_diagnostic`
    later checks a parsed reply's segments against, position for position.
    """

    if not turns:
        return None
    lines = [
        f"[{i}] {float(t['slice_offset_start']):.2f}-{float(t['slice_offset_end']):.2f} {t['speaker']}"
        for i, t in enumerate(turns)
    ]
    return DECLARED_GRID_SECTION_HEADER + "\n" + "\n".join(lines)


def build_transcribe_attribute_request(
    *,
    supply_text: str,
    span_context: Sequence[SegmentLike] = (),
    declared_grid_turns: Sequence[Mapping[str, Any]] = (),
    decoding_params: dict[str, object] | None = None,
) -> HeadRequest:
    """``supply_text`` is the rendered
    :class:`meeting_minutes_agent.supply.render.SupplyBlock`'s ``.text``
    (this head does not import :mod:`meeting_minutes_agent.supply` itself --
    it accepts the already-rendered string, keeping the dependency direction
    supply -> heads, never the reverse). ``span_context`` is prior
    speaker-tagged spans (e.g. the chunking module's own ``Segment``, or any
    other :class:`~meeting_minutes_agent.chunking.models.SegmentLike`) given
    as context for continuity across a chunk boundary.

    ``declared_grid_turns`` (default ``()``, empty -- the A-free arm's own
    default) is the P-ATTR A-grid arm's declared per-slice turn/speaker
    grid, rendered via :func:`build_declared_grid_block` and appended as
    its own supplied-text part when non-empty. ``TEMPLATE_ID``/
    ``TEMPLATE_SHA256`` never change with this argument (module docstring):
    A-grid and A-free are the identical template, differing only in whether
    this block is present."""

    context_lines = [f"[{s.speaker}] {s.text}" for s in span_context]
    context_block = (CONTEXT_SECTION_HEADER + "\n" + "\n".join(context_lines)) if context_lines else None
    grid_block = build_declared_grid_block(declared_grid_turns)
    supplied_text = build_supplied_text(supply_text, grid_block, context_block)
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


# ---------------------------------------------------------------------------
# transcribe-only template (P-ATTR A-turn arm): no attribution instruction
# at all -- the caller already knows the single speaker for a per-turn
# audio cut, by construction, from the frozen manifest.
# ---------------------------------------------------------------------------

TRANSCRIBE_ONLY_TEMPLATE_ID = "transcribe-only-v1"

TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are transcribing one short, single-speaker turn cut from a "
    "multi-speaker meeting recording. The speaker's identity is already "
    "known and is NOT part of your task. Output ONLY the verbatim "
    "transcript text of what is spoken in this audio, as plain text, with "
    "no speaker label, no line-per-segment formatting, and no extra "
    "commentary before, between, or after it."
)

TRANSCRIBE_ONLY_TEMPLATE_SHA256 = config_hash(
    {"template_id": TRANSCRIBE_ONLY_TEMPLATE_ID, "system_instruction": TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE}
)


def build_transcribe_only_request(
    *,
    supply_text: str | None = None,
    decoding_params: dict[str, object] | None = None,
) -> HeadRequest:
    """The A-turn arm's request builder: ``supply_text`` defaults to
    ``None`` (no supply block at all -- P-ATTR is a zero-supply capability
    smoke, mirroring :func:`meeting_minutes_agent.heads.qa.build_qa_request`'s
    own zero-supply default). No ``span_context``/declared-grid parameter
    exists here by design: a per-turn request carries exactly one turn's
    audio and needs neither."""

    supplied_text = build_supplied_text(supply_text)
    return HeadRequest(
        task_instruction=TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE,
        supplied_text=supplied_text,
        decoding_params=dict(decoding_params or {}),
        template_id=TRANSCRIBE_ONLY_TEMPLATE_ID,
        template_sha256=TRANSCRIBE_ONLY_TEMPLATE_SHA256,
    )


def parse_transcribe_only_response(raw_text: str) -> str:
    """Never raises. Unlike :func:`parse_transcribe_attribute_response`,
    there is no per-line ``speaker|text`` grammar to recover here -- a
    transcribe-only reply is free-form transcript text, so this simply
    strips each non-blank line and joins them with a single space,
    collapsing multi-line replies into one utterance string. Returns the
    empty string only when ``raw_text`` carried no non-blank content at
    all (an empty turn reply, itself DATA a caller may record, not an
    error this function raises)."""

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return " ".join(lines)


__all__ = [
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "DECLARED_GRID_SECTION_HEADER",
    "TranscribedSegment",
    "TranscribeAttributeParseResult",
    "build_declared_grid_block",
    "build_transcribe_attribute_request",
    "parse_transcribe_attribute_response",
    "TRANSCRIBE_ONLY_TEMPLATE_ID",
    "TRANSCRIBE_ONLY_TEMPLATE_SHA256",
    "TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE",
    "build_transcribe_only_request",
    "parse_transcribe_only_response",
]
