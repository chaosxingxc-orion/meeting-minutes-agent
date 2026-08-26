"""Tests for the LHCP eligible-cohort readback validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_material_lhcp_eligible_cohort.py"
_SPEC = importlib.util.spec_from_file_location("validate_material_lhcp_eligible_cohort", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_excluded_identity_in_items_fails() -> None:
    config = {
        "experiment_id": "test",
        "eligibility": {"excluded_audio_paths": ["x"]},
        "passing_gates": {"eligible_meetings": 1, "development_meetings": 1, "confirmation_meetings": 0},
    }
    cohort = {
        "items": [{"audio_path": "x", "split": "dev_2020", "cohort_role": "development"}],
        "exclusions": [{"audio_path": "x"}],
        "reference_reads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
    }
    verdict = {
        "reference_reads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "errors": [],
        "verdict": "LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN",
    }
    result = tool.validate(config, cohort, verdict)
    assert result["validation"] == "TRACE_INVALID"
    assert "excluded identity remains eligible" in result["errors"]

