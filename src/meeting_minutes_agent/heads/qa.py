"""``qa`` head: the meeting-QA request builder + abstention-aware parser
(component C6, backbone design doc SS2 C6 "qa (meeting QA, abstention-
aware)"). Unstubbed once the MeetingQA-floor measurement precondition's own
prerequisite -- an official-schema loader
(:mod:`meeting_minutes_agent.corpora.meetingqa.loader`) -- landed; this
module builds the QA request over meeting audio + a question and parses the
reply into the answer-span shape
:mod:`meeting_minutes_agent.metrics.qa` scores, mirroring the other two
heads' established pattern: a pinned + hashed template, a strict/lenient
parser pair, and parse failures recorded as DATA on the result, never
raised.

Design notes:

- Unlike :mod:`.transcribe_attribute`/:mod:`.minutes`, this head's only
  REQUIRED per-invocation content is the question itself; the resolved
  transcript text is deliberately NOT part of the request (per the mission
  brief: "over meeting audio + question") -- the frozen core answers from
  the audio it is given at the transport layer
  (:meth:`~meeting_minutes_agent.heads.request.HeadRequest.to_transport_kwargs`),
  not from a text transcript this head would otherwise have to suppy.
  ``supply_text`` is optional and defaults to ``None`` so the zero-supply
  G1 ``Z-qa`` arm (docs/readiness/2026-08-18-g1-preregistration-draft.md
  SS2) can build a request with no supply block at all.
- The reply grammar asks for an explicit ``ABSTAIN`` sentinel line (rather
  than, say, an empty reply) so a genuine "no answer" is distinguishable
  from a truncated/malformed reply at parse time -- :attr:`QAParseResult.answer_spans`
  is ``()`` for BOTH cases; :attr:`QAParseResult.parse_mode` is what tells
  them apart (``"failed"`` never means "the model correctly abstained").
  Multiple ``ANSWER:`` lines are how a multi-span answer is requested,
  matching :mod:`meeting_minutes_agent.metrics.qa`'s multi-span-as-
  flattened-token-bag scoring (module docstring there).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..runreceipt import config_hash
from .request import HeadRequest, build_supplied_text

TEMPLATE_ID = "qa-v1"

SYSTEM_INSTRUCTION_TEMPLATE = (
    "Answer the question below using ONLY the meeting audio you are given. "
    "If the audio does not contain enough information to answer the "
    "question, output EXACTLY this single line and nothing else:\n"
    "ABSTAIN\n"
    "Otherwise output one or more answer lines, each in EXACTLY this "
    "format:\n"
    "ANSWER: <verbatim answer text>\n"
    "Output more than one ANSWER line only when the answer is genuinely "
    "made of separate, non-contiguous parts of the meeting. Output ONLY "
    "the ABSTAIN line or one or more ANSWER lines; no extra commentary "
    "before, between, or after them."
)

TEMPLATE_SHA256 = config_hash({"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION_TEMPLATE})

QUESTION_SECTION_HEADER = "=== QUESTION ==="

_STRICT_ABSTAIN_LINE = "ABSTAIN"
_STRICT_ANSWER_RE = re.compile(r"^ANSWER:\s*(?P<span>.+)$")
_LENIENT_ANSWER_RE = re.compile(r"^-?\s*answer\s*:\s*(?P<span>.+)$", re.IGNORECASE)
_LENIENT_ABSTAIN_RE = re.compile(r"^abstain[.:]?$", re.IGNORECASE)


@dataclass(frozen=True)
class QAParseResult:
    """``answer_spans`` is exactly
    :attr:`meeting_minutes_agent.metrics.qa.QAExample.prediction_spans`'s
    shape: ``()`` for an abstention, one string for a single-span answer,
    more than one for a multi-span answer. ``parse_mode`` is ``"strict"``
    when the reply was either the single exact ``ABSTAIN`` line or every
    non-blank line matched the exact ``ANSWER: <text>`` grammar;
    ``"lenient"`` when at least one answer span (or an unambiguous
    abstain marker) was recovered despite some imperfection (extra/
    malformed lines, a case-insensitive or dash-prefixed variant);
    ``"failed"`` when nothing could be recovered at all -- callers MUST
    check ``parse_mode`` before treating an empty ``answer_spans`` as a
    real abstention: a ``"failed"`` parse is not a model abstention, it is
    a parser that recovered nothing."""

    answer_spans: tuple[str, ...]
    parse_mode: str  # "strict" | "lenient" | "failed"
    malformed_lines: tuple[str, ...]
    raw_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_spans": list(self.answer_spans),
            "parse_mode": self.parse_mode,
            "malformed_lines": list(self.malformed_lines),
            "raw_text": self.raw_text,
        }


def build_qa_request(
    *,
    question: str,
    supply_text: str | None = None,
    decoding_params: dict[str, object] | None = None,
) -> HeadRequest:
    """``question`` is required -- a QA request with no question is not a
    meaningful request. ``supply_text`` is the rendered
    :class:`meeting_minutes_agent.supply.render.SupplyBlock`'s ``.text``
    (this head does not import :mod:`meeting_minutes_agent.supply` itself,
    matching the other two heads' supply -> heads dependency direction);
    it defaults to ``None`` (no supply block at all) for the zero-supply
    arm."""

    question_block = f"{QUESTION_SECTION_HEADER}\n{question}"
    supplied_text = build_supplied_text(supply_text, question_block)
    return HeadRequest(
        task_instruction=SYSTEM_INSTRUCTION_TEMPLATE,
        supplied_text=supplied_text,
        decoding_params=dict(decoding_params or {}),
        template_id=TEMPLATE_ID,
        template_sha256=TEMPLATE_SHA256,
    )


def _strict_parse_answer_line(line: str) -> str | None:
    match = _STRICT_ANSWER_RE.match(line.strip())
    if not match:
        return None
    span = match.group("span").strip()
    return span or None


def _lenient_parse_answer_line(line: str) -> str | None:
    match = _LENIENT_ANSWER_RE.match(line.strip())
    if not match:
        return None
    span = match.group("span").strip()
    return span or None


def _is_abstain_line(line: str) -> bool:
    return bool(_LENIENT_ABSTAIN_RE.match(line.strip()))


def parse_qa_response(raw_text: str) -> QAParseResult:
    """Never raises. Strict pass: the reply is exactly the single line
    ``ABSTAIN`` (-> ``answer_spans=()``), or every non-blank line matches
    ``ANSWER: <text>`` (-> ``answer_spans`` in reply order). Otherwise a
    lenient pass re-parses every line: recognises the strict or a case-
    insensitive/dash-prefixed ``answer:`` form as an answer span, an
    unambiguous ``abstain`` marker (case-insensitive, optional trailing
    ``.``/``:``) as an abstention signal, and records everything else in
    ``malformed_lines``. Real answer content always wins over a stray
    abstain marker seen on another line of the same reply."""

    lines = [line for line in raw_text.splitlines() if line.strip()]

    if len(lines) == 1 and lines[0].strip() == _STRICT_ABSTAIN_LINE:
        return QAParseResult(answer_spans=(), parse_mode="strict", malformed_lines=(), raw_text=raw_text)

    strict_spans: list[str] = []
    strict_ok = True
    for line in lines:
        span = _strict_parse_answer_line(line)
        if span is None:
            strict_ok = False
            break
        strict_spans.append(span)

    if strict_ok and strict_spans:
        return QAParseResult(
            answer_spans=tuple(strict_spans), parse_mode="strict", malformed_lines=(), raw_text=raw_text
        )

    lenient_spans: list[str] = []
    malformed: list[str] = []
    abstain_seen = False
    for line in lines:
        span = _strict_parse_answer_line(line) or _lenient_parse_answer_line(line)
        if span is not None:
            lenient_spans.append(span)
        elif _is_abstain_line(line):
            abstain_seen = True
        else:
            malformed.append(line)

    if lenient_spans:
        return QAParseResult(
            answer_spans=tuple(lenient_spans), parse_mode="lenient", malformed_lines=tuple(malformed), raw_text=raw_text
        )
    if abstain_seen:
        return QAParseResult(answer_spans=(), parse_mode="lenient", malformed_lines=tuple(malformed), raw_text=raw_text)
    return QAParseResult(answer_spans=(), parse_mode="failed", malformed_lines=tuple(malformed), raw_text=raw_text)


__all__ = [
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "QUESTION_SECTION_HEADER",
    "QAParseResult",
    "build_qa_request",
    "parse_qa_response",
]
