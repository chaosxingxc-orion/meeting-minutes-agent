"""Tests for the offline LHCP admission receipt validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_material_lhcp_admission.py"
_SPEC = importlib.util.spec_from_file_location("validate_material_lhcp_admission", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_duplicate_checksum_fails_readback() -> None:
    config = {
        "experiment_id": "test",
        "huggingface": {"expected_splits": {"dev_2020": 2}},
        "passing_gates": {"hf_rows": 2},
    }
    manifest = {
        "config_sha256": "hash",
        "reference_firewall": {
            "projected_hf_columns": ["audio.path"],
            "reference_reads": 0,
            "audio_body_reads": 0,
            "material_body_reads": 0,
        },
        "orphans": [],
        "ambiguities": [],
        "items": [
            {
                "split": "dev_2020", "audio_path": "1c1.wav", "event_id": 1,
                "contribution_friendly_id": 1,
                "materials": [{"download_url": "u1", "checksum": "same"}],
            },
            {
                "split": "dev_2020", "audio_path": "1c2.wav", "event_id": 1,
                "contribution_friendly_id": 2,
                "materials": [{"download_url": "u2", "checksum": "same"}],
            },
        ],
    }
    result = tool.validate(config, manifest, {"config_sha256": "hash", "verdict": "pass"})
    assert result["validation"] == "TRACE_INVALID"
    assert result["counts"]["duplicate_material_checksums"] == 1

