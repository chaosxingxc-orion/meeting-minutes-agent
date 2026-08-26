from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "audit_material_lhcp_development_frontend_readiness.py"
SPEC = importlib.util.spec_from_file_location("audit_material_lhcp_development_frontend_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_windows_to_wsl_maps_drive_path() -> None:
    assert MODULE.windows_to_wsl("D:/speechrl-data/example.json") == Path(
        "/mnt/d/speechrl-data/example.json"
    )


def test_windows_to_wsl_preserves_posix_path() -> None:
    assert MODULE.windows_to_wsl("/mnt/d/example.json") == Path("/mnt/d/example.json")
