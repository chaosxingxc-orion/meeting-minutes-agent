"""MeetingQA official-release loader (component C6 precondition, G1
preregistration draft SS6: "qa head unstub + MeetingQA loader (small
ticket)").

Loads the upstream ``adobe-research/meetingqa`` release's per-split JSON
files (the record shape frozen in the umbrella
``docs/datasets.lock.json``'s ``meetingqa`` entry) into
:class:`MeetingQAExample` records, and resolves each example's meeting id
to its audio-path REFERENCE (never bytes) under the governed
``ami-meeting-corpus`` layout.

Real-schema surprises found while building this reader (verified against
the acquired release under ``datasets/meetingqa/`` -- none of this is
documented in the upstream README, which only describes the DataCollection/
PostAnnotationProcessing code that PRODUCES these files, not their final
shape):

1. The per-split file (``AllData/Dataset/final-AMI-<split>.json``) is
   ``{"version": ..., "data": [...]}`` where ``data`` is a FLAT list of
   SQuAD-shaped QA records (``context``, ``question``, ``title``, ``id``,
   ``is_impossible``, ``answers": {"text": [...], "answer_start": [...]}``)
   -- NOT the nested SQuAD ``article -> paragraphs -> qas`` structure the
   field names might suggest. ``title`` is the AMI meeting id (e.g.
   ``"EN2001b"``) for every record in that record's own group, not an
   article-level grouping key.

2. ``context`` embeds speaker turns as literal ``"Speaker <n>: <text>\\n "``
   runs, where ``<n>`` is a per-meeting-local, 0-indexed face id -- NOT
   AMI's own participant letters (A/B/C/D). This inline prefix is the ONLY
   per-instance speaker signal the official schema carries (there is no
   separate top-level speaker field); :func:`_speakers_in_context` extracts
   the distinct ids referenced by one example's context as this reader's
   answer to "any speaker fields".

3. ``answers.text``/``answers.answer_start`` in the flat file is UNRELIABLE
   for locating a span and actively LOSSY for a genuinely multi-span
   answer. Measured on the acquired dev split: only 1076/1631 (66%)
   answerable examples satisfy
   ``context[answer_start:answer_start+len(text)] == text``. The failures
   are not corrupt data -- they are multi-span answers where upstream
   post-processing recorded ONE bounding string running from the start of
   the first true sub-span to the end of the last (silently dropping the
   intervening non-answer turn(s) from the recorded ``text``) while leaving
   ``answer_start`` pointing at that same position in the FULL,
   untruncated context. This reader therefore never trusts ``answer_start``
   and never uses the flat file's ``answers.text`` as the multi-span
   source of truth.

4. The real multi-span ground truth lives in the SEPARATE
   ``AllData/MultiSpanDataset/final-AMI-ms-<split>.json`` file: same ``id``
   join key, ``context``/``question`` given as whitespace-split token
   lists (split on a single literal space -- ``str.split(" ")`` -- which is
   why a token at a turn boundary keeps a trailing ``"\\n"`` glued onto it,
   e.g. ``"way.\\n"``), and a per-token BIO-style ``labels`` list (``"O"`` /
   ``"I_ANSWER"``) whose contiguous non-``"O"`` runs ARE the answer spans.
   549/2251 dev examples decode to more than one contiguous run (a true
   multi-span answer); an ``is_impossible`` example decodes to an
   all-``"O"`` row (verified), i.e. zero spans -- already the empty-tuple
   abstention shape :mod:`meeting_minutes_agent.metrics.qa` expects. This
   reader decodes spans from THIS file, joining each run's tokens with a
   single space and collapsing embedded whitespace (:func:`_decode_bio_spans`),
   never from the flat file's ``answers`` field.

5. The two files are not perfectly aligned: on the acquired dev split
   exactly one flat-file id (``"0-0-1-TS3006c-828"``, answerable, single-
   span) is ABSENT from the multi-span file. For an id missing from the
   multi-span file, this reader falls back to the flat file's
   ``answers.text`` tuple as a best-effort single/zero-span answer and
   records that provenance on :attr:`MeetingQAExample.span_source`.

6. A ``final-AMI-<split>-meta.json`` file also ships alongside the pair
   above (seen for ``test``) carrying the official per-example
   ``impossible``/``multispan``/``multispeaker`` booleans the upstream eval
   script uses to slice its report; NOT consumed by this reader (out of
   scope -- see the comparability note below).

Comparability note (flagged, not resolved -- see the G1 preregistration
draft, "QA: ... comparability check against the MeetingQA paper's own
scoring script REQUIRED before any cross-paper comparison"): the upstream
scorer (``qaCode/custom_evaluate.py``) scores via HuggingFace's
``squad_v2`` metric (SQuAD 2.0 exact-match + F1 with a
``no_answer_probability`` threshold) after stripping every literal
``"Speaker <n>: "`` prefix from BOTH reference and prediction text, using
SQuAD's own normalization (which additionally drops English articles
a/an/the -- :mod:`meeting_minutes_agent.metrics.qa`'s
:class:`~meeting_minutes_agent.metrics.qa.NormalizationRules` does not).
For multi-span questions the upstream scorer still compares ONE joined
string per example against ``squad_v2`` (``" ".join(answers.text)``) and
slices the report using the ``meta.multispan``/``meta.multispeaker`` flags
from item 6 above -- it has no independent multi-span structural score.
It also reports a word-Jaccard number, which IS the same token-set
intersection/union formula as this repository's
:func:`meeting_minutes_agent.metrics.qa._token_iou`. None of these gaps
(metric family, speaker-prefix stripping, article removal, multi-span
scoring method) are closed by this loader; they must be bounded before any
number from this pipeline is compared against the MeetingQA paper's own
table.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SPLITS: tuple[str, ...] = ("train", "dev", "test")

_DATASET_SUBDIR = "AllData/Dataset"
_MULTISPAN_SUBDIR = "AllData/MultiSpanDataset"
_DATASET_FILENAME = "final-AMI-{split}.json"
_MULTISPAN_FILENAME = "final-AMI-ms-{split}.json"

_SPEAKER_RE = re.compile(r"Speaker (\d+):")
_WS_RE = re.compile(r"\s+")

AMI_AUDIO_SUBDIR = "amicorpus"
AMI_AUDIO_SUFFIX = ".Mix-Headset.wav"


class MeetingQASplitError(ValueError):
    """Raised for an invalid ``split`` argument -- fail-closed rather than
    silently falling back to any one split (the split-discipline
    requirement: "no default that silently reads test")."""


class MeetingAudioNotResolvedError(FileNotFoundError):
    """Raised by :func:`resolve_audio_path` (default ``require_exists=True``)
    when a MeetingQA meeting id has no corresponding Mix-Headset WAV under
    the local AMI corpus layout -- fail-closed rather than handing a caller
    a path reference that silently points at nothing."""


@dataclass(frozen=True)
class MeetingQAExample:
    """One MeetingQA question over one AMI meeting.

    ``answer_spans`` is ``()`` for BOTH an unanswerable question
    (``unanswerable is True``) and a question this reader could not recover
    any span for; :attr:`span_source` disambiguates provenance. This is the
    exact shape :class:`meeting_minutes_agent.metrics.qa.QAExample` expects
    for ``reference_spans``.

    ``audio_path`` is a REFERENCE only -- this loader never opens or reads
    the WAV; see :func:`resolve_audio_path`.
    """

    example_id: str
    meeting_id: str
    split: str
    question: str
    context: str
    unanswerable: bool
    answer_spans: tuple[str, ...]
    span_source: str  # "decoded_multi_span" | "flat_fallback" | "unanswerable"
    speakers: tuple[str, ...]
    audio_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "meeting_id": self.meeting_id,
            "split": self.split,
            "question": self.question,
            "context": self.context,
            "unanswerable": self.unanswerable,
            "answer_spans": list(self.answer_spans),
            "span_source": self.span_source,
            "speakers": list(self.speakers),
            "audio_path": str(self.audio_path),
        }


def resolve_audio_path(ami_root: Path | str, meeting_id: str, *, require_exists: bool = True) -> Path:
    """Resolve ``meeting_id`` to its Mix-Headset WAV path under the local
    AMI corpus layout (``<ami_root>/amicorpus/<meeting_id>/audio/
    <meeting_id>.Mix-Headset.wav`` -- the layout the governed
    ``ami-meeting-corpus`` asset materializes, ``media_type: "Mix-Headset"``
    per the umbrella dataset lock's selector). Returns the path REFERENCE
    only; the caller reads bytes, not this function.

    ``require_exists=True`` (the default) fails closed: a meeting id that
    does not resolve to a real file is a corpus-join defect worth stopping
    on, not a silently-wrong reference a downstream head could be pointed
    at. Pass ``require_exists=False`` to get the templated path regardless
    (e.g. to inspect what path a meeting id WOULD resolve to on a machine
    without the audio bytes materialized)."""

    path = Path(ami_root) / AMI_AUDIO_SUBDIR / meeting_id / "audio" / f"{meeting_id}{AMI_AUDIO_SUFFIX}"
    if require_exists and not path.is_file():
        raise MeetingAudioNotResolvedError(
            f"resolve_audio_path: no Mix-Headset audio found for MeetingQA meeting id {meeting_id!r} "
            f"under AMI root {Path(ami_root)!s} (expected {path})"
        )
    return path


def _speakers_in_context(context: str) -> tuple[str, ...]:
    """Distinct per-meeting-local speaker face ids referenced in ``context``
    (see module docstring item 2), in ascending numeric order."""

    return tuple(sorted(set(_SPEAKER_RE.findall(context)), key=int))


def _decode_bio_spans(tokens: list[str], labels: list[str]) -> tuple[str, ...]:
    """Decode a MultiSpanDataset ``(tokens, labels)`` pair into the ordered
    tuple of contiguous non-``"O"`` runs, each run's tokens joined with a
    single space and its embedded whitespace (e.g. a token's glued-on
    ``"\\n"``, module docstring item 4) collapsed. Zero runs (an all-``"O"``
    row) decodes to ``()`` -- the abstention shape."""

    spans: list[str] = []
    current: list[str] = []
    for tok, lab in zip(tokens, labels):
        if lab != "O":
            current.append(tok)
        elif current:
            spans.append(_WS_RE.sub(" ", " ".join(current)).strip())
            current = []
    if current:
        spans.append(_WS_RE.sub(" ", " ".join(current)).strip())
    return tuple(spans)


def _load_json_data(path: Path) -> list[Mapping[str, Any]]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    return payload["data"]


def _index_multi_span(items: list[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    decoded: dict[str, tuple[str, ...]] = {}
    for item in items:
        decoded[item["id"]] = _decode_bio_spans(item["context"], item["labels"])
    return decoded


def load_split(
    *,
    meetingqa_root: Path | str,
    ami_root: Path | str,
    split: str,
    require_audio: bool = True,
) -> tuple[MeetingQAExample, ...]:
    """Load one official MeetingQA split. ``split`` is REQUIRED (keyword-
    only, no default) and must be one of :data:`SPLITS` -- there is no
    fallback split a missing/misspelled argument could silently resolve to.

    ``meetingqa_root`` is the acquired ``adobe-research/meetingqa`` release
    root (the umbrella lock's ``meetingqa.local_subdir``); ``ami_root`` is
    the acquired AMI corpus root (``ami-meeting-corpus.local_subdir``) used
    only for :func:`resolve_audio_path`. Every distinct meeting id in the
    split is resolved at most once (the same ~166 meetings are referenced
    by thousands of examples)."""

    if split not in SPLITS:
        raise MeetingQASplitError(f"load_split: split must be one of {SPLITS}, got {split!r}")

    meetingqa_root = Path(meetingqa_root)
    dataset_path = meetingqa_root / _DATASET_SUBDIR / _DATASET_FILENAME.format(split=split)
    multi_span_path = meetingqa_root / _MULTISPAN_SUBDIR / _MULTISPAN_FILENAME.format(split=split)

    flat_items = _load_json_data(dataset_path)
    multi_span_by_id = _index_multi_span(_load_json_data(multi_span_path)) if multi_span_path.is_file() else {}

    audio_cache: dict[str, Path] = {}

    def _audio_for(meeting_id: str) -> Path:
        if meeting_id not in audio_cache:
            audio_cache[meeting_id] = resolve_audio_path(ami_root, meeting_id, require_exists=require_audio)
        return audio_cache[meeting_id]

    examples: list[MeetingQAExample] = []
    for item in flat_items:
        example_id = item["id"]
        meeting_id = item["title"]
        unanswerable = bool(item["is_impossible"])

        if unanswerable:
            answer_spans: tuple[str, ...] = ()
            span_source = "unanswerable"
        elif example_id in multi_span_by_id:
            answer_spans = multi_span_by_id[example_id]
            span_source = "decoded_multi_span"
        else:
            answer_spans = tuple(item["answers"]["text"])
            span_source = "flat_fallback"

        examples.append(
            MeetingQAExample(
                example_id=example_id,
                meeting_id=meeting_id,
                split=split,
                question=item["question"],
                context=item["context"],
                unanswerable=unanswerable,
                answer_spans=answer_spans,
                span_source=span_source,
                speakers=_speakers_in_context(item["context"]),
                audio_path=_audio_for(meeting_id),
            )
        )

    return tuple(examples)


__all__ = [
    "SPLITS",
    "AMI_AUDIO_SUBDIR",
    "AMI_AUDIO_SUFFIX",
    "MeetingQASplitError",
    "MeetingAudioNotResolvedError",
    "MeetingQAExample",
    "resolve_audio_path",
    "load_split",
]
