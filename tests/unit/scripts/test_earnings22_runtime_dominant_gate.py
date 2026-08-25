"""Tests for the RTTM-only dominant cluster gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from meeting_minutes_agent.chunking.slicer import TurnSpan


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "earnings22_runtime_dominant_gate.py"
_SPEC = importlib.util.spec_from_file_location("earnings22_runtime_dominant_gate", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_runtime_gate_accepts_same_dominant_pair_across_three_windows() -> None:
    turns = []
    for start in (0.0, 600.0, 1200.0):
        turns.extend(
            [
                TurnSpan(start, start + 180.0, "main"),
                TurnSpan(start + 180.0, start + 300.0, "second"),
                TurnSpan(start + 300.0, start + 390.0, "tail1"),
                TurnSpan(start + 390.0, start + 450.0, "tail2"),
            ]
        )

    result = tool.runtime_features(tuple(turns))

    assert result["top2_speech_share"] == 2 / 3
    assert result["stable_window_fraction"] == 1.0
    assert result["runtime_admitted"] is True


def test_runtime_gate_rejects_pair_that_does_not_persist() -> None:
    turns = (
        TurnSpan(0.0, 250.0, "a"),
        TurnSpan(250.0, 500.0, "b"),
        TurnSpan(600.0, 850.0, "c"),
        TurnSpan(850.0, 1100.0, "d"),
        TurnSpan(1200.0, 1450.0, "a"),
        TurnSpan(1450.0, 1700.0, "b"),
    )

    result = tool.runtime_features(turns)

    assert result["occupancy_only_admitted"] is True
    assert result["stable_window_fraction"] == 2 / 3
    assert result["runtime_admitted"] is False
