"""Copy-rate instrument: detects verbatim, normalized-token, in-order
parroting of a reference text inside a produced text.

Lineage (the one recorded cross-repo import for this repository; see
CLAUDE.md "Research object" and the 2026-08-17 owner decision): this
reimplements, small and standalone, the verbatim-subsequence copy-detection
pattern used by the speech-aware-evidence-acquisition study --
``analysis.p2_reads.copy_count_for_arm`` / its ``_count_subsequence`` helper
(studies/speech-aware-evidence-acquisition/src/speech_aware_evidence_acquisition/analysis/p2_reads.py,
as of umbrella commit range including 12590d4). No code is imported from that
study -- only the algorithm shape is reused: normalize both sides to a token
list, then count how many times the needle's tokens occur as a contiguous,
in-order subsequence of the haystack's tokens. This module deliberately
drops everything else that study's version carries (arm bookkeeping, guard
tiers, replay-window plumbing); it is a plain byte/token-identical parroting
counter for this repository's own use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def normalize_tokens(text: str) -> list[str]:
    """Lowercase word tokens, punctuation and surrounding whitespace
    stripped. Two texts that differ only in case, punctuation, or spacing
    normalize to the same token list."""

    return [t.lower() for t in _TOKEN_RE.findall(text)]


def count_verbatim_occurrences(haystack_tokens: Sequence[str], needle_tokens: Sequence[str]) -> int:
    """How many times ``needle_tokens`` occurs as a contiguous, in-order
    subsequence of ``haystack_tokens``. 0 if the needle is empty or longer
    than the haystack."""

    n, m = len(haystack_tokens), len(needle_tokens)
    if m == 0 or m > n:
        return 0
    return sum(1 for i in range(n - m + 1) if list(haystack_tokens[i : i + m]) == list(needle_tokens))


@dataclass(frozen=True)
class CopyRateResult:
    total_items: int
    items_with_copy: int
    total_occurrences: int

    @property
    def copy_rate(self) -> float:
        """items_with_copy / total_items -- 0.0 when there were no items to
        check (never a bare ZeroDivisionError)."""

        return self.items_with_copy / self.total_items if self.total_items else 0.0


def compute_copy_rate(produced_texts: Sequence[str], reference_texts: Sequence[str]) -> CopyRateResult:
    """Pairwise copy-rate over parallel ``produced_texts`` /
    ``reference_texts`` sequences: for each pair, count verbatim
    normalized-token occurrences of the reference inside the produced text.
    An empty reference (nothing to check for) never counts as a copy."""

    if len(produced_texts) != len(reference_texts):
        raise ValueError(
            f"produced_texts and reference_texts must be the same length, "
            f"got {len(produced_texts)} and {len(reference_texts)}"
        )

    items_with_copy = 0
    total_occurrences = 0
    for produced, reference in zip(produced_texts, reference_texts):
        needle = normalize_tokens(reference)
        if not needle:
            continue
        occurrences = count_verbatim_occurrences(normalize_tokens(produced), needle)
        if occurrences > 0:
            items_with_copy += 1
            total_occurrences += occurrences

    return CopyRateResult(
        total_items=len(produced_texts),
        items_with_copy=items_with_copy,
        total_occurrences=total_occurrences,
    )
