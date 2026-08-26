"""Tests for the LHCP supply readback validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_material_lhcp_supply.py"
_SPEC = importlib.util.spec_from_file_location("validate_material_lhcp_supply", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_failed_meeting_produces_insufficient_verdict(tmp_path: Path) -> None:
    config = {
        "experiment_id": "test",
        "construction": {"expected_meetings": 1, "expected_splits": {"test": 1}},
        "passing_gates": {"meetings": 1},
    }
    verdict = {
        "meetings": [{"audio_path": "a", "split": "test", "passed": False}],
        "documents": [],
        "failed_meeting_ids": ["a"],
        "counts": {"failed_meetings": 1, "documents": 0},
        "reference_reads": 0,
        "audio_downloads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "verdict": "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT",
    }
    receipt = {"artifacts": {}, "verdict": "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT"}
    result = tool.validate(config, verdict, receipt, tmp_path)
    assert result["validation"] == "TRACE_COMPLETE"

