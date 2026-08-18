"""Stage 1: candidate extraction, rule-based.

Three rule-based miners over a chunk's transcript text, no model contact:
capitalized runs, spelled-out letter sequences, and repeated OOV-ish
tokens. The LLM-prompted extractor is a LATER wire-in -- it should
implement the same :class:`CandidateExtractor` protocol as
:class:`RuleBasedExtractor` does here, so the rest of the pipeline (stages
2-4) needs no change when it lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_CAP_TOKEN_RE = re.compile(r"[A-Z][a-zA-Z']*$")
_SPELLED_LETTER_RUN_RE = re.compile(r"\b(?:[A-Z]\s+){1,}[A-Z]\b")
_WORD_RE = re.compile(r"[A-Za-z]+")
_STRIP_CHARS = ".,!?;:\"'()"

_FIRST_PERSON = {"i", "i'm", "i've", "i'll", "i'd"}
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "this", "that",
    "it", "we", "you", "he", "she", "they", "at", "as", "by", "from",
    "so", "if", "then", "will", "would", "can", "could", "should", "not",
    "do", "does", "did", "has", "have", "had", "about", "there", "our",
    "us", "their", "his", "her", "its", "these", "those", "just", "also",
    "very", "more", "than", "into", "over", "again", "once", "some",
}


@dataclass(frozen=True)
class Candidate:
    surface: str
    method: str  # "capitalized_run" | "spelled_out" | "repeated_oov"


@runtime_checkable
class CandidateExtractor(Protocol):
    def extract(self, text: str) -> list[Candidate]: ...


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]


def extract_capitalized_runs(text: str) -> list[Candidate]:
    """Maximal runs of capitalized tokens, sentence-initial position
    excluded (mirrors the MeetingBank/AMI census exclusion rule: a token
    at the start of a sentence is never a candidate on its own, since
    ordinary sentence-initial capitalization would otherwise flood the
    count)."""

    out: list[Candidate] = []
    for sentence in _sentences(text):
        tokens = sentence.split()
        run: list[str] = []
        for idx, raw in enumerate(tokens):
            word = raw.strip(_STRIP_CHARS)
            is_cap = bool(word) and bool(_CAP_TOKEN_RE.match(word)) and word.lower() not in _FIRST_PERSON
            if is_cap and idx != 0:
                run.append(word)
            else:
                if run:
                    out.append(Candidate(" ".join(run), "capitalized_run"))
                run = []
        if run:
            out.append(Candidate(" ".join(run), "capitalized_run"))
    return out


def extract_spelled_out_sequences(text: str) -> list[Candidate]:
    """Sequences of single capital letters spelled out with spaces
    (``P G L O S S``), collapsed into one contiguous candidate token
    (``PGLOSS``)."""

    out: list[Candidate] = []
    for match in _SPELLED_LETTER_RUN_RE.finditer(text):
        letters = match.group(0).split()
        if len(letters) < 2:
            continue
        out.append(Candidate("".join(letters), "spelled_out"))
    return out


def extract_repeated_oov_tokens(text: str, *, min_repeats: int = 2) -> list[Candidate]:
    """Lowercase alphabetic tokens, length >= 4, not a stopword or
    first-person pronoun, appearing at least ``min_repeats`` times in
    ``text`` -- a cheap out-of-vocabulary proxy, no model contact."""

    counts: dict[str, int] = {}
    for w in _WORD_RE.findall(text):
        lw = w.lower()
        if len(lw) < 4 or lw in _STOPWORDS or lw in _FIRST_PERSON:
            continue
        counts[lw] = counts.get(lw, 0) + 1
    out = [Candidate(w, "repeated_oov") for w, c in counts.items() if c >= min_repeats]
    out.sort(key=lambda c: c.surface)
    return out


def extract_candidates(text: str, *, min_repeats: int = 2) -> list[Candidate]:
    """Combine all three rule-based miners over one chunk's text."""

    return (
        extract_capitalized_runs(text)
        + extract_spelled_out_sequences(text)
        + extract_repeated_oov_tokens(text, min_repeats=min_repeats)
    )


@dataclass(frozen=True)
class RuleBasedExtractor:
    """Concrete :class:`CandidateExtractor`. An ``LLMPromptedExtractor``
    implementing the same protocol is a later, out-of-scope wire-in --
    this repository makes zero model contact."""

    min_repeats: int = 2

    def extract(self, text: str) -> list[Candidate]:
        return extract_candidates(text, min_repeats=self.min_repeats)
