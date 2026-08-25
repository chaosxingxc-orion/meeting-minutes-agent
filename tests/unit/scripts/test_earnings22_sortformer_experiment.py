"""Offline tests for the Earnings-22 Sortformer experiment machinery."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "earnings22_sortformer_experiment.py"
_SPEC = importlib.util.spec_from_file_location("earnings22_sortformer_experiment", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = tool
_SPEC.loader.exec_module(tool)


def test_best_mapping_handles_many_reference_speakers_exactly() -> None:
    matrix = {
        "gold0": {"h0": 10.0},
        "gold1": {"h1": 9.0},
        "gold2": {"h2": 8.0},
        "gold3": {"h3": 7.0},
        "gold4": {"h0": 1.0},
        "gold5": {"h1": 1.0},
    }

    mapping = tool._best_mapping(matrix, list(matrix), ["h0", "h1", "h2", "h3"])

    assert mapping == {"gold0": "h0", "gold1": "h1", "gold2": "h2", "gold3": "h3"}


def test_reference_turns_merge_only_consecutive_same_speaker() -> None:
    words = [
        tool.WordSpan("A", 0.0, 0.2),
        tool.WordSpan("A", 0.4, 0.6),
        tool.WordSpan("B", 0.8, 1.0),
        tool.WordSpan("A", 1.1, 1.3),
    ]

    turns = tool._reference_turns(words)

    assert [(turn.speaker, turn.start, turn.end) for turn in turns] == [
        ("A", 0.0, 0.6),
        ("B", 0.8, 1.0),
        ("A", 1.1, 1.3),
    ]


def test_word_metrics_separate_top_speakers_from_tail() -> None:
    words = [
        tool.WordSpan("main", 0.0, 1.0),
        tool.WordSpan("second", 1.0, 2.0),
        tool.WordSpan("tail", 2.0, 3.0),
    ]
    hypotheses = (
        tool.TurnSpan(0.0, 1.0, "h0"),
        tool.TurnSpan(1.0, 2.0, "h1"),
        tool.TurnSpan(2.0, 3.0, "h0"),
    )

    metrics = tool._word_assignment_metrics(words, hypotheses)

    assert metrics["top2"]["error_rate"] == 0.0
    assert metrics["tail"]["error_rate"] == 1.0
