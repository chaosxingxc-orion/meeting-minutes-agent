"""E7a -- task heads (component C6).

Each head is a prompt template builder + a response parser, never a
transport call: :mod:`.transcribe_attribute` (the LISTEN-stage
transcribe+attribute head), :mod:`.minutes` (the four-section minutes
head), and :mod:`.qa` (the meeting-QA, abstention-aware head -- unstubbed
once its own precondition, the MeetingQA-official-schema loader
:mod:`meeting_minutes_agent.corpora.meetingqa.loader`, landed).
:mod:`.request` defines the shared :class:`~.request.HeadRequest` shape
every head builds.
"""

from __future__ import annotations

from .minutes import (
    MinutesBulletClaim,
    MinutesParseResult,
    build_minutes_request,
    parse_minutes_response,
)
from .qa import QAParseResult, build_qa_request, parse_qa_response
from .request import HeadRequest, build_supplied_text
from .transcribe_attribute import (
    TRANSCRIBE_ONLY_TEMPLATE_ID,
    TRANSCRIBE_ONLY_TEMPLATE_SHA256,
    TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE,
    TranscribeAttributeParseResult,
    TranscribedSegment,
    build_declared_grid_block,
    build_transcribe_attribute_request,
    build_transcribe_only_request,
    parse_transcribe_attribute_response,
    parse_transcribe_only_response,
)

__all__ = [
    "HeadRequest",
    "build_supplied_text",
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
    "MinutesBulletClaim",
    "MinutesParseResult",
    "build_minutes_request",
    "parse_minutes_response",
    "QAParseResult",
    "build_qa_request",
    "parse_qa_response",
]
