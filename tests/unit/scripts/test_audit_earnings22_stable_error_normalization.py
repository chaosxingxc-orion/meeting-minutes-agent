"""Tests for the labelled post-hoc normalization diagnostic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_earnings22_stable_error_normalization.py"
_SPEC = importlib.util.spec_from_file_location("audit_earnings22_stable_error_normalization", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_compact_alnum_only_removes_separators() -> None:
    assert tool.compact_alnum("E B-I_T.D.A") == "ebitda"
    assert tool.compact_alnum("Q one") != tool.compact_alnum("Q1")
