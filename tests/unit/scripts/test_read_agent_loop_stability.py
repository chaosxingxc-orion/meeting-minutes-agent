"""Unit tests for the registered loop-stability reader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "read_agent_loop_stability.py"
_SPEC = importlib.util.spec_from_file_location("read_agent_loop_stability", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_edit_distance_counts_word_operations() -> None:
    assert tool.edit_distance(["a", "b", "c"], ["a", "x"]) == 2


def test_observed_form_extracts_aligned_replacement() -> None:
    assert tool.observed_form(["our", "ebitda", "rose"], ["our", "ebit", "rose"], 1, 2) == "ebit"


def test_verdict_separates_stability_from_safety() -> None:
    base = {
        "complete": True,
        "context_hash_replay": True,
        "context_budget": True,
        "consistency_vs_bare": True,
        "consistency_vs_deranged": True,
        "convergence": True,
        "wer_noninferior": True,
        "worst_speaker_noninferior": True,
        "unsupported_activation": True,
        "language_drift": True,
    }
    assert tool.choose_verdict(base) == "LOOP-STABILITY-REACHABLE"
    assert tool.choose_verdict({**base, "wer_noninferior": False}) == "CONTEXT-STABLE-BUT-HARMFUL"
    assert tool.choose_verdict({**base, "convergence": False}) == "LOOP-STABILITY-NOT-REACHED"
