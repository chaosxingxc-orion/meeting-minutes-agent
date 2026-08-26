"""Tests for the material-conditioned Omni preregistration audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_material_omni_capability_prereg.py"
_SPEC = importlib.util.spec_from_file_location("audit_material_omni_capability_prereg", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_subset_bounds_select_smallest_and_largest_values() -> None:
    assert tool.subset_bounds([4.0, 1.0, 3.0, 2.0], 2) == {"minimum": 3.0, "maximum": 7.0}


def test_required_pairs_increases_with_discordance() -> None:
    low = tool.required_pairs(effect=0.05, alpha=0.05, power=0.8, discordant_fraction=0.1)
    middle = tool.required_pairs(effect=0.05, alpha=0.05, power=0.8, discordant_fraction=0.2)
    high = tool.required_pairs(effect=0.05, alpha=0.05, power=0.8, discordant_fraction=0.3)

    assert (low, middle, high) == (314, 628, 942)


def test_missing_trace_fails_closed(tmp_path: Path) -> None:
    rows, errors = tool.validate_trace(
        tmp_path / "missing.jsonl",
        ["file_id", "turn_index"],
    )

    assert rows == []
    assert errors == ["required frozen per-turn dispatch trace is absent"]


def test_required_pairs_rejects_impossible_discordance() -> None:
    with pytest.raises(ValueError, match="at least the absolute effect"):
        tool.required_pairs(effect=0.1, alpha=0.05, power=0.8, discordant_fraction=0.05)
