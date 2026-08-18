"""Boundary-provenance tiering for chunk/slice planning.

Reuses the SAME machine-enforced M0/M1 leakage-tier gate pattern
:mod:`meeting_minutes_agent.glossary.provenance` already uses for the
glossary's REVISE-stage carry (``LeakageTier`` / ``LeakageTierViolation`` /
``build_runtime_supply_view``'s fail-closed ``_reject_m1``), applied here to
chunk-boundary and turn-table inputs:

- the analysis document's own instruction (17-item change list item 7):
  "tag AMI topic-layer marks as gold-derived (M1) when used by the runtime
  planner... reuse the glossary leakage-tier machinery pattern";
- extended, per the 2026-08-18 slicer amendment (turn-aware transport
  packing), to speaker-turn tables: a gold AMI diarization/turn layer is
  ceiling/oracle-tier metadata exactly like the topic layer, never a
  runtime default.

**M0** = signal-derived, or genuinely shipped-with-the-meeting materials
(e.g. MeetingBank's Legistar agenda/bill index), or a future automatic
diarizer's own output -- runtime-admissible, the only tier a headline arm
may use by default. **M1** = annotation/reference-derived (AMI/ICSI gold
topic marks, AMI/ICSI gold diarization/turn tables) -- ceiling-arm only,
never a runtime default.

Fail-closed, not a silent filter, mirroring
:func:`meeting_minutes_agent.glossary.provenance.build_runtime_supply_view`'s
own stated rationale: a caller who passes an M1 source straight into
:func:`assert_runtime_admissible` without explicitly admitting it gets an
exception, not a plan that quietly (and wrongly) used it anyway. The
DIFFERENT, complementary half of the design lives in the adapter call sites
that already know their source is gold (:mod:`.adapters`): rather than ever
raising for an ordinary caller who simply didn't ask for the oracle, those
adapters decide UP FRONT whether to forward gold marks at all, falling back
to an empty boundary set (pure signal packing) when the ceiling arm is not
admitted -- "runtime chunk planning must fall back to signal-derived
boundaries unless a ceiling arm explicitly admits the gold topic layer."
This module's :func:`assert_runtime_admissible` is the defense-in-depth
backstop for any OTHER caller that bypasses that adapter and passes an M1
source directly.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping


class BoundaryProvenance(str, Enum):
    """Where a chunk-boundary or turn-table input came from."""

    SIGNAL = "signal"  # fixed grid / VAD pause detection -- no annotation
    SHIPPED_MATERIALS = "shipped-materials"  # e.g. MeetingBank Legistar agenda/bill index
    TOOL_DIAR = "tool-diar"  # a future automatic diarizer's turn table -- deployment-tier
    ORACLE_TOPIC = "oracle-topic"  # AMI/ICSI gold topic-segmentation layer
    ORACLE_TURN = "oracle-turn"  # AMI/ICSI gold diarization/turn (speaker-segment) layer


class BoundaryLeakageTier(str, Enum):
    M0 = "M0"
    M1 = "M1"


PROVENANCE_TIER: Mapping[BoundaryProvenance, BoundaryLeakageTier] = {
    BoundaryProvenance.SIGNAL: BoundaryLeakageTier.M0,
    BoundaryProvenance.SHIPPED_MATERIALS: BoundaryLeakageTier.M0,
    BoundaryProvenance.TOOL_DIAR: BoundaryLeakageTier.M0,
    BoundaryProvenance.ORACLE_TOPIC: BoundaryLeakageTier.M1,
    BoundaryProvenance.ORACLE_TURN: BoundaryLeakageTier.M1,
}


class BoundaryLeakageTierViolation(RuntimeError):
    """Raised when a Tier-M1 (oracle/gold-annotation-derived) boundary
    source is used to plan a runtime chunk/slice without an explicit
    ceiling-arm admission (``allow_oracle=True``)."""


def tier_of(provenance: BoundaryProvenance) -> BoundaryLeakageTier:
    return PROVENANCE_TIER[provenance]


def assert_runtime_admissible(
    provenance: BoundaryProvenance,
    *,
    allow_oracle: bool = False,
    label: str = "boundary source",
) -> None:
    """Fail-closed gate: refuse a Tier-M1 ``provenance`` unless
    ``allow_oracle`` is explicitly ``True`` (a declared oracle-ceiling arm).
    Tier-M0 provenances always pass, regardless of ``allow_oracle``."""

    if tier_of(provenance) is BoundaryLeakageTier.M1 and not allow_oracle:
        raise BoundaryLeakageTierViolation(
            f"{label} {provenance.value!r} is Tier-M1 (oracle/gold-annotation-derived) and cannot "
            "plan a runtime chunk/slice boundary by default; pass allow_oracle=True only from a "
            "declared oracle-ceiling arm, never a headline arm"
        )


__all__ = [
    "BoundaryProvenance",
    "BoundaryLeakageTier",
    "PROVENANCE_TIER",
    "BoundaryLeakageTierViolation",
    "tier_of",
    "assert_runtime_admissible",
]
