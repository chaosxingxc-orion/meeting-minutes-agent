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
    wrong_speaker = index.deranged_speaker[speaker_id]
    wrong_pool = index.speaker_pools.get(wrong_speaker, ())
    ranked = sorted(
        ((similarity(term, tuple(content_tokens(query_text))), term) for term in wrong_pool),
        key=lambda item: (-item[0], item[1]),
    )
    return tuple(term for _, term in ranked[: len(speaker_terms)])


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
    "RetrievalIndex",
    "RetrievalLimits",
    "build_index",
    "render_candidates",
    "retrieve",
    "retrieve_for_arm",
    "similarity",
]
