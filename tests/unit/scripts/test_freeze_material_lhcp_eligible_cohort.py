"""Tests for the LHCP eligible-cohort freezer."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "freeze_material_lhcp_eligible_cohort.py"
_SPEC = importlib.util.spec_from_file_location("freeze_material_lhcp_eligible_cohort", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_cohort_role_uses_published_split_identity() -> None:
    assert tool.cohort_role("dev_2020") == "development"
    assert tool.cohort_role("test_2022") == "confirmation"


def test_build_excludes_only_mechanical_failure() -> None:
    config = {
        "experiment_id": "test",
        "evidence_tier": "test",
        "eligibility": {"excluded_audio_paths": ["1c2.wav"], "minimum_candidates": 8},
        "passing_gates": {
            "eligible_meetings": 1, "development_meetings": 1,
            "confirmation_meetings": 0, "excluded_meetings": 1,
        },
    }
    admission = {
        "items": [
            {"audio_path": "1c1.wav", "split": "dev_2020", "contribution_friendly_id": 1},
            {"audio_path": "1c2.wav", "split": "test_2020", "contribution_friendly_id": 2},
        ]
    }
    supply = {
        "verdict": "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT",
        "meetings": [
            {"audio_path": "1c1.wav", "passed": True, "readable_documents": 1, "visible_characters": 200, "candidate_count": 8},
            {"audio_path": "1c2.wav", "passed": False, "readable_documents": 0, "visible_characters": 0, "candidate_count": 0, "failure_reasons": ["no_readable_document"]},
        ],
    }
    cohort, verdict = tool.build(config, admission, supply, {"validation": "TRACE_COMPLETE", "errors": []})
    assert verdict["verdict"] == "LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN"
    assert [row["audio_path"] for row in cohort["items"]] == ["1c1.wav"]
    assert cohort["exclusions"][0]["audio_path"] == "1c2.wav"

