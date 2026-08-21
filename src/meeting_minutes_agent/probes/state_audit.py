"""Frozen structures and scoring helpers for the E3 legal-state audit.

Reference text and entity lists are scoring-side data.  Runtime state is
constructed only from chronological Pass-0 hypotheses supplied to
``build_state_views``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..glossary.arms import gated_arm, naive_raw_arm
from ..glossary.gate import GateConfig
from ..runreceipt import config_hash

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_match(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def contains_entity(text: str, entity: str) -> bool:
    haystack = f" {normalize_match(text)} "
    needle = normalize_match(entity)
    return bool(needle) and f" {needle} " in haystack


@dataclass(frozen=True)
class StateAuditTurn:
    index: int
    speaker_id: str
    start: float
    end: float
    reference_text: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateAuditTurn":
        return cls(
            index=int(value["index"]),
            speaker_id=str(value["speaker_id"]),
            start=float(value["start"]),
            end=float(value["end"]),
            reference_text=str(value["reference_text"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "speaker_id": self.speaker_id,
            "start": self.start,
            "end": self.end,
            "reference_text": self.reference_text,
        }


@dataclass(frozen=True)
class StateAuditEntry:
    uniq_id: str
    duration: float
    entity_list: tuple[str, ...]
    turns: tuple[StateAuditTurn, ...]
    source_tar: str
    tar_member: str
    audio_sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateAuditEntry":
        return cls(
            uniq_id=str(value["uniq_id"]),
            duration=float(value["duration"]),
            entity_list=tuple(str(x) for x in value["entity_list"]),
            turns=tuple(StateAuditTurn.from_dict(x) for x in value["turns"]),
            source_tar=str(value["source_tar"]),
            tar_member=str(value["tar_member"]),
            audio_sha256=str(value["audio_sha256"]),
        )


@dataclass(frozen=True)
class StateAuditManifest:
    raw: Mapping[str, Any]
    entries: tuple[StateAuditEntry, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


def load_manifest(path: str | Path) -> StateAuditManifest:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != "e3-state-audit-manifest-v1":
        raise ValueError(f"unsupported E3 manifest schema: {document.get('schema_version')!r}")
    payload = {str(k): v for k, v in document.items() if k != "content_hash"}
    expected = config_hash(payload)
    if document.get("content_hash") != expected:
        raise ValueError(f"E3 manifest hash mismatch: recorded={document.get('content_hash')!r}, computed={expected}")
    entries = tuple(StateAuditEntry.from_dict(x) for x in document["entries"])
    if len({entry.uniq_id for entry in entries}) != len(entries):
        raise ValueError("E3 manifest contains duplicate dialogue ids")
    for entry in entries:
        if tuple(turn.index for turn in entry.turns) != tuple(range(len(entry.turns))):
            raise ValueError(f"non-contiguous turn indices in {entry.uniq_id}")
        if any(turn.duration <= 0 for turn in entry.turns):
            raise ValueError(f"non-positive turn duration in {entry.uniq_id}")
    return StateAuditManifest(raw=document, entries=entries)


def carry_targets(entry: StateAuditEntry, target_index: int, *, same_speaker: bool) -> tuple[str, ...]:
    """Gold-side entities in a target turn that occurred in eligible history."""

    target = entry.turns[target_index]
    prior = [
        turn
        for turn in entry.turns[:target_index]
        if not same_speaker or turn.speaker_id == target.speaker_id
    ]
    return tuple(
        entity
        for entity in entry.entity_list
        if contains_entity(target.reference_text, entity)
        and any(contains_entity(turn.reference_text, entity) for turn in prior)
    )


def _surfaces(plan) -> tuple[str, ...]:
    return tuple(entry.canonical_surface for entry in plan.entries)


def build_state_views(
    entry: StateAuditEntry,
    hypotheses: Mapping[int, str],
    target_index: int,
) -> dict[str, tuple[str, ...]]:
    """Build legal state arms using only prior Pass-0 hypothesis text."""

    target = entry.turns[target_index]
    same = [turn for turn in entry.turns[:target_index] if turn.speaker_id == target.speaker_id]
    other = [turn for turn in entry.turns[:target_index] if turn.speaker_id != target.speaker_id]
    all_prior = list(entry.turns[:target_index])

    def joined(turns: Sequence[StateAuditTurn]) -> str:
        return " ".join(hypotheses[turn.index] for turn in turns)

    latest_same = same[-1:] if same else []
    return {
        "gated-speaker": _surfaces(gated_arm(joined(same), chunk_index=target_index, introduced_by=target.speaker_id)),
        "first-mention-speaker": _surfaces(
            gated_arm(
                joined(same),
                chunk_index=target_index,
                introduced_by=target.speaker_id,
                gate_config=GateConfig(min_evidence=1, inventory_cap=8),
            )
        ),
        "gated-global": _surfaces(gated_arm(joined(all_prior), chunk_index=target_index)),
        "naive-speaker": _surfaces(naive_raw_arm(joined(same), chunk_index=target_index, introduced_by=target.speaker_id)),
        "no-carry-speaker": _surfaces(gated_arm(joined(latest_same), chunk_index=target_index, introduced_by=target.speaker_id)),
        "wrong-speaker": _surfaces(gated_arm(joined(other), chunk_index=target_index)),
    }


def score_state(
    entry: StateAuditEntry,
    target_index: int,
    terms: Sequence[str],
) -> dict[str, int]:
    """Score one already-built state; reference is consulted only here.

    Support is measured against prior speech, not against the dataset's
    non-exhaustive entity list.  A legitimate proper noun is therefore not
    mislabeled as pollution merely because it is absent from that list.
    """

    normalized_terms = {normalize_match(term) for term in terms if normalize_match(term)}
    target = entry.turns[target_index]
    prior = entry.turns[:target_index]
    same_prior = [turn for turn in prior if turn.speaker_id == target.speaker_id]
    supported = {
        term for term in normalized_terms if any(contains_entity(turn.reference_text, term) for turn in prior)
    }
    speaker_supported = {
        term for term in normalized_terms if any(contains_entity(turn.reference_text, term) for turn in same_prior)
    }
    target_relevant = {term for term in normalized_terms if contains_entity(target.reference_text, term)}
    same_targets = {normalize_match(x) for x in carry_targets(entry, target_index, same_speaker=True)}
    global_targets = {normalize_match(x) for x in carry_targets(entry, target_index, same_speaker=False)}
    return {
        "terms": len(normalized_terms),
        "supported_terms": len(supported),
        "hallucinated_terms": len(normalized_terms - supported),
        "speaker_supported_terms": len(speaker_supported),
        "off_speaker_terms": len(supported - speaker_supported),
        "target_relevant_terms": len(target_relevant),
        "same_target_hits": len(normalized_terms & same_targets),
        "same_targets": len(same_targets),
        "global_target_hits": len(normalized_terms & global_targets),
        "global_targets": len(global_targets),
    }


__all__ = [
    "StateAuditEntry",
    "StateAuditManifest",
    "StateAuditTurn",
    "build_state_views",
    "carry_targets",
    "contains_entity",
    "load_manifest",
    "normalize_match",
    "score_state",
]
