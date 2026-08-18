from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.glossary_diagnostics import (
    AlignedPair,
    align_tokens,
    glossary_induced_substitution_diagnostic,
    unsupported_activation_rate,
)

# ---------------------------------------------------------------------------
# AlignedPair.op
# ---------------------------------------------------------------------------


def test_aligned_pair_op_correct():
    assert AlignedPair("a", "a").op == "correct"


def test_aligned_pair_op_substitution():
    assert AlignedPair("a", "b").op == "substitution"


def test_aligned_pair_op_deletion():
    assert AlignedPair("a", None).op == "deletion"


def test_aligned_pair_op_insertion():
    assert AlignedPair(None, "a").op == "insertion"


def test_aligned_pair_op_both_none_is_invalid():
    with pytest.raises(ValueError):
        AlignedPair(None, None).op


# ---------------------------------------------------------------------------
# align_tokens -- one hand-traceable difflib case
# ---------------------------------------------------------------------------


def test_align_tokens_hand_traceable_case():
    # a = [the, quick, brown, fox]; b = [the, fast, brown, fox, jumps].
    # "the" matches at position 0; "quick"/"fast" is a single-token
    # replace; "brown fox" matches as a contiguous block; "jumps" is a
    # trailing insertion. difflib.SequenceMatcher.get_opcodes() on this
    # unambiguous case yields exactly: equal(the), replace(quick->fast),
    # equal(brown), equal(fox), insert(jumps).
    reference = ["the", "quick", "brown", "fox"]
    hypothesis = ["the", "fast", "brown", "fox", "jumps"]
    pairs = align_tokens(reference, hypothesis)
    assert pairs == (
        AlignedPair("the", "the"),
        AlignedPair("quick", "fast"),
        AlignedPair("brown", "brown"),
        AlignedPair("fox", "fox"),
        AlignedPair(None, "jumps"),
    )


def test_align_tokens_identical_sequences_are_all_correct():
    tokens = ["a", "b", "c"]
    pairs = align_tokens(tokens, tokens)
    assert all(p.op == "correct" for p in pairs)
    assert len(pairs) == 3


# ---------------------------------------------------------------------------
# glossary_induced_substitution_diagnostic -- hand-computed on a built
# alignment (not routed through align_tokens, so the diagnostic's own
# arithmetic is verified independently of the difflib helper).
# ---------------------------------------------------------------------------

_GLOSSARY = ["acme", "zeta"]

# 1. correct, neither glossary       -> hello / hello
# 2. correct, ref IS glossary        -> acme / acme
# 3. substitution, INDUCED           -> foo (not glossary) / acme (glossary)
# 4. substitution, INDUCED           -> bar (not glossary) / zeta (glossary)
# 5. substitution, not induced       -> baz / qux (neither glossary)
# 6. insertion, hyp IS glossary      -> None / acme
# 7. deletion, ref IS glossary       -> zeta / None
_ALIGNED_PAIRS = (
    AlignedPair("hello", "hello"),
    AlignedPair("acme", "acme"),
    AlignedPair("foo", "acme"),
    AlignedPair("bar", "zeta"),
    AlignedPair("baz", "qux"),
    AlignedPair(None, "acme"),
    AlignedPair("zeta", None),
)


def test_glossary_induced_substitution_diagnostic_hand_computed():
    result = glossary_induced_substitution_diagnostic(_ALIGNED_PAIRS, _GLOSSARY)

    # total substitutions: pairs 3, 4, 5 -> 3.
    assert result.total_substitutions == 3
    # induced: pairs 3 and 4 (hyp is glossary, ref is not) -> 2.
    assert result.glossary_induced_substitutions == 2
    assert set(result.induced_pairs) == {AlignedPair("foo", "acme"), AlignedPair("bar", "zeta")}

    # hypothesis glossary occurrences: pairs 2, 3, 4, 6 -> 4.
    assert result.hypothesis_glossary_term_occurrences == 4
    # false-alarm rate = induced / hyp glossary occurrences = 2/4 = 0.5.
    assert result.false_alarm_rate == pytest.approx(0.5)

    # biased ref tokens (ref IS glossary, present): pairs 2 (correct), 7 (deletion, error) -> total 2, errors 1.
    assert result.biased_ref_token_count == 2
    assert result.biased_wer == pytest.approx(0.5)

    # unbiased ref tokens (ref present, not glossary): pairs 1 (correct), 3, 4, 5 (all substitutions/errors) -> total 4, errors 3.
    assert result.unbiased_ref_token_count == 4
    assert result.unbiased_wer == pytest.approx(0.75)


def test_glossary_induced_substitution_diagnostic_no_glossary_terms_present():
    pairs = (AlignedPair("a", "a"), AlignedPair("b", "c"))
    result = glossary_induced_substitution_diagnostic(pairs, glossary_terms=["nonexistent"])
    assert result.glossary_induced_substitutions == 0
    assert result.hypothesis_glossary_term_occurrences == 0
    assert result.false_alarm_rate == 0.0  # never a ZeroDivisionError
    assert result.biased_wer is None  # no biased ref tokens seen -> None, not 0.0
    assert result.unbiased_wer == pytest.approx(0.5)


def test_glossary_induced_substitution_diagnostic_normalizes_case():
    pairs = (AlignedPair("foo", "ACME"),)
    result = glossary_induced_substitution_diagnostic(pairs, glossary_terms=["Acme"])
    assert result.glossary_induced_substitutions == 1


# ---------------------------------------------------------------------------
# unsupported_activation_rate -- EGTA's instrument, hand-computed.
# ---------------------------------------------------------------------------


def test_unsupported_activation_rate_hand_computed():
    injected_terms = ["acme", "zeta", "omega"]
    hypothesis_text = "The Acme deal with Zeta Corp closed."
    reference_text = "The deal with Zeta Corp closed successfully."

    result = unsupported_activation_rate(hypothesis_text, reference_text, injected_terms)

    # activated: acme (in hyp), zeta (in hyp); omega never appears in hyp.
    assert set(result.activated_terms) == {"acme", "zeta"}
    # unsupported: acme has no support in reference; zeta does (reference
    # mentions "Zeta").
    assert result.unsupported_terms == ("acme",)

    assert result.unsupported_activation_rate == pytest.approx(1 / 3)
    assert result.unsupported_given_activated_rate == pytest.approx(0.5)


def test_unsupported_activation_rate_no_activation_gives_none_conditional_rate():
    result = unsupported_activation_rate("nothing relevant here", "also nothing", ["acme"])
    assert result.activated_terms == ()
    assert result.unsupported_activation_rate == pytest.approx(0.0)
    assert result.unsupported_given_activated_rate is None


def test_unsupported_activation_rate_rejects_empty_injected_terms():
    with pytest.raises(ValueError):
        unsupported_activation_rate("hyp", "ref", [])
