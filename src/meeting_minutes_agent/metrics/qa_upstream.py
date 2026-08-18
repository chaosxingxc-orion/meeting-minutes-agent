"""Faithful, dependency-free reimplementation of the *upstream* MeetingQA
scorer's per-example scoring semantics, so it can be run side by side with
this repository's own macro token-F1 + IoU scorer
(:mod:`meeting_minutes_agent.metrics.qa`) on identical predictions/gold.

Every function and dataclass in this module is prefixed ``upstream_meetingqa``
(or ``Upstream...``) precisely so it can never be mistaken for, or promoted
to, this repository's headline metric -- :mod:`.qa`'s ``score_qa_examples``
remains the only metric this repository reports as its own result.

Upstream source of truth (read-only reference; this module neither imports
nor executes it):
``speechrl-data/datasets/meetingqa/qaCode/custom_evaluate.py`` (the
"official" MeetingQA repository's evaluation script, ACL 2023).

Upstream call graph, traced line by line:

- ``custom_evaluate.py:10-11`` -- ``remove_speakers(text)``::

      def remove_speakers(text):
          return re.sub(r'Speaker [0-9]*\\: ', '', text)

  Applied on BOTH sides: once per individual reference answer span
  (``custom_evaluate.py:30-32``, inside the loop that mutates
  ``references[r]['answers']['text'][i]`` in place, i.e. *before* any
  span is handed to the metric) and once to the (possibly already
  multi-span-joined -- see below) prediction string
  (``custom_evaluate.py:35``: ``remove_speakers(v)``). The pattern has no
  ``^`` anchor, so despite the "prefix stripping" framing it removes every
  occurrence of ``"Speaker <digits>: "`` anywhere in the text, not only a
  leading one; ``[0-9]*`` is zero-or-more, so ``"Speaker : "`` (no digits)
  also matches.
- ``custom_evaluate.py:36-37`` -- ``metric = load_metric("squad_v2");
  metrics = metric.compute(predictions=formatted_predictions,
  references=references)``. Upstream's own file contains no local F1/EM
  formula -- ``load_metric("squad_v2")`` is HuggingFace's ``evaluate``/
  ``datasets`` squad_v2 metric, so *that* package's math is what actually
  executes. The formulas below are transcribed from the public source
  (``huggingface/evaluate`` -- ``metrics/squad_v2/compute_score.py``:
  ``normalize_answer``, ``get_tokens``, ``compute_exact``, ``compute_f1``,
  ``get_raw_scores``; and ``metrics/squad_v2/squad_v2.py``: ``_compute``),
  fetched and cross-checked against the live GitHub source while writing
  this module, since that IS what ``load_metric("squad_v2")`` runs.
- ``custom_evaluate.py:14-18`` -- the ``pred_ref_type`` branch::

      predictions = predictions['data']
      for r, ref in enumerate(predictions):
          if not len(ref["answers"]['text']): predictions[r]['answers']['text'] = []
      predictions = {ex["id"]: " ".join(ex['answers']['text']) for ex in predictions}

  used ``"when the reference and the predictions are in the same format"``
  (``qaCode/README.md``, Evaluation section) -- i.e. when a prediction is
  itself given as a *structured* list of spans (the same
  ``answers.text``-list shape used for gold), those spans are joined with a
  single space into ONE string before scoring. This is the "multi-span
  answers scored as one joined string" behavior named in the work order.
  It is a PREDICTION-side transform only.

Design choices made explicit here (each is deep-checkable against the trace
above and against this module's own tests):

1.  **Gold multi-span handling is NOT a join.** HuggingFace squad_v2's
    ``get_raw_scores`` treats every entry of a reference's
    ``answers.text`` list as an alternative gold answer and scores the
    prediction against each independently, keeping the MAX F1/EM
    (``compute_score.py`` comment: ``"Take max over all gold answers"``).
    Upstream's own default/canonical invocation (``custom_evaluate.py``'s
    ``compute_metrics`` called *without* ``--pred-ref-type`` -- the exact
    command documented in ``qaCode/README.md``'s "Evaluation" section)
    passes MeetingQA's multi-span gold spans straight through as multiple
    alternatives, so a prediction that nails ONE of several genuinely
    distinct gold spans can score as well as one that covers all of them.
    That is reproduced here verbatim, not "corrected" -- contrast
    :mod:`.qa`'s module docstring, which documents the deliberately
    different flatten-then-score choice this repository's own scorer
    makes for BOTH sides. See ``tests/unit/metrics/test_qa_comparison.py``
    for a hand-computed fixture where this produces a materially
    different score than :mod:`.qa`.
2.  **Prediction multi-span handling mirrors the ``--pred-ref-type``
    join.** This repository's own QA head
    (:mod:`meeting_minutes_agent.heads.qa`) always emits a *structured*
    tuple of spans (``QAParseResult.answer_spans`` /
    ``QAExample.prediction_spans``) -- there is no free-text prediction
    string to begin with. The faithful mapping of that shape onto
    upstream's scorer is therefore the ``--pred-ref-type`` join path
    (``" ".join(prediction_spans)``), exactly as upstream applies it "when
    the reference and predictions are in the same format."
3.  **Unanswerable / no-answer convention.** HF squad_v2 filters gold
    texts through ``normalize_answer(...)`` truthiness and substitutes
    ``[""]`` when nothing survives (``get_raw_scores``); ``compute_f1``'s
    early return (``len(gold_toks) == 0 or len(pred_toks) == 0: return
    int(gold_toks == pred_toks)``) is what makes empty-vs-empty a perfect
    score and empty-vs-nonempty a zero. We reproduce that mechanism
    exactly rather than special-casing "is_unanswerable" ourselves the
    way :mod:`.qa` does. One subtlety this surfaces: because the filter
    is ``normalize_answer(t)`` truthiness (article/punctuation-stripped),
    a *structurally answerable* MeetingQA example whose single gold span
    is nothing but a stopword/article (e.g. ``"a"``, ``"the"``) is scored
    by upstream AS IF it were unanswerable (``gold_answers == [""]``),
    even though nothing upstream ever reclassifies it as such at the
    example-metadata level. :mod:`.qa`'s ``QAExample.is_unanswerable`` is
    purely structural (``len(reference_spans) == 0``) and has no
    equivalent degeneracy check, so the two scorers can diverge sharply
    on such examples -- see the comparison test fixture for a
    hand-computed case.
4.  **``no_answer_probability`` / ``no_answer_threshold`` are a dead
    branch here, not reimplemented.** ``custom_evaluate.py:35`` always
    passes ``"no_answer_probability": 0.0``, and never overrides
    ``no_answer_threshold`` (the squad_v2 metric's default is ``1.0``).
    HF's ``apply_no_ans_threshold`` computes ``pred_na = na_probs[qid] >
    na_prob_thresh``, i.e. ``0.0 > 1.0``, which is always ``False`` --
    so that function is a permanent no-op in this pipeline and every
    score is the raw ``get_raw_scores`` value. We do not model the
    no-answer-probability machinery at all.
5.  **Percentage scaling is presentation, not scoring, and is dropped.**
    ``custom_evaluate.py``'s ``compute_metrics`` reports
    ``100 * np.mean(...)`` rounded to 2 decimals
    (``metrics[key] = np.round(metrics[key], 2)``). This module returns
    plain ``0..1`` fractions -- the same scale :mod:`.qa` uses -- so the
    two metric families are directly numerically comparable; the
    ``x100``/``round(2)`` step is presentation, not part of the scoring
    semantics being reimplemented.
6.  **Out of scope, documented not silently dropped:** upstream's
    ``compute_metrics`` also reports a third metric, ``jaccard``
    (``custom_evaluate.py:40-45``) -- a RAW (no ``normalize_answer`` at
    all, so no lowercasing/punctuation/article handling), whitespace-only
    tokenized, set-based Jaccard similarity between the prediction and
    ONLY THE FIRST gold answer span (``ref['answers']['text'][0] if
    len(...) else ""`` -- i.e., unlike F1/EM, no max-over-alternatives),
    computed via the third-party ``textdistance`` library. The work order
    for this module names "squad_v2-style token F1 + exact match"
    specifically; ``jaccard`` is a distinct upstream sub-metric with its
    own distinct (first-span-only, unnormalized) semantics and is
    deliberately NOT reimplemented here to keep this module's scope and
    test coverage precise. A future extension implementing it should
    reuse ``upstream_meetingqa_remove_speaker_prefixes`` for the
    speaker-stripping step (still shared) but must NOT reuse
    ``upstream_meetingqa_normalize_answer`` (jaccard has no normalization
    step at all) or the max-over-gold-answers reduction (jaccard uses the
    first gold span only).
7.  **``qid_to_has_ans`` / HasAns-NoAns subset splitting is not
    reimplemented.** HF squad_v2's ``_compute`` also buckets scores into
    ``HasAns_*``/``NoAns_*`` subset averages using
    ``qid_to_has_ans = bool(qa["answers"]["text"])`` (raw list truthiness,
    evaluated BEFORE the ``normalize_answer`` filter described in point 3
    above -- so it does not itself perform the degeneracy reclassification,
    it just is never consulted). Nothing in ``custom_evaluate.py``'s own
    printed/returned output (``compute_metrics`` keeps only
    ``['f1', 'exact', 'jaccard']`` when ``meta`` is present, or prints the
    full dict otherwise but nothing downstream reads the HasAns/NoAns
    keys) ever consumes those subset fields -- MeetingQA's own
    answerable/unanswerable/multi-span/multi-speaker breakdowns
    (``compute_split_metrics``, ``custom_evaluate.py:55-83``) instead
    re-filter the raw example list by ``ex['meta']`` flags and call
    ``compute_metrics`` again per subset. Since it is both unused and
    score-inert, this module skips it.
"""

from __future__ import annotations

import re
import string
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from .qa import QAExample

# ---------------------------------------------------------------------------
# Upstream primitives (custom_evaluate.py + HF squad_v2's compute_score.py)
# ---------------------------------------------------------------------------

# custom_evaluate.py:10-11 -- re.sub(r'Speaker [0-9]*\: ', '', text); not
# anchored to string start, `[0-9]*` is zero-or-more digits.
_SPEAKER_PREFIX_RE = re.compile(r"Speaker [0-9]*: ")

# HF evaluate/datasets squad_v2 compute_score.py: ARTICLES_REGEX.
_ARTICLES_RE = re.compile(r"\b(a|an|the)\b", re.UNICODE)

# HF compute_score.py's remove_punc: set(string.punctuation), deleted (not
# replaced with a space) -- contrast .qa.normalize_answer, which replaces
# `[^\w\s]` with a space via _PUNCT_RE.
_PUNCTUATION_CHARS = frozenset(string.punctuation)


def upstream_meetingqa_remove_speaker_prefixes(text: str) -> str:
    """``custom_evaluate.py:10-11``'s ``remove_speakers``, verbatim."""

    return _SPEAKER_PREFIX_RE.sub("", text)


def upstream_meetingqa_normalize_answer(text: str) -> str:
    """HF squad_v2 ``compute_score.py``'s ``normalize_answer``, verbatim
    fixed step order: ``white_space_fix(remove_articles(remove_punc(lower(s))))``
    -- lowercase, then DELETE (not replace-with-space) every
    ``string.punctuation`` character, then remove whole-word
    ``a``/``an``/``the`` via a word-boundary regex substituted with a
    single space, then collapse/trim whitespace. No number-word handling
    (contrast :mod:`.qa`'s ``normalize_answer``, which has no article
    removal but does convert number words to digits)."""

    lowered = text.lower()
    no_punctuation = "".join(ch for ch in lowered if ch not in _PUNCTUATION_CHARS)
    no_articles = _ARTICLES_RE.sub(" ", no_punctuation)
    return " ".join(no_articles.split())


def upstream_meetingqa_tokens(text: str) -> list[str]:
    """HF squad_v2's ``get_tokens``: ``[] if not s else
    normalize_answer(s).split()`` -- the falsy-string short-circuit matters
    because ``normalize_answer("")`` is also ``""``, so this only differs
    from unconditionally calling ``.split()`` when ``text`` itself is
    falsy going in (kept for exact upstream fidelity)."""

    if not text:
        return []
    return upstream_meetingqa_normalize_answer(text).split()


def upstream_meetingqa_exact_match(gold: str, pred: str) -> float:
    """HF squad_v2's ``compute_exact``: normalized-string equality, as a
    ``0.0``/``1.0`` float (upstream returns ``int``; kept as ``float`` here
    for uniform averaging with F1)."""

    return 1.0 if upstream_meetingqa_normalize_answer(gold) == upstream_meetingqa_normalize_answer(pred) else 0.0


def upstream_meetingqa_f1(gold: str, pred: str) -> float:
    """HF squad_v2's ``compute_f1``, verbatim: token-multiset overlap F1,
    with the "either side has zero tokens" special case returning 1.0 if
    both sides are empty and 0.0 otherwise (this is what makes an
    unanswerable gold ``""`` against an abstained prediction ``""`` score
    a perfect 1.0, and against any non-empty prediction score 0.0)."""

    gold_tokens = upstream_meetingqa_tokens(gold)
    pred_tokens = upstream_meetingqa_tokens(pred)
    common = Counter(gold_tokens) & Counter(pred_tokens)
    num_same = sum(common.values())
    if len(gold_tokens) == 0 or len(pred_tokens) == 0:
        return 1.0 if gold_tokens == pred_tokens else 0.0
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Per-example / report shapes -- reuses .qa.QAExample as the shared input
# shape (its reference_spans/prediction_spans tuples already match the
# upstream answers.text-list shape on both sides).
# ---------------------------------------------------------------------------


def _upstream_prediction_text(prediction_spans: tuple[str, ...]) -> str:
    """``--pred-ref-type`` join (design choice 2 above) then speaker-prefix
    strip, matching the ORDER of ``custom_evaluate.py:18`` (join) followed
    by ``custom_evaluate.py:35`` (``remove_speakers(v)`` applied to the
    already-joined string). Zero spans (abstention) joins to ``""``, which
    then feeds ``compute_f1``/``compute_exact``'s empty-side convention."""

    joined = " ".join(prediction_spans)
    return upstream_meetingqa_remove_speaker_prefixes(joined)


def _upstream_gold_answers(reference_spans: tuple[str, ...]) -> tuple[str, ...]:
    """Per-span speaker-prefix strip (``custom_evaluate.py:30-32``, applied
    to each span BEFORE the metric sees it), then HF squad_v2's
    ``get_raw_scores`` gold-answer filter: keep only spans whose
    ``normalize_answer`` is truthy, falling back to ``("",)`` -- the
    no-answer convention -- when nothing survives (design choice 3
    above). The surviving strings are the pre-normalization,
    speaker-stripped text, matching upstream's ``[t for t in
    qa["answers"]["text"] if normalize_answer(t)]`` (filtered BY the
    normalized form, but the ORIGINAL ``t`` is kept as the alternative)."""

    stripped = tuple(upstream_meetingqa_remove_speaker_prefixes(span) for span in reference_spans)
    survivors = tuple(span for span in stripped if upstream_meetingqa_normalize_answer(span))
    return survivors if survivors else ("",)


@dataclass(frozen=True)
class UpstreamMeetingQAExampleScore:
    """One example's upstream-equivalent score. ``scored_prediction_text``
    and ``scored_gold_answers`` are exposed (not just the final numbers) so
    a divergence report can show exactly what string upstream's scorer
    compared, which is often the clearest way to see WHY a score differs
    from :mod:`.qa`'s (e.g. a gold span that degenerated to the empty
    string after article removal, or a multi-span prediction that got
    joined)."""

    example_id: str
    upstream_meetingqa_f1: float
    upstream_meetingqa_exact_match: float
    scored_prediction_text: str
    scored_gold_answers: tuple[str, ...]


def upstream_meetingqa_score_example(example: QAExample) -> UpstreamMeetingQAExampleScore:
    prediction_text = _upstream_prediction_text(example.prediction_spans)
    gold_answers = _upstream_gold_answers(example.reference_spans)
    return UpstreamMeetingQAExampleScore(
        example_id=example.example_id,
        # HF get_raw_scores: "Take max over all gold answers" for both EM and F1.
        upstream_meetingqa_f1=max(upstream_meetingqa_f1(gold, prediction_text) for gold in gold_answers),
        upstream_meetingqa_exact_match=max(
            upstream_meetingqa_exact_match(gold, prediction_text) for gold in gold_answers
        ),
        scored_prediction_text=prediction_text,
        scored_gold_answers=gold_answers,
    )


@dataclass(frozen=True)
class UpstreamMeetingQAScoreReport:
    """Pooled report -- plain mean over ALL examples, matching HF squad_v2's
    ``make_eval_dict``'s ``100 * sum(...) / total`` (percentage scaling
    dropped per design choice 5 above; every example counted equally, no
    HasAns/NoAns subset weighting per design choice 7)."""

    n_examples: int
    upstream_meetingqa_macro_f1: float
    upstream_meetingqa_macro_exact_match: float
    per_example: tuple[UpstreamMeetingQAExampleScore, ...] = field(default_factory=tuple)


def upstream_meetingqa_score_examples(examples: Sequence[QAExample]) -> UpstreamMeetingQAScoreReport:
    if not examples:
        raise ValueError("upstream_meetingqa_score_examples: examples must be non-empty")

    scores = tuple(upstream_meetingqa_score_example(ex) for ex in examples)
    return UpstreamMeetingQAScoreReport(
        n_examples=len(scores),
        upstream_meetingqa_macro_f1=sum(s.upstream_meetingqa_f1 for s in scores) / len(scores),
        upstream_meetingqa_macro_exact_match=sum(s.upstream_meetingqa_exact_match for s in scores) / len(scores),
        per_example=scores,
    )


__all__ = [
    "upstream_meetingqa_remove_speaker_prefixes",
    "upstream_meetingqa_normalize_answer",
    "upstream_meetingqa_tokens",
    "upstream_meetingqa_exact_match",
    "upstream_meetingqa_f1",
    "UpstreamMeetingQAExampleScore",
    "upstream_meetingqa_score_example",
    "UpstreamMeetingQAScoreReport",
    "upstream_meetingqa_score_examples",
]
