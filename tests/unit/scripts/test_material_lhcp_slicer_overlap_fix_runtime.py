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


RUNNER = _load("run_material_lhcp_slicer_overlap_fix", ROOT / "scripts/run_material_lhcp_slicer_overlap_fix.py")
VALIDATOR = _load(
    "validate_material_lhcp_slicer_overlap_fix",
    ROOT / "scripts/validate_material_lhcp_slicer_overlap_fix.py",
)


def test_runtime_scripts_share_windows_path_mapping() -> None:
    expected = Path("/mnt/d/speechrl-data/example")
    assert RUNNER.windows_to_wsl("D:/speechrl-data/example") == expected
    assert VALIDATOR.windows_to_wsl("D:/speechrl-data/example") == expected


def test_atomic_json_refuses_to_overwrite_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "receipt.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text("occupied", encoding="utf-8")

    try:
        RUNNER.atomic_json(destination, {"ok": True})
    except FileExistsError:
        pass
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("atomic writer must fail closed on a prior temporary file")
