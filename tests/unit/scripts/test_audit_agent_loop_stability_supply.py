"""Tests for the agent-loop stability supply audit."""

from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_agent_loop_stability_supply.py"
_SPEC = importlib.util.spec_from_file_location("audit_agent_loop_stability_supply", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_tokens_normalize_and_remove_stopwords() -> None:
    assert tool.tokens("The EBITDA and Q1 EBITDA-margin in SK") == ["ebitda", "q1", "ebitda-margin", "sk"]


def test_ranked_keywords_are_deterministic_and_bounded() -> None:
    counts = Counter({"beta": 3, "alpha": 3, "gamma": 1})

    assert tool.ranked_keywords(counts, minimum_count=2, cap=1) == ["alpha"]
