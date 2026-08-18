"""``qa`` head: interface-complete STUB.

Not built (component inventory,
``docs/plans/2026-08-18-agent-backbone-and-layout.md`` SS2 C6: "qa
(meeting QA, abstention-aware) ... after the MeetingQA floor measurement").
This module exists so a caller can import and reference the qa head's
intended entry points before that precondition is measured; every entry
point raises immediately, naming the precondition, rather than silently
returning a placeholder result a caller could mistake for a real answer.
"""

from __future__ import annotations

from typing import Any

from .request import HeadRequest

TEMPLATE_ID = "qa-v1-STUB"


class MeetingQAFloorNotMeasuredError(NotImplementedError):
    """Raised by every ``qa`` head entry point until the MeetingQA-floor
    measurement precondition (backbone design doc component C6) lands and
    this stub is replaced with a real implementation."""


_PRECONDITION_MESSAGE = (
    "heads.qa.{fn} is an interface-complete stub: the qa head cannot {verb} "
    "before the MeetingQA-floor measurement precondition lands (see "
    "docs/plans/2026-08-18-agent-backbone-and-layout.md, component C6, "
    "'qa (meeting QA, abstention-aware) ... after the MeetingQA floor "
    "measurement')."
)


def build_qa_request(*args: Any, **kwargs: Any) -> HeadRequest:
    raise MeetingQAFloorNotMeasuredError(_PRECONDITION_MESSAGE.format(fn="build_qa_request", verb="build a request"))


def parse_qa_response(*args: Any, **kwargs: Any) -> Any:
    raise MeetingQAFloorNotMeasuredError(_PRECONDITION_MESSAGE.format(fn="parse_qa_response", verb="parse a response"))


__all__ = ["TEMPLATE_ID", "MeetingQAFloorNotMeasuredError", "build_qa_request", "parse_qa_response"]
