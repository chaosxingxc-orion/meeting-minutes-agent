"""RTTM (Rich Transcription Time Marked) parsing and writing.

RTTM is the NIST diarization interchange format the DIAR-SMOKE pinned tool
arm emits (``docs/plans/2026-08-18-diarization-tool-selection.md`` SS2.4:
NeMo-Speech.cpp's ``--format rttm``). One space-separated ``SPEAKER`` record
per turn::

    SPEAKER <file-id> <channel> <onset> <duration> <NA> <NA> <speaker> <NA> <NA>

Only the ``SPEAKER`` record type carries a speaker-attributed turn; every
other record type (``SEGMENT``, ``NOSCORE``, ...) and every blank or
``;``-comment line is skipped, never treated as a parse failure. A
``SPEAKER`` line that IS malformed (too few fields, a non-numeric onset/
duration, a non-positive duration) raises :class:`RttmParseError` --
fail-closed, mirroring every other loader in this repository
(:mod:`meeting_minutes_agent.corpora.roles`, :mod:`.leakage`): a bad line is
a defect to surface, never a silently dropped turn.

This module returns/accepts :class:`~.slicer.TurnSpan` directly -- the same
plain, source-agnostic ``(speaker, start, end)`` shape
:func:`~.diarization.build_turn_aware_slice_plan_from_backend` and
:class:`~.diarization.PinnedToolDiarization` already use, so an RTTM-parsed
turn table needs no further adaptation before it reaches the slicer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .slicer import TurnSpan

RTTM_SPEAKER_RECORD_TYPE = "SPEAKER"

#: A well-formed SPEAKER line carries at least these 8 whitespace-separated
#: fields: type, file-id, channel, onset, duration, orthography, speaker
#: type, speaker name. (The trailing confidence/lookahead fields are
#: optional in some emitters, so this module does not require more than 8.)
_MIN_SPEAKER_FIELDS = 8


class RttmParseError(ValueError):
    """A ``SPEAKER`` line failed to parse: too few fields, a non-numeric
    onset/duration, or a non-positive duration."""


def _parse_speaker_line(line: str, *, line_no: int) -> TurnSpan:
    fields = line.split()
    if len(fields) < _MIN_SPEAKER_FIELDS:
        raise RttmParseError(
            f"RTTM line {line_no}: SPEAKER record has {len(fields)} field(s), expected at least "
            f"{_MIN_SPEAKER_FIELDS}: {line!r}"
        )
    try:
        onset = float(fields[3])
        duration = float(fields[4])
    except ValueError as error:
        raise RttmParseError(
            f"RTTM line {line_no}: onset {fields[3]!r} / duration {fields[4]!r} are not numeric: {line!r}"
        ) from error
    if duration <= 0:
        raise RttmParseError(f"RTTM line {line_no}: non-positive turn duration {duration}: {line!r}")
    speaker = fields[7]
    if not speaker or speaker == "<NA>":
        raise RttmParseError(f"RTTM line {line_no}: missing speaker name (field 8): {line!r}")
    return TurnSpan(start=onset, end=onset + duration, speaker=speaker)


def parse_rttm_text(text: str) -> tuple[TurnSpan, ...]:
    """Parse RTTM text into a sorted (by ``start``, then ``end``, then
    ``speaker``) tuple of :class:`~.slicer.TurnSpan`. Blank lines,
    ``;``-comment lines, and non-``SPEAKER`` record types are skipped;
    a malformed ``SPEAKER`` line raises :class:`RttmParseError`."""

    turns: list[TurnSpan] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        record_type = line.split(maxsplit=1)[0]
        if record_type != RTTM_SPEAKER_RECORD_TYPE:
            continue
        turns.append(_parse_speaker_line(line, line_no=line_no))
    return tuple(sorted(turns, key=lambda t: (t.start, t.end, t.speaker)))


def parse_rttm_file(path: Path | str) -> tuple[TurnSpan, ...]:
    """:func:`parse_rttm_text` over a file's contents."""

    return parse_rttm_text(Path(path).read_text(encoding="utf-8"))


def write_rttm_text(turns: Sequence[TurnSpan], *, file_id: str, channel: str = "1") -> str:
    """One ``SPEAKER`` line per turn, in the given order, NA-filled for the
    fields this module's parser does not populate (orthography/speaker-type/
    confidence/lookahead) -- the conventional RTTM filler. The round-trip
    counterpart of :func:`parse_rttm_text`: onset/duration are written to 3
    decimal places, so a turn whose ``start``/``end`` already carry <=3
    decimal places round-trips byte-for-byte through
    ``parse_rttm_text(write_rttm_text(turns, ...))``."""

    lines = [
        f"SPEAKER {file_id} {channel} {t.start:.3f} {(t.end - t.start):.3f} <NA> <NA> {t.speaker} <NA> <NA>"
        for t in turns
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def write_rttm_file(turns: Sequence[TurnSpan], path: Path | str, *, file_id: str, channel: str = "1") -> Path:
    """Write :func:`write_rttm_text`'s output to ``path``, creating parent
    directories as needed. Returns ``path``."""

    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(write_rttm_text(turns, file_id=file_id, channel=channel), encoding="utf-8")
    return resolved


__all__ = [
    "RTTM_SPEAKER_RECORD_TYPE",
    "RttmParseError",
    "parse_rttm_text",
    "parse_rttm_file",
    "write_rttm_text",
    "write_rttm_file",
]
