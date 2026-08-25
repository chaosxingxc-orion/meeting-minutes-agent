"""Manifest validation tests for the stable-error Pass-0 launcher."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from meeting_minutes_agent.runreceipt import config_hash


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "launch_earnings22_stable_error_pass0.py"
_SPEC = importlib.util.spec_from_file_location("launch_earnings22_stable_error_pass0", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_runtime_manifest_hash_is_enforced(tmp_path: Path) -> None:
    value = {"schema": "earnings22-stable-error-runtime-v1", "meetings": [], "budget": {}}
    value["content_hash"] = config_hash(value)
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert tool.load_runtime(path)["content_hash"] == value["content_hash"]

    value["budget"] = {"calls": 1}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        tool.load_runtime(path)
