"""Tests for stable-error extraction and decision rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "read_earnings22_stable_error_supply.py"
_SPEC = importlib.util.spec_from_file_location("read_earnings22_stable_error_supply", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_observed_form_returns_replacement_or_deletion() -> None:
    reference = ["revenue", "was", "q3", "adjusted"]
    assert tool.observed_form(reference, ["revenue", "was", "q", "three", "adjusted"], 2, 3) == "q three"
    assert tool.observed_form(reference, ["revenue", "was", "adjusted"], 2, 3) == "<DEL>"


def test_classification_requires_repeat_and_purity() -> None:
    rows = [
        {"file_id": "m", "speaker_id": "s", "surface": "q3", "entity_class": "ALPHANUMERIC", "observed_form": form, "legal_ticker_anchor": False}
        for form in ("q three", "q three", "q three", "q3")
    ]
    group = tool.classify_groups(rows)[0]
    assert group["category"] == "stable-wrong"
    assert group["majority_purity"] == 0.75
