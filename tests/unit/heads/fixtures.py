"""Shared fixtures for the ``heads`` module's tests."""

from __future__ import annotations

from meeting_minutes_agent.chunking.models import Segment

SPAN_CONTEXT = (
    Segment(id="seg-0", speaker="S1", start=0.0, end=1.0, text="Let's get started."),
    Segment(id="seg-1", speaker="S2", start=1.0, end=2.5, text="Sounds good."),
)

RESOLVED_TRANSCRIPT = (
    Segment(id="seg-10", speaker="S1", start=10.0, end=12.0, text="We should approve the budget."),
    Segment(id="seg-11", speaker="S2", start=12.0, end=14.0, text="Agreed, let's move on."),
)

STRICT_MINUTES_REPLY = (
    "ABSTRACT:\n"
    "- The team approved the budget. [evidence: S1|seg-10]\n"
    "ACTIONS:\n"
    "- Follow up with legal. [evidence: none]\n"
    "DECISIONS:\n"
    "- Ship v2 by Friday. [evidence: S2|seg-11]\n"
    "PROBLEMS:\n"
    "- None identified this chunk. [evidence: none]\n"
)
