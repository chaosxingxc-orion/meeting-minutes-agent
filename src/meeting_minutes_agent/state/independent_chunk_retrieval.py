"""Leave-one-chunk-out retrieval from independent same-speaker outputs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import difflib
from typing import Mapping, Sequence

from .sliding_memory import content_tokens


@dataclass(frozen=True)
class IndependentRetrievalLimits:
    maximum_candidates: int = 4
    minimum_supporting_chunks: int = 2
    minimum_similarity: float = 0.75
    speaker_pool_size: int = 256
    maximum_context_characters: int = 256

    def validate(self) -> "IndependentRetrievalLimits":
        for name in ("maximum_candidates", "minimum_supporting_chunks", "speaker_pool_size", "maximum_context_characters"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not 0 <= self.minimum_similarity <= 1:
            raise ValueError("minimum_similarity must be in [0, 1]")
        return self


@dataclass(frozen=True)
class IndependentCandidate:
    term: str
    matched_query_term: str
    similarity: float
    supporting_turns: tuple[int, ...]


@dataclass(frozen=True)
class IndependentIndex:
    speaker_support: Mapping[str, Mapping[str, tuple[int, ...]]]


def build_independent_index(rows: Sequence[Mapping[str, object]]) -> IndependentIndex:
    support: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    seen_turns: set[int] = set()
    for row in rows:
        turn_index = int(row["turn_index"])
        if turn_index in seen_turns:
            raise ValueError("duplicate turn_index")
        seen_turns.add(turn_index)
        speaker = str(row["speaker_id"])
        for term in set(content_tokens(str(row.get("text", "")))):
            support[speaker][term].add(turn_index)
    return IndependentIndex({
        speaker: {term: tuple(sorted(turns)) for term, turns in sorted(terms.items())}
        for speaker, terms in sorted(support.items())
    })


def _best_match(candidate: str, query_terms: Sequence[str]) -> tuple[float, str]:
    matches = sorted(
        ((difflib.SequenceMatcher(a=candidate, b=query, autojunk=False).ratio(), query) for query in query_terms),
        key=lambda item: (-item[0], item[1]),
    )
    return matches[0] if matches else (0.0, "")


def retrieve_independent(
    speaker_id: str,
    turn_index: int,
    query_text: str,
    index: IndependentIndex,
    limits: IndependentRetrievalLimits,
) -> tuple[IndependentCandidate, ...]:
    """Retrieve novel forms supported by other chunks from the same speaker."""
    limits.validate()
    query_terms = tuple(dict.fromkeys(content_tokens(query_text)))
    query_set = set(query_terms)
    ranked = []
    for term, all_supporting_turns in index.speaker_support.get(speaker_id, {}).items():
        if term in query_set:
            continue
        supporting_turns = tuple(value for value in all_supporting_turns if value != turn_index)
        if len(supporting_turns) < limits.minimum_supporting_chunks:
            continue
        score, matched = _best_match(term, query_terms)
        if score < limits.minimum_similarity:
            continue
        ranked.append((score, len(supporting_turns), term, matched, supporting_turns))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    return tuple(
        IndependentCandidate(term, matched, score, supporting_turns)
        for score, _, term, matched, supporting_turns in ranked[: limits.maximum_candidates]
    )


__all__ = [
    "IndependentCandidate",
    "IndependentIndex",
    "IndependentRetrievalLimits",
    "build_independent_index",
    "retrieve_independent",
]
