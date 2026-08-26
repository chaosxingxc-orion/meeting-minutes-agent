from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validate_material_lhcp_development_audio.py"
SPEC = importlib.util.spec_from_file_location("validate_material_lhcp_development_audio", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_safe_external_path_accepts_descendant(tmp_path: Path) -> None:
    assert MODULE.safe_external_path(tmp_path, "audio/dev/file.wav") == (
        tmp_path / "audio/dev/file.wav"
    ).resolve()


def test_safe_external_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes root"):
        MODULE.safe_external_path(tmp_path, "../outside.wav")
