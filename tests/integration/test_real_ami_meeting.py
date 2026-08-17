"""ONE integration test that resolves a single REAL AMI meeting end to end.

Gated behind an env flag -- it is never run by a plain `pytest` invocation,
only when explicitly opted into (this repository's engineering-only, zero
model contact policy still allows reading the already-acquired, already-
licensed AMI annotation bytes from disk; it's gated because those bytes are
WSL2-only per program convention, not present on every machine/CI run, and
because unit tests must stay on tiny synthetic fixtures per the E2 task
brief).

Run explicitly (in WSL2, where SPEECHRL_DATA_DIR is reachable)::

    MMA_RUN_AMI_INTEGRATION=1 PYTHONPATH=src pytest tests/integration -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting

_ENV_FLAG = "MMA_RUN_AMI_INTEGRATION"
_DEFAULT_ROOT = (
    "/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data/"
    "datasets/ami/annotations/manual_1.6.2"
)
_MEETING_ID = "ES2002a"  # has the full layer stack (verified during E2 exploration)

pytestmark = pytest.mark.skipif(
    os.environ.get(_ENV_FLAG) != "1",
    reason=f"real-AMI integration test gated behind {_ENV_FLAG}=1",
)


def _annotations_root() -> Path:
    root = Path(os.environ.get("AMI_ANNOTATIONS_ROOT", _DEFAULT_ROOT))
    if not root.is_dir():
        pytest.skip(f"AMI annotations root not found: {root}")
    return root


def test_resolve_one_real_ami_meeting_end_to_end():
    corpus = NxtCorpus(_annotations_root())
    layers = corpus.discover_meetings().get(_MEETING_ID)
    assert layers is not None, f"{_MEETING_ID} not found in discovered meetings"
    assert layers.has_words and layers.has_segments
    assert layers.has_dialogue_acts
    assert layers.has_abstractive
    assert layers.has_extractive and layers.has_summlink
    assert layers.has_topics

    result = resolve_meeting(corpus, _MEETING_ID)

    assert len(result.transcript) > 0
    assert len(result.dialogue_acts) > 0
    assert result.minutes is not None
    assert len(result.minutes.all_sentences()) > 0
    assert len(result.evidence_links) > 0
    assert len(result.topics) > 0

    # every utterance must carry reconstructed text and a speaker
    assert all(u.speaker for u in result.transcript)
    assert all(isinstance(u.text, str) for u in result.transcript)

    # every evidence link must point at real, non-empty text on both sides
    for link in result.evidence_links:
        assert link.sentence_text
        assert link.text
        assert link.da_ids

    assert result.orphans == (), f"unexpected orphan pointers: {result.orphans[:5]!r}"
