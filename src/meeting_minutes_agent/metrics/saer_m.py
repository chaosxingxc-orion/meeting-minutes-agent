"""SAER-M computation: per-statement speaker-attribution accuracy over
minutes sentences, scored against E2's resolved ``EvidenceLink`` structures.

The metric's precise definition, worked micro-examples, and
PRE-REGISTERED-DRAFT status live in
``docs/readiness/2026-08-18-saer-m-definition.md``. This module is the
reference implementation that document describes: no scoring logic should
exist here that is not also stated in that document, and no claim in that
document should exist that this module does not implement.

SAER-M definition v1.1 (in-module note; the doc file itself is not edited
here -- the coordinator handles doc-side versioning at the next read
registration)
--------------------------------------------------------------------------
Finding that motivated this note: the G1 floors read
(``docs/readiness/2026-08-19-g1-floors-verdict.md`` S1e) found SAER-M
scored 0.0 on all 24 (arm x scoreable-meeting) cells not because
attribution was wrong, but because the join underneath ``compute_saer_m``
was an EXACT ``sentence_id`` join, and the two sides never share an id
space: gold sentence ids are NXT corpus ids
(``"ES2011a.JacquelinePalmer.s.1"``); the minutes head (``heads.minutes``)
synthesizes its own bullet ids as ``"<section>-<index>"`` (``"abstract-0"``,
...) because a generative head has no corpus-assigned sentence id to draw
on. The intersection of the two id spaces is empty by construction, so
every gold sentence read as ``unattributed`` and every predicted bullet
read as ``hallucinated_speaker`` regardless of what either one actually
said -- a join failure reported as a capability floor.

v1.1 fixes the join, not the taxonomy: :func:`compute_saer_m` now content-
aligns predictions to gold sentences BEFORE the exact-id join in
:func:`_score_sentence` runs, and that classify/count step is byte-for-byte
unchanged from v1 (this module's docstring promise -- "no claim in the
definition doc that this module does not implement" -- continues to hold
for the five-way taxonomy; only the input to the join is new).

- **Method**: :data:`SAER_M_ALIGNMENT_METHOD` = ``"token_f1"``, a SQuAD-
  style bag-of-words F1 (:func:`token_f1`) over lowercased ``[a-z0-9]+``
  tokens (``.split()``-adjacent, punctuation-stripped, no stopword removal,
  no stemming -- the smallest normalization that survives minor
  casing/punctuation drift between a generated bullet and its paraphrased
  gold sentence without pulling in a second NLP dependency; stdlib
  ``re``/``collections.Counter`` only, matching the task brief's
  stdlib+numpy constraint with no numpy actually needed for a scalar bag-
  of-words overlap).
- **Threshold**: :data:`SAER_M_ALIGNMENT_F1_THRESHOLD` = ``0.3``. Chosen
  conservatively low, not empirically tuned (no labelled bullet-to-sentence
  alignment exists to tune against): a generated minutes bullet is a
  paraphrase of the transcript, and a gold NXT abstractive sentence is
  ITSELF a paraphrase of the same transcript, so two independently-authored
  paraphrases of the same event are expected to share a real but partial
  vocabulary, not near-verbatim wording. 0.3 rules out coincidental
  stopword-only overlap (two unrelated sentences sharing only "the"/"a"
  score far below it) while tolerating heavy rewording. This is a
  provisional heuristic pinned for determinism and auditability, flagged
  here exactly like the definition doc's own open questions (micro/macro
  averaging, ambiguous-gold leniency, section weighting) for coordinator
  recalibration, not a claim that 0.3 is optimal.
- **Matching shape**: one gold sentence aligns to at most one prediction and
  vice versa (:func:`align_predictions_to_gold_sentences` is a greedy
  maximum-weight one-to-one assignment over every ``(prediction, gold
  sentence)`` pair scoring at or above the threshold, processed in
  descending score order with a deterministic ``(gold_sentence_id,
  prediction_index)`` tie-break) -- a single strong bullet is prevented from
  "double-booking" two different gold sentences and starving a real,
  weaker match for the second one.
- **Backward compatibility**: alignment only considers predictions carrying
  non-``None``, non-empty :attr:`SpeakerAttributionPrediction.text` AND a
  non-``None`` ``predicted_speaker`` (nothing to align on, or nothing to
  attribute, otherwise). A prediction with no ``text`` set (the field's
  default) never enters alignment and keeps its original ``sentence_id``,
  so the pre-v1.1 exact-id-join behaviour is preserved unchanged when
  callers do not populate ``text`` -- v1.1 is strictly additive at the
  input layer.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence

from meeting_minutes_agent.corpora.nxt.models import EvidenceLink

__all__ = [
    "SpeakerAttributionPrediction",
    "SentenceAttributionResult",
    "SaerMReport",
    "compute_saer_m",
    "SAER_M_ALIGNMENT_METHOD",
    "SAER_M_ALIGNMENT_F1_THRESHOLD",
    "token_f1",
    "align_predictions_to_gold_sentences",
]

# Error taxonomy (see the definition doc for the worked examples).
OUTCOME_CORRECT = "correct"
OUTCOME_WRONG_SPEAKER = "wrong_speaker"
OUTCOME_UNATTRIBUTED = "unattributed"
OUTCOME_HALLUCINATED_SPEAKER = "hallucinated_speaker"
OUTCOME_NOT_SCORED = "not_scored"  # no gold evidence AND no prediction -- excluded from every count


@dataclass(frozen=True)
class SpeakerAttributionPrediction:
    """One system-produced (minutes sentence id -> attributed speaker)
    guess. ``predicted_speaker is None`` means the system did not attribute
    a speaker to this sentence at all (distinct from attributing an empty
    string). ``text`` is the bullet's own generated text, optional (default
    ``None``) for backward compatibility with callers that only ever had a
    corpus-assigned ``sentence_id`` to give -- see the module docstring's
    v1.1 note: it is what :func:`align_predictions_to_gold_sentences`
    matches against a gold sentence's text when ``sentence_id`` itself
    cannot be expected to coincide with the gold id (a generative head's
    synthesized ``"<section>-<index>"`` id vs a corpus id)."""

    sentence_id: str
    predicted_speaker: str | None
    text: str | None = None


@dataclass(frozen=True)
class SentenceAttributionResult:
    sentence_id: str
    gold_speakers: tuple[str, ...]
    predicted_speaker: str | None
    outcome: str


def _gold_speaker_table(evidence_links: Sequence[EvidenceLink]) -> dict[str, tuple[str, ...]]:
    """One minutes sentence can be supported by more than one
    ``EvidenceLink`` (multiple summlink entries into the same sentence) and
    a single link's ``speaker`` field is itself ``"speakerA|speakerB"``
    when its dialogue acts span more than one agent (see
    ``MeetingResolver.resolve_evidence_links``). Both are folded into one
    gold SET of speakers per sentence; a prediction naming any member of
    that set counts as correct (see the definition doc's ambiguous-gold
    worked example)."""

    table: dict[str, set[str]] = {}
    for link in evidence_links:
        if not link.speaker:
            continue
        speakers = link.speaker.split("|")
        table.setdefault(link.sentence_id, set()).update(speakers)
    return {sentence_id: tuple(sorted(speakers)) for sentence_id, speakers in table.items()}


def _score_sentence(
    sentence_id: str,
    gold_speakers: tuple[str, ...],
    predicted_speaker: str | None,
) -> SentenceAttributionResult:
    has_gold = len(gold_speakers) > 0
    has_pred = predicted_speaker is not None

    if not has_gold and not has_pred:
        outcome = OUTCOME_NOT_SCORED
    elif has_gold and not has_pred:
        outcome = OUTCOME_UNATTRIBUTED
    elif not has_gold and has_pred:
        outcome = OUTCOME_HALLUCINATED_SPEAKER
    elif predicted_speaker in gold_speakers:
        outcome = OUTCOME_CORRECT
    else:
        outcome = OUTCOME_WRONG_SPEAKER

    return SentenceAttributionResult(
        sentence_id=sentence_id,
        gold_speakers=gold_speakers,
        predicted_speaker=predicted_speaker,
        outcome=outcome,
    )


# ---------------------------------------------------------------------------
# v1.1 content-based alignment (module docstring's "SAER-M definition v1.1")
# ---------------------------------------------------------------------------

SAER_M_ALIGNMENT_METHOD = "token_f1"
SAER_M_ALIGNMENT_F1_THRESHOLD = 0.3

_ALIGNMENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _alignment_tokens(text: str) -> Counter[str]:
    """Lowercased ``[a-z0-9]+`` tokens as a multiset. No stopword removal,
    no stemming -- see the module docstring's v1.1 "Method" note for why."""

    return Counter(_ALIGNMENT_TOKEN_RE.findall(text.lower()))


def token_f1(text_a: str, text_b: str) -> float:
    """SQuAD-style bag-of-words F1 between two texts' normalized token
    multisets: precision = shared / len(text_a), recall = shared /
    len(text_b), F1 = harmonic mean. ``0.0`` if either side has zero tokens
    after normalization, or if the two share no token at all (avoids a
    division by zero when precision and recall are both 0)."""

    tokens_a = _alignment_tokens(text_a)
    tokens_b = _alignment_tokens(text_b)
    total_a = sum(tokens_a.values())
    total_b = sum(tokens_b.values())
    if not total_a or not total_b:
        return 0.0
    shared = sum((tokens_a & tokens_b).values())
    if not shared:
        return 0.0
    precision = shared / total_a
    recall = shared / total_b
    return 2 * precision * recall / (precision + recall)


def align_predictions_to_gold_sentences(
    evidence_links: Sequence[EvidenceLink],
    predictions: Sequence[SpeakerAttributionPrediction],
    gold_speakers: Mapping[str, tuple[str, ...]],
) -> tuple[SpeakerAttributionPrediction, ...]:
    """Content-align ``predictions`` onto ``gold_speakers``'s sentence ids
    (the ids :func:`_gold_speaker_table` already restricted to sentences
    carrying at least one non-empty gold speaker -- the metric's own
    definition of "has gold evidence") by :func:`token_f1` over each gold
    sentence's ``EvidenceLink.sentence_text`` and each candidate
    prediction's ``text``.

    Only predictions with non-``None``/non-empty ``text`` AND a non-``None``
    ``predicted_speaker`` are candidates (nothing to align on, or nothing to
    attribute, otherwise -- see the module docstring's "Backward
    compatibility" note; an unattributed bullet's outcome is identical
    whether or not it is aligned, since the join treats a missing prediction
    the same as a present one with ``predicted_speaker=None``).

    Matching is a global greedy MAXIMUM-WEIGHT ONE-TO-ONE assignment: every
    ``(gold_sentence_id, prediction_index)`` pair scoring
    ``>= SAER_M_ALIGNMENT_F1_THRESHOLD`` is collected, sorted by descending
    F1 with a deterministic ``(gold_sentence_id, prediction_index)``
    tie-break, and claimed in that order as long as both sides are still
    free -- so one prediction can never satisfy two gold sentences (and vice
    versa), and the same input always produces the same assignment.

    A matched prediction is returned with its ``sentence_id`` REWRITTEN to
    the gold sentence id it aligned to (its ``predicted_speaker``/``text``
    unchanged); every unmatched prediction is returned unchanged, under its
    own original ``sentence_id`` (still eligible for the exact-id join
    downstream, e.g. a caller that happens to synthesize the real gold id
    directly -- the toy micro-example fixtures do exactly this)."""

    gold_texts: dict[str, str] = {}
    for link in evidence_links:
        if link.sentence_id in gold_speakers and link.sentence_id not in gold_texts:
            gold_texts[link.sentence_id] = link.sentence_text

    candidates = [
        (index, prediction)
        for index, prediction in enumerate(predictions)
        if prediction.text and prediction.predicted_speaker is not None
    ]
    if not candidates or not gold_texts:
        return tuple(predictions)

    scored_pairs: list[tuple[float, str, int]] = [
        (f1, gold_id, index)
        for gold_id, gold_text in gold_texts.items()
        for index, prediction in candidates
        for f1 in (token_f1(prediction.text or "", gold_text),)
        if f1 >= SAER_M_ALIGNMENT_F1_THRESHOLD
    ]
    scored_pairs.sort(key=lambda pair: (-pair[0], pair[1], pair[2]))

    claimed_gold: dict[str, int] = {}
    claimed_predictions: set[int] = set()
    for _f1, gold_id, index in scored_pairs:
        if gold_id in claimed_gold or index in claimed_predictions:
            continue
        claimed_gold[gold_id] = index
        claimed_predictions.add(index)

    aligned: list[SpeakerAttributionPrediction] = [
        prediction for index, prediction in enumerate(predictions) if index not in claimed_predictions
    ]
    for gold_id, index in claimed_gold.items():
        original = predictions[index]
        aligned.append(
            SpeakerAttributionPrediction(
                sentence_id=gold_id, predicted_speaker=original.predicted_speaker, text=original.text
            )
        )
    return tuple(aligned)


@dataclass(frozen=True)
class SaerMReport:
    n_scored: int  # sentences with gold evidence -- the accuracy denominator
    n_correct: int
    accuracy: float | None  # n_correct / n_scored; None if n_scored == 0

    n_wrong_speaker: int
    n_unattributed: int
    n_hallucinated_speaker: int
    n_not_scored: int  # no gold evidence AND no prediction; reported, excluded from accuracy

    per_sentence: tuple[SentenceAttributionResult, ...]


def compute_saer_m(
    evidence_links: Sequence[EvidenceLink],
    predictions: Sequence[SpeakerAttributionPrediction],
) -> SaerMReport:
    """SAER-M over one meeting: fold ``evidence_links`` into a gold
    (sentence -> speaker set) table, CONTENT-ALIGN ``predictions`` onto that
    table's sentence ids (:func:`align_predictions_to_gold_sentences` --
    module docstring's "SAER-M definition v1.1"; a no-op for any prediction
    whose ``sentence_id`` already IS a gold id, so v1 callers see no
    change), join the aligned predictions against the gold table by exact
    ``sentence_id``, and classify every sentence id seen on either side into
    the SAER-M error taxonomy (correct / wrong_speaker / unattributed /
    hallucinated_speaker / not_scored) -- this classify step is unchanged
    from v1."""

    gold_table = _gold_speaker_table(evidence_links)
    aligned_predictions = align_predictions_to_gold_sentences(evidence_links, predictions, gold_table)
    pred_table = {p.sentence_id: p.predicted_speaker for p in aligned_predictions}

    sentence_ids = sorted(set(gold_table) | set(pred_table))
    results = tuple(
        _score_sentence(sid, gold_table.get(sid, ()), pred_table.get(sid)) for sid in sentence_ids
    )

    n_correct = sum(1 for r in results if r.outcome == OUTCOME_CORRECT)
    n_wrong_speaker = sum(1 for r in results if r.outcome == OUTCOME_WRONG_SPEAKER)
    n_unattributed = sum(1 for r in results if r.outcome == OUTCOME_UNATTRIBUTED)
    n_hallucinated = sum(1 for r in results if r.outcome == OUTCOME_HALLUCINATED_SPEAKER)
    n_not_scored = sum(1 for r in results if r.outcome == OUTCOME_NOT_SCORED)

    n_scored = n_correct + n_wrong_speaker + n_unattributed
    accuracy = n_correct / n_scored if n_scored else None

    return SaerMReport(
        n_scored=n_scored,
        n_correct=n_correct,
        accuracy=accuracy,
        n_wrong_speaker=n_wrong_speaker,
        n_unattributed=n_unattributed,
        n_hallucinated_speaker=n_hallucinated,
        n_not_scored=n_not_scored,
        per_sentence=results,
    )
