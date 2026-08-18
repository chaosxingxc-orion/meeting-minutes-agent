"""Glossary-induced-substitution diagnostic and the unsupported-activation-
rate audit (EGTA's instrument, adopted as a Tier-0 diagnostic per the
deep-check registered changes).

Both diagnostics look for the same failure mode from two different angles:
a glossary that gets INJECTED into the prompt can leak into the hypothesis
where it does not belong (the model "sees" a glossary term and reaches for
it even where the audio/reference does not support it).

- :func:`glossary_induced_substitution_diagnostic` works at the ALIGNED
  TOKEN level: given a hypothesis/reference token alignment, it flags every
  substitution where the hypothesis side is a glossary term and the
  reference side is not, and reports a B-WER/U-WER-style biased-vs-unbiased
  WER split plus a false-alarm rate.
- :func:`unsupported_activation_rate` works at the WHOLE-TEXT, PER-TERM
  level (EGTA's instrument): of the terms that were injected into the
  prompt, what fraction show up in the hypothesis with no support anywhere
  in the reference.

:func:`align_tokens` is a small, dependency-free (``difflib``-based) word
alignment used ONLY to feed the substitution diagnostic in tests and
ad-hoc analysis. It is NOT a WER computation and must never be used as one
-- all WER-family numbers come from :mod:`.wer`'s meeteval wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

__all__ = [
    "AlignedPair",
    "align_tokens",
    "GlossarySubstitutionResult",
    "glossary_induced_substitution_diagnostic",
    "UnsupportedActivationResult",
    "unsupported_activation_rate",
]

_default_normalize: Callable[[str], str] = str.lower


@dataclass(frozen=True)
class AlignedPair:
    """One aligned (reference token, hypothesis token) slot. Exactly one
    side is ``None`` for an insertion/deletion; both present (equal or
    not) for a correct/substituted slot."""

    ref_token: str | None
    hyp_token: str | None

    @property
    def op(self) -> str:
        if self.ref_token is None and self.hyp_token is None:
            raise ValueError("AlignedPair: both sides None is not a valid alignment slot")
        if self.ref_token is None:
            return "insertion"
        if self.hyp_token is None:
            return "deletion"
        return "correct" if self.ref_token == self.hyp_token else "substitution"


def align_tokens(reference_tokens: Sequence[str], hypothesis_tokens: Sequence[str]) -> tuple[AlignedPair, ...]:
    """Deterministic word-level alignment via ``difflib.SequenceMatcher``
    (Ratcliff/Obershelp), expanded into ref/hyp opcode pairs. This is a
    lightweight helper for feeding the glossary-substitution diagnostic
    from raw token lists -- it does not claim to reproduce meeteval's
    edit-distance alignment exactly and must never be used to derive a
    headline WER number."""

    import difflib

    ref = list(reference_tokens)
    hyp = list(hypothesis_tokens)
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    pairs: list[AlignedPair] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                pairs.append(AlignedPair(ref[i], hyp[j]))
        elif tag == "replace":
            ref_slice = ref[i1:i2]
            hyp_slice = hyp[j1:j2]
            for k in range(max(len(ref_slice), len(hyp_slice))):
                r = ref_slice[k] if k < len(ref_slice) else None
                h = hyp_slice[k] if k < len(hyp_slice) else None
                pairs.append(AlignedPair(r, h))
        elif tag == "delete":
            for i in range(i1, i2):
                pairs.append(AlignedPair(ref[i], None))
        elif tag == "insert":
            for j in range(j1, j2):
                pairs.append(AlignedPair(None, hyp[j]))
        else:  # pragma: no cover -- difflib only emits the four tags above
            raise ValueError(f"align_tokens: unexpected opcode tag {tag!r}")
    return tuple(pairs)


@dataclass(frozen=True)
class GlossarySubstitutionResult:
    glossary_induced_substitutions: int
    total_substitutions: int
    hypothesis_glossary_term_occurrences: int
    false_alarm_rate: float  # glossary_induced_substitutions / hypothesis_glossary_term_occurrences
    biased_wer: float | None  # B-WER: error rate over reference tokens that ARE glossary terms
    unbiased_wer: float | None  # U-WER: error rate over reference tokens that are NOT glossary terms
    biased_ref_token_count: int
    unbiased_ref_token_count: int
    induced_pairs: tuple[AlignedPair, ...]


def glossary_induced_substitution_diagnostic(
    aligned_pairs: Sequence[AlignedPair],
    glossary_terms: Sequence[str],
    *,
    normalize: Callable[[str], str] = _default_normalize,
) -> GlossarySubstitutionResult:
    """Given an aligned (hypothesis tokens, reference tokens) pair sequence
    and a glossary term list: count hypothesis tokens matching a glossary
    term where the ALIGNED reference token is a non-glossary word (a
    "glossary-induced substitution" -- the glossary leaked in where the
    reference did not support it), and report a B-WER/U-WER-style
    biased-vs-unbiased split plus a false-alarm rate.

    Kill criterion (deep-check registered, applied by the caller, not
    enforced here): induced substitutions >= entity true-positive gains
    implies the glossary arm is net-harmful.
    """

    glossary_set = {normalize(t) for t in glossary_terms}

    induced: list[AlignedPair] = []
    total_substitutions = 0
    hyp_glossary_occurrences = 0
    biased_ref_total = 0
    biased_ref_errors = 0
    unbiased_ref_total = 0
    unbiased_ref_errors = 0

    for pair in aligned_pairs:
        if pair.hyp_token is not None and normalize(pair.hyp_token) in glossary_set:
            hyp_glossary_occurrences += 1

        if pair.ref_token is not None:
            ref_is_glossary = normalize(pair.ref_token) in glossary_set
            is_error = pair.op != "correct"
            if ref_is_glossary:
                biased_ref_total += 1
                if is_error:
                    biased_ref_errors += 1
            else:
                unbiased_ref_total += 1
                if is_error:
                    unbiased_ref_errors += 1

        if pair.op == "substitution":
            total_substitutions += 1
            ref_is_glossary = normalize(pair.ref_token) in glossary_set  # type: ignore[arg-type]
            hyp_is_glossary = normalize(pair.hyp_token) in glossary_set  # type: ignore[arg-type]
            if hyp_is_glossary and not ref_is_glossary:
                induced.append(pair)

    false_alarm_rate = len(induced) / hyp_glossary_occurrences if hyp_glossary_occurrences else 0.0
    biased_wer = biased_ref_errors / biased_ref_total if biased_ref_total else None
    unbiased_wer = unbiased_ref_errors / unbiased_ref_total if unbiased_ref_total else None

    return GlossarySubstitutionResult(
        glossary_induced_substitutions=len(induced),
        total_substitutions=total_substitutions,
        hypothesis_glossary_term_occurrences=hyp_glossary_occurrences,
        false_alarm_rate=false_alarm_rate,
        biased_wer=biased_wer,
        unbiased_wer=unbiased_wer,
        biased_ref_token_count=biased_ref_total,
        unbiased_ref_token_count=unbiased_ref_total,
        induced_pairs=tuple(induced),
    )


_WORD_RE_CACHE = None


def _simple_tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[^\W_]+", text, re.UNICODE)


@dataclass(frozen=True)
class UnsupportedActivationResult:
    """EGTA's unsupported-activation-rate audit, per distinct injected
    term (not per occurrence -- contrast with
    :class:`GlossarySubstitutionResult`, which is occurrence/token-level).

    Two denominators are exposed because "fraction of injected terms that
    appear in the hypothesis with no support in the reference" is
    ambiguous about whether the denominator is ALL injected terms or only
    the ones that activated at all:

    - ``unsupported_activation_rate`` = unsupported / ALL injected terms
      (this repository's primary reading -- see the E5 report's pinning
      note).
    - ``unsupported_given_activated_rate`` = unsupported / activated terms
      only (the alternative reading), ``None`` if nothing activated.
    """

    injected_terms: tuple[str, ...]
    activated_terms: tuple[str, ...]
    unsupported_terms: tuple[str, ...]
    unsupported_activation_rate: float
    unsupported_given_activated_rate: float | None


def unsupported_activation_rate(
    hypothesis_text: str,
    reference_text: str,
    injected_terms: Sequence[str],
    *,
    normalize: Callable[[str], str] = _default_normalize,
) -> UnsupportedActivationResult:
    """Of ``injected_terms`` (the glossary terms actually injected into the
    prompt for this arm/turn): which appear in ``hypothesis_text`` at all
    ("activated"), and of those, which have NO occurrence anywhere in
    ``reference_text`` ("unsupported")."""

    if not injected_terms:
        raise ValueError("unsupported_activation_rate: injected_terms must be non-empty")

    hyp_tokens = {normalize(t) for t in _simple_tokenize(hypothesis_text)}
    ref_tokens = {normalize(t) for t in _simple_tokenize(reference_text)}

    activated = tuple(t for t in injected_terms if normalize(t) in hyp_tokens)
    unsupported = tuple(t for t in activated if normalize(t) not in ref_tokens)

    return UnsupportedActivationResult(
        injected_terms=tuple(injected_terms),
        activated_terms=activated,
        unsupported_terms=unsupported,
        unsupported_activation_rate=len(unsupported) / len(injected_terms),
        unsupported_given_activated_rate=(len(unsupported) / len(activated)) if activated else None,
    )
