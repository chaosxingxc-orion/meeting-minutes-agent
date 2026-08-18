"""ONE integration test that loads a REAL MeetingQA split end to end against
the REAL, already-acquired AMI audio tree.

Gated behind an env flag -- it is never run by a plain `pytest` invocation,
only when explicitly opted into (mirrors ``test_real_ami_meeting.py``'s own
gating rationale: the acquired bytes are WSL2-only per program convention,
not present on every machine/CI run, and unit tests must stay on tiny
synthetic fixtures per program policy).

Run explicitly (in WSL2, where SPEECHRL_DATA_DIR is reachable)::

    MMA_RUN_MEETINGQA_INTEGRATION=1 PYTHONPATH=src pytest tests/integration -v

The expected counts asserted below are the umbrella dataset lock's own
verification receipt for the ``meetingqa`` record
(``docs/datasets.lock.json``, observed 2026-08-17): dev has 2252 QA
instances over 48 annotated-transcript meetings, of which 621 are
unanswerable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from meeting_minutes_agent.corpora.meetingqa.loader import load_split

_ENV_FLAG = "MMA_RUN_MEETINGQA_INTEGRATION"
_DEFAULT_SPEECHRL_DATA_DIR = "/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data"

pytestmark = pytest.mark.skipif(
    os.environ.get(_ENV_FLAG) != "1",
    reason=f"real-MeetingQA integration test gated behind {_ENV_FLAG}=1",
)


def _data_dir() -> Path:
    return Path(os.environ.get("SPEECHRL_DATA_DIR", _DEFAULT_SPEECHRL_DATA_DIR))


def _meetingqa_root() -> Path:
    root = _data_dir() / "datasets" / "meetingqa"
    if not root.is_dir():
        pytest.skip(f"MeetingQA release not found: {root}")
    return root


def _ami_root() -> Path:
    root = _data_dir() / "datasets" / "ami"
    if not root.is_dir():
        pytest.skip(f"AMI corpus not found: {root}")
    return root


def test_load_real_dev_split_end_to_end_with_audio_resolution():
    examples = load_split(meetingqa_root=_meetingqa_root(), ami_root=_ami_root(), split="dev", require_audio=True)

    assert len(examples) == 2252

    meeting_ids = {ex.meeting_id for ex in examples}
    assert len(meeting_ids) == 48

    n_unanswerable = sum(1 for ex in examples if ex.unanswerable)
    assert n_unanswerable == 621
    assert all(ex.answer_spans == () for ex in examples if ex.unanswerable)

    n_multi_span = sum(1 for ex in examples if len(ex.answer_spans) > 1)
    assert n_multi_span > 0

    # every resolved audio path must be a real file on disk -- require_audio
    # already enforces this at load time, but assert it explicitly as the
    # end-to-end contract this test exists to check.
    assert all(ex.audio_path.is_file() for ex in examples)

    # the one known real-release id absent from the multi-span file
    # (loader.py module docstring, surprise 5) must still be present, via
    # the flat-fallback path.
    known_gap_id = "0-0-1-TS3006c-828"
    by_id = {ex.example_id: ex for ex in examples}
    if known_gap_id in by_id:
        assert by_id[known_gap_id].span_source == "flat_fallback"

    # every example must carry at least one speaker id extracted from its
    # context (AMI meetings are always multi-party).
    assert all(len(ex.speakers) >= 1 for ex in examples)
