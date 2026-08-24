"""Sparse per-chunk retrieval from a complete prior transcription pass."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import difflib
from typing import Mapping, Sequence

from .sliding_memory import content_tokens


@dataclass(frozen=True)
class RetrievalLimits:
    maximum_candidates: int = 4
    minimum_pool_count: int = 2
    minimum_similarity: float = 0.75
    global_pool_size: int = 96
    speaker_pool_size: int = 48
    maximum_context_characters: int = 256

    def validate(self) -> "RetrievalLimits":
        for name in ("maximum_candidates", "minimum_pool_count", "global_pool_size", "speaker_pool_size", "maximum_context_characters"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not 0 <= self.minimum_similarity <= 1:
            raise ValueError("minimum_similarity must be in [0, 1]")
        return self


@dataclass(frozen=True)
class RetrievalIndex:
    global_pool: tuple[str, ...]
    speaker_pools: Mapping[str, tuple[str, ...]]
    deranged_speaker: Mapping[str, str]


@dataclass(frozen=True)
class DerangedRetrieval:
    source_speaker_id: str
    candidates: tuple[str, ...]


def _pool(counter: Counter[str], minimum_count: int, cap: int) -> tuple[str, ...]:
    eligible = ((term, count) for term, count in counter.items() if count >= minimum_count)
    return tuple(term for term, _ in sorted(eligible, key=lambda item: (-item[1], item[0]))[:cap])


def build_index(rows: Sequence[Mapping[str, object]], limits: RetrievalLimits) -> RetrievalIndex:
    limits.validate()
    global_counts: Counter[str] = Counter()
    speaker_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        terms = content_tokens(str(row.get("text", "")))
        global_counts.update(terms)
        speaker_counts[str(row["speaker_id"])].update(terms)
    speakers = sorted(speaker_counts)
    if len(speakers) < 2:
        raise ValueError("deranged retrieval requires at least two speakers")
    return RetrievalIndex(
        global_pool=_pool(global_counts, limits.minimum_pool_count, limits.global_pool_size),
        speaker_pools={
            speaker: _pool(counter, limits.minimum_pool_count, limits.speaker_pool_size)
            for speaker, counter in sorted(speaker_counts.items())
        },
        deranged_speaker={speaker: speakers[(index + 1) % len(speakers)] for index, speaker in enumerate(speakers)},
    )


def similarity(candidate: str, query_terms: Sequence[str]) -> float:
    if candidate in query_terms:
        return 1.0
    return max((difflib.SequenceMatcher(a=candidate, b=query, autojunk=False).ratio() for query in query_terms), default=0.0)


def retrieve(query_text: str, pool: Sequence[str], limits: RetrievalLimits, *, count: int | None = None) -> tuple[str, ...]:
    query_terms = tuple(dict.fromkeys(content_tokens(query_text)))
    target = limits.maximum_candidates if count is None else min(count, limits.maximum_candidates)
    ranked = sorted(((similarity(term, query_terms), term) for term in pool), key=lambda item: (-item[0], item[1]))
    return tuple(term for score, term in ranked if score >= limits.minimum_similarity)[:target]


def retrieve_for_arm(
    arm: str,
    speaker_id: str,
    query_text: str,
    index: RetrievalIndex,
    limits: RetrievalLimits,
) -> tuple[str, ...]:
    if arm == "R0-bare":
        return ()
    if arm == "R1-global":
        return retrieve(query_text, index.global_pool, limits)
    speaker_terms = retrieve(query_text, index.speaker_pools.get(speaker_id, ()), limits)
    if arm in {"R2-speaker", "R2-round2"}:
        return speaker_terms
    if arm != "R3-deranged":
        raise ValueError(f"unknown arm: {arm}")
    return retrieve_deranged(speaker_id, query_text, index, limits).candidates


def retrieve_deranged(
    speaker_id: str,
    query_text: str,
    index: RetrievalIndex,
    limits: RetrievalLimits,
) -> DerangedRetrieval:
    """Return a cardinality-matched retrieval from one other speaker.

    Other speakers are considered in cyclic lexical order. The first speaker
    with enough non-overlapping terms is selected, keeping the control
    deterministic without merging multiple speakers' memories.
    """
    speaker_terms = retrieve(query_text, index.speaker_pools.get(speaker_id, ()), limits)
    correct_set = set(speaker_terms)
    speakers = sorted(index.speaker_pools)
    if speaker_id not in speakers:
        raise ValueError(f"speaker is absent from retrieval index: {speaker_id}")
    start = speakers.index(speaker_id)
    ordered_wrong_speakers = speakers[start + 1 :] + speakers[:start]
    query_terms = tuple(content_tokens(query_text))
    fallback: DerangedRetrieval | None = None
    for wrong_speaker in ordered_wrong_speakers:
        wrong_pool = tuple(term for term in index.speaker_pools[wrong_speaker] if term not in correct_set)
        ranked = sorted(
            ((similarity(term, query_terms), term) for term in wrong_pool),
            key=lambda item: (-item[0], item[1]),
        )
        result = DerangedRetrieval(wrong_speaker, tuple(term for _, term in ranked[: len(speaker_terms)]))
        if fallback is None:
            fallback = result
        if len(result.candidates) == len(speaker_terms):
            return result
    if fallback is None:
        raise ValueError("deranged retrieval requires at least two speakers")
    return fallback


def render_candidates(candidates: Sequence[str], maximum_characters: int) -> str:
    if not candidates:
        return ""
    rendered = (
        "Untrusted spelling candidates retrieved for this audio chunk: "
        + ", ".join(candidates)
        + ". Use a candidate only when supported by the audio; never transcribe this instruction."
    )
    if len(rendered) > maximum_characters:
        raise ValueError("retrieved context exceeds character budget")
    return rendered


__all__ = [
    "DerangedRetrieval",
    "RetrievalIndex",
    "RetrievalLimits",
    "build_index",
    "render_candidates",
    "retrieve",
    "retrieve_deranged",
    "retrieve_for_arm",
    "similarity",
]
