"""Deterministic trigger for externally registered company identities.

This module does not decide whether an external registry is runtime-admissible.
It only implements the frozen zero-model feasibility policy: exact identity
mentions need no correction; otherwise a sufficiently similar Pass0 n-gram
may request the registered canonical surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata


_TOKEN = re.compile(r"[a-z0-9]+")


def identity_tokens(text: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFKD", text).casefold()
    value = "".join(character for character in value if not unicodedata.combining(character))
    return tuple(_TOKEN.findall(value))


def contains_identity(text: str, aliases: tuple[str, ...]) -> bool:
    tokens = identity_tokens(text)
    for alias in aliases:
        target = identity_tokens(alias)
        width = len(target)
        if width and any(tokens[index : index + width] == target for index in range(len(tokens) - width + 1)):
            return True
    return False


@dataclass(frozen=True)
class IdentityTrigger:
    canonical: str
    matched_alias: str
    observed_surface: str
    similarity: float


def trigger_identity(
    text: str,
    canonical: str,
    aliases: tuple[str, ...],
    similarity_threshold: float = 0.75,
) -> IdentityTrigger | None:
    """Return the best fuzzy identity trigger, excluding exact mentions."""

    if contains_identity(text, aliases):
        return None
    tokens = identity_tokens(text)
    best: IdentityTrigger | None = None
    for alias in aliases:
        target = identity_tokens(alias)
        width = len(target)
        if not width:
            continue
        target_text = " ".join(target)
        for index in range(len(tokens) - width + 1):
            observed = tokens[index : index + width]
            score = SequenceMatcher(None, " ".join(observed), target_text).ratio()
            if score < similarity_threshold:
                continue
            candidate = IdentityTrigger(canonical, alias, " ".join(observed), score)
            if best is None or (candidate.similarity, candidate.matched_alias, candidate.observed_surface) > (
                best.similarity,
                best.matched_alias,
                best.observed_surface,
            ):
                best = candidate
    return best


__all__ = ["IdentityTrigger", "contains_identity", "identity_tokens", "trigger_identity"]
