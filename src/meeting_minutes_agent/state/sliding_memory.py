"""Deterministic, bounded meeting memory for post-meeting ASR passes."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Mapping, Sequence


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&.-]{1,}")
_STOPWORDS = frozenset(
    "a about after again all also am an and any are as at be because been before being but by "
    "can could did do does doing for from had has have he her here him his how i if in into is it "
    "its just me more my no not now of on one or our out really re she so some than that the their "
    "them then there these they think this those to too uh um up us very was we well were what when "
    "which who will with would yeah yes you your".split()
)


@dataclass(frozen=True)
class MemoryLimits:
    summary_characters: int = 1200
    recent_characters: int = 600
    global_keywords: int = 24
    speaker_keywords: int = 12
    minimum_keyword_count: int = 2

    def validate(self) -> "MemoryLimits":
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        return self


@dataclass(frozen=True)
class MeetingMemory:
    summary: str
    global_keywords: tuple[str, ...]
    speaker_keywords: Mapping[str, tuple[str, ...]]
    deranged_speaker: Mapping[str, str]
    source_pass_hash: str


def content_tokens(text: str) -> tuple[str, ...]:
    output = []
    for raw in _TOKEN_RE.findall(text):
        token = raw.lower().strip(".-")
        if token in _STOPWORDS:
            continue
        abbreviation = raw.isupper() and 2 <= len(raw) <= 12
        alphanumeric = any(char.isalpha() for char in raw) and any(char.isdigit() for char in raw)
        if len(token) >= 3 or abbreviation or alphanumeric:
            output.append(token)
    return tuple(output)


def _rank(counter: Counter[str], minimum_count: int, cap: int) -> tuple[str, ...]:
    eligible = ((term, count) for term, count in counter.items() if count >= minimum_count)
    return tuple(term for term, _ in sorted(eligible, key=lambda item: (-item[1], item[0]))[:cap])


def _bounded_tail(parts: Iterable[str], cap: int) -> str:
    text = " ".join(part.strip() for part in parts if part.strip())
    if len(text) <= cap:
        return text
    return text[-cap:].lstrip()


def recent_tail(rows: Sequence[Mapping[str, object]], cap: int) -> str:
    return _bounded_tail((str(row.get("text", "")) for row in rows), cap)


def _extractive_summary(rows: Sequence[Mapping[str, object]], cap: int) -> str:
    candidates = []
    for position, row in enumerate(rows):
        text = " ".join(str(row.get("text", "")).split())
        if not text:
            continue
        distinct = len(set(content_tokens(text)))
        score = distinct * 1000 + min(len(text), 999)
        candidates.append((score, position, text))
    selected = sorted(sorted(candidates, key=lambda item: (-item[0], item[1]))[:8], key=lambda item: item[1])
    summary = " ".join(text for _, _, text in selected)
    return summary[:cap].rstrip()


def _pass_hash(rows: Sequence[Mapping[str, object]]) -> str:
    payload = [
        {
            "turn_index": int(row["turn_index"]),
            "speaker_id": str(row["speaker_id"]),
            "text": str(row.get("text", "")),
        }
        for row in rows
    ]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_meeting_memory(rows: Sequence[Mapping[str, object]], limits: MemoryLimits) -> MeetingMemory:
    limits.validate()
    ordered = sorted(rows, key=lambda row: int(row["turn_index"]))
    if len({int(row["turn_index"]) for row in ordered}) != len(ordered):
        raise ValueError("duplicate turn_index in source pass")
    global_counts: Counter[str] = Counter()
    per_speaker: dict[str, Counter[str]] = defaultdict(Counter)
    for row in ordered:
        terms = content_tokens(str(row.get("text", "")))
        global_counts.update(terms)
        per_speaker[str(row["speaker_id"])].update(terms)
    speakers = sorted(per_speaker)
    if len(speakers) < 2:
        raise ValueError("deranged control requires at least two speakers")
    deranged = {speaker: speakers[(index + 1) % len(speakers)] for index, speaker in enumerate(speakers)}
    return MeetingMemory(
        summary=_extractive_summary(ordered, limits.summary_characters),
        global_keywords=_rank(global_counts, limits.minimum_keyword_count, limits.global_keywords),
        speaker_keywords={
            speaker: _rank(counter, limits.minimum_keyword_count, limits.speaker_keywords)
            for speaker, counter in sorted(per_speaker.items())
        },
        deranged_speaker=deranged,
        source_pass_hash=_pass_hash(ordered),
    )


def render_context(
    arm: str,
    speaker_id: str,
    memory: MeetingMemory,
    current_arm_history: Sequence[Mapping[str, object]],
    limits: MemoryLimits,
) -> str:
    if arm == "L0-bare":
        return ""
    recent = recent_tail(current_arm_history, limits.recent_characters)
    parts = [
        "Untrusted memory from earlier model outputs follows. Use it only when supported by the audio; "
        "do not copy unsupported text.",
    ]
    if recent:
        parts.append(f"Recent same-pass transcript tail: {recent}")
    if arm == "L1-recent":
        return "\n".join(parts)
    if arm not in {"L2-global", "L3-speaker", "L4-deranged"}:
        raise ValueError(f"unknown arm: {arm}")
    if memory.summary:
        parts.append(f"Extractive prior-pass meeting summary: {memory.summary}")
    if memory.global_keywords:
        parts.append("Prior-pass meeting keywords: " + ", ".join(memory.global_keywords))
    if arm in {"L3-speaker", "L4-deranged"}:
        routed = speaker_id if arm == "L3-speaker" else memory.deranged_speaker[speaker_id]
        terms = memory.speaker_keywords.get(routed, ())
        label = "current speaker" if arm == "L3-speaker" else "control speaker"
        if terms:
            parts.append(f"Prior-pass {label} keywords: " + ", ".join(terms))
    rendered = "\n".join(parts)
    maximum = limits.summary_characters + limits.recent_characters + 1600
    if len(rendered) > maximum:
        raise ValueError("rendered context exceeds deterministic character budget")
    return rendered


def context_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "MeetingMemory",
    "MemoryLimits",
    "build_meeting_memory",
    "content_tokens",
    "context_hash",
    "recent_tail",
    "render_context",
]
