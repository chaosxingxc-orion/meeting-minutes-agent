"""Tests for the stable-error roster builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build_earnings22_stable_error_manifests.py"
_SPEC = importlib.util.spec_from_file_location("build_earnings22_stable_error_manifests", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_selection_prefers_supply_then_seeded_tie_break() -> None:
    rows = [
        {"file_id": "low", "exclusive_carry": 1},
        {"file_id": "a", "exclusive_carry": 8},
        {"file_id": "b", "exclusive_carry": 8},
        {"file_id": "c", "exclusive_carry": 7},
        {"file_id": "d", "exclusive_carry": 6},
        {"file_id": "e", "exclusive_carry": 5},
    ]

    selected = tool.select_meetings(rows)

    assert {row["file_id"] for row in selected[:2]} == {"a", "b"}
    assert [row["exclusive_carry"] for row in selected] == [8, 8, 7, 6]
    assert all(row["file_id"] != "low" for row in selected)


def test_overlong_turn_is_split_only_at_transport_bound() -> None:
    pieces = tool.split_overlong_turn(10.0, 271.0, "speaker_2")

    assert pieces == [
        {"speaker_id": "speaker_2", "start": 10.0, "end": 130.0},
        {"speaker_id": "speaker_2", "start": 130.0, "end": 250.0},
        {"speaker_id": "speaker_2", "start": 250.0, "end": 271.0},
    ]
