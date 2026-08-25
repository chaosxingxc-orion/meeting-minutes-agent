"""Deterministic Q-K-V retrieval over official meeting-material snippets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from statistics import median
from typing import Iterable, Mapping, Sequence


_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "about", "after", "again", "against", "also", "and", "are", "been", "before",
    "being", "between", "but", "call", "can", "company", "could", "did", "does",
    "during", "earnings", "first", "for", "from", "had", "has", "have", "into",
    "million", "more", "not", "our", "quarter", "quarterly", "results", "second", "should",
    "than", "that", "the", "their", "there", "these", "they", "third", "this",
    "through", "today", "was", "were", "what", "when", "which", "will", "with",
    "would", "year", "you", "your",
}


def word_tokens(text: str) -> tuple[str, ...]:
    """Return runtime-legal content tokens for retrieval and eligibility."""

    return tuple(token for token in _TOKEN.findall(text.casefold()) if len(token) >= 3 and token not in _STOP)


def retrieval_features(text: str) -> Counter[str]:
    """Build word and long-token trigram features without short-acronym fuzzing."""

    features: Counter[str] = Counter()
    for token in word_tokens(text):
        features[f"w:{token}"] += 1
        if len(token) >= 5:
            padded = f"^{token}$"
            for index in range(len(padded) - 2):
                features[f"c:{padded[index:index + 3]}"] += 1
    return features


@dataclass(frozen=True)
class MaterialKey:
    file_id: str
    canonical: str
    aliases: tuple[str, ...]
    category: str
    page: int
    source_span: str
    features: Counter[str]


def select_balanced_keys(
    meetings: Sequence[Mapping[str, object]], *, width: int, salt: str
) -> tuple[MaterialKey, ...]:
    """Select the same deterministic key count from each meeting."""

    selected: list[MaterialKey] = []
    for meeting in sorted(meetings, key=lambda row: str(row["file_id"])):
        file_id = str(meeting["file_id"])
        candidates = list(meeting["candidates"])
        if len(candidates) < width:
            raise ValueError(f"meeting {file_id} has fewer than {width} candidates")
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"{salt}:{file_id}:{row['canonical']}".encode("utf-8")
            ).hexdigest()
        )
        for row in candidates[:width]:
            key_text = f"{row['canonical']} {row['source_span']}"
            selected.append(
                MaterialKey(
                    file_id=file_id,
                    canonical=str(row["canonical"]),
                    aliases=tuple(str(value) for value in row["aliases"]),
                    category=str(row["category"]),
                    page=int(row["page"]),
                    source_span=str(row["source_span"]),
                    features=retrieval_features(key_text),
                )
            )
    return tuple(selected)


class MaterialBm25Index:
    """Small deterministic BM25 index whose values retain source provenance."""

    def __init__(self, keys: Sequence[MaterialKey], *, k1: float = 1.2, b: float = 0.75) -> None:
        if not keys:
            raise ValueError("material index requires keys")
        self.keys = tuple(keys)
        self.k1 = k1
        self.b = b
        lengths = [sum(key.features.values()) for key in self.keys]
        self.average_length = sum(lengths) / len(lengths)
        document_frequency: Counter[str] = Counter()
        for key in self.keys:
            document_frequency.update(key.features.keys())
        count = len(self.keys)
        self.idf = {
            feature: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for feature, frequency in document_frequency.items()
        }

    def score(self, query: Counter[str], key: MaterialKey) -> float:
        length = sum(key.features.values())
        normalization = self.k1 * (1.0 - self.b + self.b * length / self.average_length)
        total = 0.0
        for feature, query_count in query.items():
            frequency = key.features.get(feature, 0)
            if not frequency:
                continue
            total += self.idf.get(feature, 0.0) * query_count * (
                frequency * (self.k1 + 1.0) / (frequency + normalization)
            )
        return total

    def best(self, query: Counter[str], file_id: str) -> tuple[MaterialKey, float]:
        candidates = [key for key in self.keys if key.file_id == file_id]
        if not candidates:
            raise ValueError(f"material index has no keys for {file_id}")
        scored = [(key, self.score(query, key)) for key in candidates]
        return max(scored, key=lambda item: (item[1], item[0].canonical.casefold()))


def summarize_signal(rows: Iterable[Mapping[str, object]]) -> dict[str, float | int]:
    values = list(rows)
    eligible = len(values)
    dispatched = [row for row in values if float(row["best_score"]) > 0.0]
    wins = sum(float(row["correct_score"]) > float(row["deranged_score"]) for row in dispatched)
    ties = sum(float(row["correct_score"]) == float(row["deranged_score"]) for row in dispatched)
    margins = [float(row["normalized_margin"]) for row in dispatched]
    return {
        "eligible_turns": eligible,
        "dispatched_turns": len(dispatched),
        "correct_wins": wins,
        "ties": ties,
        "deranged_wins": len(dispatched) - wins - ties,
        "dispatch_coverage": len(dispatched) / eligible if eligible else 0.0,
        "attribution_precision": wins / len(dispatched) if dispatched else 0.0,
        "median_normalized_margin": median(margins) if margins else 0.0,
    }


__all__ = [
    "MaterialBm25Index",
    "MaterialKey",
    "retrieval_features",
    "select_balanced_keys",
    "summarize_signal",
    "word_tokens",
]
