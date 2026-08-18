"""Tests for :mod:`meeting_minutes_agent.chunking.leakage`: the M0/M1
boundary-provenance leakage-tier gate (the same pattern
:mod:`meeting_minutes_agent.glossary.provenance` uses, reused here for
chunk-boundary and turn-table inputs)."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.leakage import (
    BoundaryLeakageTier,
    BoundaryLeakageTierViolation,
    BoundaryProvenance,
    assert_runtime_admissible,
    tier_of,
)


@pytest.mark.parametrize(
    "provenance,expected_tier",
    [
        (BoundaryProvenance.SIGNAL, BoundaryLeakageTier.M0),
        (BoundaryProvenance.SHIPPED_MATERIALS, BoundaryLeakageTier.M0),
        (BoundaryProvenance.TOOL_DIAR, BoundaryLeakageTier.M0),
        (BoundaryProvenance.ORACLE_TOPIC, BoundaryLeakageTier.M1),
        (BoundaryProvenance.ORACLE_TURN, BoundaryLeakageTier.M1),
    ],
)
def test_tier_of_every_provenance(provenance, expected_tier):
    assert tier_of(provenance) is expected_tier


@pytest.mark.parametrize(
    "provenance", [BoundaryProvenance.SIGNAL, BoundaryProvenance.SHIPPED_MATERIALS, BoundaryProvenance.TOOL_DIAR]
)
def test_m0_provenance_always_admissible(provenance):
    assert_runtime_admissible(provenance)  # does not raise
    assert_runtime_admissible(provenance, allow_oracle=False)  # does not raise
    assert_runtime_admissible(provenance, allow_oracle=True)  # does not raise either


@pytest.mark.parametrize("provenance", [BoundaryProvenance.ORACLE_TOPIC, BoundaryProvenance.ORACLE_TURN])
def test_m1_provenance_refused_by_default(provenance):
    with pytest.raises(BoundaryLeakageTierViolation, match="Tier-M1"):
        assert_runtime_admissible(provenance)
    with pytest.raises(BoundaryLeakageTierViolation):
        assert_runtime_admissible(provenance, allow_oracle=False)


@pytest.mark.parametrize("provenance", [BoundaryProvenance.ORACLE_TOPIC, BoundaryProvenance.ORACLE_TURN])
def test_m1_provenance_admitted_with_explicit_flag(provenance):
    assert_runtime_admissible(provenance, allow_oracle=True)  # does not raise


def test_violation_message_names_the_provenance_and_label():
    with pytest.raises(BoundaryLeakageTierViolation, match="oracle-topic"):
        assert_runtime_admissible(BoundaryProvenance.ORACLE_TOPIC, label="topic_marks provenance")
