"""Builds a tiny synthetic MeetingQA release + AMI audio tree under a
tmp_path, mirroring the acquired real release's schema (see
:mod:`meeting_minutes_agent.corpora.meetingqa.loader`'s module docstring
for the full real-schema surprise catalogue) closely enough to exercise
split discipline, BIO multi-span decoding, the flat-fallback path, and
speaker extraction end to end -- WITHOUT ever touching the real 311 MB
release. See CLAUDE.md: unit tests use tiny synthetic fixtures only.

Four dev examples, deliberately shaped to cover distinct cases (mirrors
:mod:`tests.unit.nxt.fixtures`'s per-case design):

- ``DEV_SINGLE_SPAN_ID``: a normal, single-span answerable example, present
  in both the flat and multi-span files.
- ``DEV_MULTI_SPAN_ID``: a genuinely multi-span answerable example (two
  disjoint spans separated by an unrelated turn), whose multi-span tokens
  carry the real release's glued-trailing-``"\\n"`` tokenization quirk at
  every turn boundary; also names a THIRD speaker id, absent from every
  other example, to exercise multi-speaker extraction. The flat file's own
  ``answers.text`` for this id deliberately reproduces the real release's
  gap-collapsing surprise (one bounding string spanning both true spans,
  dropping the intervening turn) -- present only to document why the
  loader never reads it, never asserted on.
- ``DEV_UNANSWERABLE_ID``: unanswerable (``is_impossible: true``); present
  in the multi-span file as an all-``"O"`` label row.
- ``DEV_FALLBACK_ID``: answerable, single-span, and internally consistent
  in the flat file (``answer_start`` really does locate ``text``, computed
  via ``str.find`` here rather than hand-counted) but deliberately ABSENT
  from the multi-span file altogether -- the flat-fallback path (mirrors
  the one real dev id, ``0-0-1-TS3006c-828``, missing from the real
  ms-dev file).

One train example (``TRAIN_ID``, same meeting id as the dev examples but
distinct content) to prove split isolation: loading "train" must never see
"dev" content or vice versa.

Two AMI meetings get a dummy-content Mix-Headset WAV under ``amicorpus/``:
MEET1 and MEET2 (:func:`build_tiny_ami_audio_tree`). No third meeting's
audio is ever created here, so an unresolvable-meeting test can point at an
empty AMI root without disturbing this tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEV_SINGLE_SPAN_ID = "0-0-1-MEET1-1"
DEV_MULTI_SPAN_ID = "0-0-1-MEET1-2"
DEV_UNANSWERABLE_ID = "0-0-1-MEET1-3"
DEV_FALLBACK_ID = "0-0-1-MEET2-1"
TRAIN_ID = "0-0-1-MEET1-9"

DEV_SINGLE_SPAN_DECODED = ("I agree, sounds good.",)
DEV_MULTI_SPAN_DECODED = ("I can help with that.", "Sure, I'll look at the budget too.")
DEV_FALLBACK_ANSWER = ("The deadline is Friday.",)
TRAIN_DECODED = ("Great, let's begin.",)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _flat_item(
    *,
    example_id: str,
    title: str,
    question: str,
    context: str,
    is_impossible: bool,
    answer_text: list[str],
    answer_start: list[int],
) -> dict:
    return {
        "context": context,
        "question": question,
        "title": title,
        "id": example_id,
        "is_impossible": is_impossible,
        # answer_start/text below are illustrative of the real release's own
        # shape only -- loader.py never reads them when a multi-span row is
        # available (module docstring, surprise 3).
        "answers": {"text": answer_text, "answer_start": answer_start},
    }


def _ms_item(*, example_id: str, tokens: list[str], answer_token_indices: Iterable[int]) -> dict:
    indices = set(answer_token_indices)
    labels = ["I_ANSWER" if i in indices else "O" for i in range(len(tokens))]
    return {"id": example_id, "question": [], "context": tokens, "labels": labels}


def build_tiny_meetingqa_release(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    dev_single_context = "Speaker 0: Let's start the meeting.\n Speaker 1: I agree, sounds good.\n"
    dev_single_tokens = dev_single_context.split(" ")
    assert dev_single_tokens[8:12] == ["I", "agree,", "sounds", "good.\n"]

    dev_multi_context = (
        "Speaker 0: We need more time.\n Speaker 1: I can help with that.\n "
        "Speaker 0: Let's also check the budget.\n Speaker 1: Sure, I'll look at the budget too.\n "
        "Speaker 2: Noted, thanks everyone.\n"
    )
    dev_multi_tokens = dev_multi_context.split(" ")
    assert dev_multi_tokens[8:13] == ["I", "can", "help", "with", "that.\n"]
    assert dev_multi_tokens[22:29] == ["Sure,", "I'll", "look", "at", "the", "budget", "too.\n"]

    dev_unanswerable_context = "Speaker 0: Any other business?\n Speaker 1: No, I think we're done.\n"
    dev_unanswerable_tokens = dev_unanswerable_context.split(" ")

    dev_fallback_context = "Speaker 0: The deadline is Friday.\n Speaker 1: Got it, thanks.\n"
    dev_fallback_answer_start = dev_fallback_context.find("The deadline is Friday.")
    assert dev_fallback_answer_start >= 0
    assert (
        dev_fallback_context[dev_fallback_answer_start : dev_fallback_answer_start + len("The deadline is Friday.")]
        == "The deadline is Friday."
    )

    train_context = "Speaker 0: Welcome to training data.\n Speaker 1: Great, let's begin.\n"
    train_tokens = train_context.split(" ")
    assert train_tokens[8:11] == ["Great,", "let's", "begin.\n"]

    dev_flat = {
        "version": "0.1.0-fixture",
        "data": [
            _flat_item(
                example_id=DEV_SINGLE_SPAN_ID,
                title="MEET1",
                question="What did speaker 1 say?",
                context=dev_single_context,
                is_impossible=False,
                answer_text=["I agree, sounds good."],
                answer_start=[dev_single_context.find("I agree, sounds good.")],
            ),
            _flat_item(
                example_id=DEV_MULTI_SPAN_ID,
                title="MEET1",
                question="What did speaker 1 offer to do?",
                context=dev_multi_context,
                is_impossible=False,
                answer_text=[
                    "I can help with that.\n Speaker 0: Let's also check the budget.\n "
                    "Speaker 1: Sure, I'll look at the budget too."
                ],
                answer_start=[dev_multi_context.find("I can help with that.")],
            ),
            _flat_item(
                example_id=DEV_UNANSWERABLE_ID,
                title="MEET1",
                question="What is the capital of France?",
                context=dev_unanswerable_context,
                is_impossible=True,
                answer_text=[],
                answer_start=[],
            ),
            _flat_item(
                example_id=DEV_FALLBACK_ID,
                title="MEET2",
                question="When is the deadline?",
                context=dev_fallback_context,
                is_impossible=False,
                answer_text=["The deadline is Friday."],
                answer_start=[dev_fallback_answer_start],
            ),
        ],
    }

    dev_ms = {
        "version": "0.1.0-fixture",
        "data": [
            _ms_item(example_id=DEV_SINGLE_SPAN_ID, tokens=dev_single_tokens, answer_token_indices=range(8, 12)),
            _ms_item(
                example_id=DEV_MULTI_SPAN_ID,
                tokens=dev_multi_tokens,
                answer_token_indices=list(range(8, 13)) + list(range(22, 29)),
            ),
            _ms_item(example_id=DEV_UNANSWERABLE_ID, tokens=dev_unanswerable_tokens, answer_token_indices=[]),
            # DEV_FALLBACK_ID deliberately absent -- the flat_fallback case.
        ],
    }

    train_flat = {
        "version": "0.1.0-fixture",
        "data": [
            _flat_item(
                example_id=TRAIN_ID,
                title="MEET1",
                question="What did speaker 1 say?",
                context=train_context,
                is_impossible=False,
                answer_text=["Great, let's begin."],
                answer_start=[train_context.find("Great, let's begin.")],
            ),
        ],
    }
    train_ms = {
        "version": "0.1.0-fixture",
        "data": [
            _ms_item(example_id=TRAIN_ID, tokens=train_tokens, answer_token_indices=range(8, 11)),
        ],
    }

    _write_json(root / "AllData" / "Dataset" / "final-AMI-dev.json", dev_flat)
    _write_json(root / "AllData" / "MultiSpanDataset" / "final-AMI-ms-dev.json", dev_ms)
    _write_json(root / "AllData" / "Dataset" / "final-AMI-train.json", train_flat)
    _write_json(root / "AllData" / "MultiSpanDataset" / "final-AMI-ms-train.json", train_ms)


def build_tiny_ami_audio_tree(root: Path, meeting_ids: tuple[str, ...] = ("MEET1", "MEET2")) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for meeting_id in meeting_ids:
        audio_path = root / "amicorpus" / meeting_id / "audio" / f"{meeting_id}.Mix-Headset.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"RIFF....WAVEfmt fixture-not-real-audio")
