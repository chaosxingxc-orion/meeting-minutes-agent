from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load("run_material_lhcp_development_frontend", ROOT / "scripts/run_material_lhcp_development_frontend.py")
READER = _load("validate_material_lhcp_development_frontend", ROOT / "scripts/validate_material_lhcp_development_frontend.py")


def test_windows_to_wsl_is_consistent() -> None:
    expected = Path("/mnt/d/speechrl-data/example")
    assert RUNNER.windows_to_wsl("D:/speechrl-data/example") == expected
    assert READER.windows_to_wsl("D:/speechrl-data/example") == expected


def test_reader_rejects_oversized_or_wrong_provenance() -> None:
    document = {
        "meetings": [
            {
                "meeting_id": f"m{index}",
                "slice_manifest": {
                    "mode": "turn_aware" if index else "vad",
                    "turn_provenance": "tool-diar",
                    "entries": [{"index": 0, "start": 0.0, "end": 121.0 if index == 1 else 90.0}],
                },
            }
            for index in range(25)
        ]
    }

    errors = READER.validate_slice_document(document)

    assert "slice provenance mismatch: m0" in errors
    assert "oversized slice: m1" in errors


def test_conversion_validator_rejects_wrong_count() -> None:
    try:
        RUNNER.validate_conversion({}, Path("/tmp/unused"), {"files": []})
    except ValueError as error:
        assert "count or order mismatch" in str(error)
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("empty conversion manifest should fail")
