"""Tests for the post-hoc loop echo diagnostic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_agent_loop_echo.py"
_SPEC = importlib.util.spec_from_file_location("audit_agent_loop_echo", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_echo_fraction_detects_contiguous_reuse() -> None:
    assert tool.echo_fraction(["prior", "cloud", "growth"], ["cloud", "growth"]) == 1.0
    assert tool.echo_fraction([], ["cloud"]) == 0.0
