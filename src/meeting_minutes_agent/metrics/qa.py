"""MeetingQA scorer: macro-averaged SQuAD-style token F1 + token IoU, with
empty-string abstention scoring, multi-span (sentence-set) support, and a
deterministic normalization layer whose rule list is serialized and hashed
alongside every report.

Design notes (for the coordinator; also see the final E5 report):

- Unanswerable questions are represented with an EMPTY reference span tuple
  (``reference_spans == ()``). Abstaining is represented the same way on the
  prediction side (``prediction_spans == ()``). Both empty is a perfect
  score (1.0); this is what "unanswerables scored against the empty string"
  means concretely -- there is no separate empty-string sentinel, an empty
  tuple already IS the empty string case.
- Multi-span answers (``len(spans) > 1``) are scored by flattening every
  span in the set into ONE token bag per side (concatenate-then-normalize),
  then applying the ordinary token F1 / token IoU formula to the two bags.
  This is the simplest aggregation that stays hand-verifiable on a small
  fixture; it does NOT attempt span-to-span alignment within the set (e.g.
  matching predicted span 1 against reference span 2). That is a design
  choice, not an oversight -- flag it to the coordinator if per-span
  alignment turns out to matter for the eventual MeetingQA question set.
- Abstention and multi-span sub-metrics are reported separately from the
  pooled macro F1/IoU per the task brief ("the deep check requires them
  visible") -- see :class:`QAScoreReport`.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

# ---------------------------------------------------------------------------
# Normalization layer
# ---------------------------------------------------------------------------

_NUMBER_WORDS: dict[str, str] = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_DIGIT_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")


@dataclass(frozen=True)
class NormalizationRules:
    """Which normalization steps are active. The active subset is exactly
    what gets serialized into :meth:`rule_list` / hashed by
    :meth:`content_hash` -- a report's normalization is reproducible from
    the hash alone plus this class's fixed step order (case, then
    number-form, then punctuation, then whitespace collapse)."""

    lowercase: bool = True
    strip_punctuation: bool = True
    normalize_number_form: bool = True

    def rule_list(self) -> tuple[str, ...]:
        rules: list[str] = []
        if self.lowercase:
            rules.append("lowercase")
        if self.normalize_number_form:
            rules.append("normalize_number_form")
        if self.strip_punctuation:
            rules.append("strip_punctuation")
        rules.append("collapse_whitespace")  # always active, not a toggle
        return tuple(rules)

    def content_hash(self) -> str:
        from meeting_minutes_agent.runreceipt import config_hash

        return config_hash({"rules": list(self.rule_list())})


DEFAULT_NORMALIZATION_RULES = NormalizationRules()


def normalize_answer(text: str, rules: NormalizationRules = DEFAULT_NORMALIZATION_RULES) -> str:
    """Apply the active rules in a fixed order: lowercase -> number-form
    (word-to-digit substitution for single-word cardinals zero..ninety plus
    hundred/thousand, and de-comma-ing thousands separators like "1,000")
    -> punctuation stripping -> whitespace collapse. Number-form runs
    BEFORE punctuation stripping specifically so "1,000" de-commas to
    "1000" instead of being torn into "1 000" by generic punctuation
    stripping.

    Limitation (documented, not hidden): number-word substitution is
    single-token only ("twenty" -> "20") and does not compose compound
    number words ("twenty-one" is untouched beyond hyphen stripping).
    """

    s = text
    if rules.lowercase:
        s = s.lower()
    if rules.normalize_number_form:
        s = _DIGIT_COMMA_RE.sub("", s)
        s = " ".join(_NUMBER_WORDS.get(tok, tok) for tok in s.split())
    if rules.strip_punctuation:
        s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _span_set_tokens(spans: Sequence[str], rules: NormalizationRules) -> list[str]:
    tokens: list[str] = []
    for span in spans:
        tokens.extend(normalize_answer(span, rules).split())
    return tokens


def _token_f1(pred_tokens: Sequence[str], ref_tokens: Sequence[str]) -> float:
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _token_iou(pred_tokens: Sequence[str], ref_tokens: Sequence[str]) -> float:
    pred_set, ref_set = set(pred_tokens), set(ref_tokens)
    if not pred_set and not ref_set:
        return 1.0
    union = pred_set | ref_set
    if not union:
        return 0.0
    return len(pred_set & ref_set) / len(union)


# ---------------------------------------------------------------------------
# Example / report shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QAExample:
    """One MeetingQA example. ``reference_spans`` / ``prediction_spans`` are
    tuples of zero or more answer strings: zero for "unanswerable"
    (reference side) or "abstained" (prediction side), one for an ordinary
    single-span answer, more than one for a multi-span (sentence-set)
    answer."""

    example_id: str
    reference_spans: tuple[str, ...]
    prediction_spans: tuple[str, ...]

    @property
    def is_unanswerable(self) -> bool:
        return len(self.reference_spans) == 0

    @property
    def is_abstention(self) -> bool:
        return len(self.prediction_spans) == 0

    @property
    def is_multi_span(self) -> bool:
        return len(self.reference_spans) > 1


@dataclass(frozen=True)
class QAExampleScore:
    example_id: str
    f1: float
    iou: float
    is_unanswerable: bool
    is_abstention: bool
    is_multi_span: bool
    correctly_abstained: bool  # unanswerable AND abstained
    falsely_abstained: bool  # answerable BUT abstained


def score_example(example: QAExample, rules: NormalizationRules = DEFAULT_NORMALIZATION_RULES) -> QAExampleScore:
    pred_tokens = _span_set_tokens(example.prediction_spans, rules)
    ref_tokens = _span_set_tokens(example.reference_spans, rules)
    return QAExampleScore(
        example_id=example.example_id,
        f1=_token_f1(pred_tokens, ref_tokens),
        iou=_token_iou(pred_tokens, ref_tokens),
        is_unanswerable=example.is_unanswerable,
        is_abstention=example.is_abstention,
        is_multi_span=example.is_multi_span,
        correctly_abstained=example.is_unanswerable and example.is_abstention,
        falsely_abstained=(not example.is_unanswerable) and example.is_abstention,
    )


@dataclass(frozen=True)
class QAScoreReport:
    """Pooled + sub-metric report. ``macro_f1``/``macro_iou`` average over
    ALL examples (answerable, unanswerable, single- and multi-span alike --
    the standard SQuAD-style macro average). Abstention and multi-span
    numbers are broken out separately per the task brief."""

    n_examples: int
    macro_f1: float
    macro_iou: float

    n_unanswerable: int
    abstention_accuracy: float | None  # over unanswerable examples only; None if n_unanswerable == 0

    n_answerable: int
    false_abstention_rate: float | None  # over answerable examples only; None if n_answerable == 0

    n_multi_span: int
    multi_span_macro_f1: float | None
    multi_span_macro_iou: float | None

    normalization_rules: tuple[str, ...]
    normalization_rules_hash: str

    per_example: tuple[QAExampleScore, ...] = field(default_factory=tuple)


def score_qa_examples(
    examples: Sequence[QAExample],
    rules: NormalizationRules = DEFAULT_NORMALIZATION_RULES,
) -> QAScoreReport:
    if not examples:
        raise ValueError("score_qa_examples: examples must be non-empty")

    scores = tuple(score_example(ex, rules) for ex in examples)

    macro_f1 = sum(s.f1 for s in scores) / len(scores)
    macro_iou = sum(s.iou for s in scores) / len(scores)

    unanswerable = [s for s in scores if s.is_unanswerable]
    abstention_accuracy = (
        sum(1 for s in unanswerable if s.correctly_abstained) / len(unanswerable) if unanswerable else None
    )

    answerable = [s for s in scores if not s.is_unanswerable]
    false_abstention_rate = (
        sum(1 for s in answerable if s.falsely_abstained) / len(answerable) if answerable else None
    )

    multi_span = [s for s in scores if s.is_multi_span]
    multi_span_macro_f1 = sum(s.f1 for s in multi_span) / len(multi_span) if multi_span else None
    multi_span_macro_iou = sum(s.iou for s in multi_span) / len(multi_span) if multi_span else None

    return QAScoreReport(
        n_examples=len(scores),
        macro_f1=macro_f1,
        macro_iou=macro_iou,
        n_unanswerable=len(unanswerable),
        abstention_accuracy=abstention_accuracy,
        n_answerable=len(answerable),
        false_abstention_rate=false_abstention_rate,
        n_multi_span=len(multi_span),
        multi_span_macro_f1=multi_span_macro_f1,
        multi_span_macro_iou=multi_span_macro_iou,
        normalization_rules=rules.rule_list(),
        normalization_rules_hash=rules.content_hash(),
        per_example=scores,
    )
