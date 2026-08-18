"""SAER-M computation: per-statement speaker-attribution accuracy over
minutes sentences, scored against E2's resolved ``EvidenceLink`` structures.

The metric's precise definition, worked micro-examples, and
PRE-REGISTERED-DRAFT status live in
``docs/readiness/2026-08-18-saer-m-definition.md``. This module is the
reference implementation that document describes: no scoring logic should
exist here that is not also stated in that document, and no claim in that
document should exist that this module does not implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from meeting_minutes_agent.corpora.nxt.models import EvidenceLink

__all__ = [
    "SpeakerAttributionPrediction",
    "SentenceAttributionResult",
    "SaerMReport",
    "compute_saer_m",
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
    string)."""

    sentence_id: str
    predicted_speaker: str | None


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
    (sentence -> speaker set) table, join against ``predictions``, and
    classify every sentence id seen on either side into the SAER-M error
    taxonomy (correct / wrong_speaker / unattributed / hallucinated_speaker
    / not_scored)."""

    gold_table = _gold_speaker_table(evidence_links)
    pred_table = {p.sentence_id: p.predicted_speaker for p in predictions}

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
