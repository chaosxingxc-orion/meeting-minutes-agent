from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "audit_material_lhcp_development_frontend_overlap.py"
SPEC = importlib.util.spec_from_file_location("audit_material_lhcp_development_frontend_overlap", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _document(second_start: float) -> dict:
    return {
        "experiment_id": "x",
        "meetings": [
            {
                "meeting_id": "m1",
                "slice_manifest": {
                    "entries": [
                        {"index": 0, "start": 0.0, "end": 90.0},
                        {"index": 1, "start": second_start, "end": 180.0},
                    ]
                },
            }
        ],
    }


def test_overlap_gate_fails_on_positive_overlap() -> None:
    result = MODULE.audit(_document(89.5))
    assert result["verdict"] == "FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED"
    assert result["counts"]["overlap_boundaries"] == 1
    assert result["counts"]["total_overlap_seconds"] == 0.5


def test_overlap_gate_accepts_touching_boundaries() -> None:
    result = MODULE.audit(_document(90.0))
    assert result["verdict"] == "FRONTEND_SLICE_ZERO_OVERLAP_GATE_PASSED"
    assert result["counts"]["overlap_boundaries"] == 0
