"""Leakage-separated manifests and four-arm requests for E4 confirmatory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..heads.request import HeadRequest, build_supplied_text
from ..runreceipt import config_hash
from .contextasr import SYSTEM_INSTRUCTION

ARMS = ("CF0-bare", "CF1-global", "CF2-speaker", "CF3-wrong")
TEMPLATE_ID = "e4-confirmatory-speaker-v1"
TEMPLATE_SHA256 = config_hash({"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION})


@dataclass(frozen=True)
class RuntimeTurn:
    index: int
    speaker_id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeTurn":
        return cls(int(value["index"]), str(value["speaker_id"]), float(value["start"]), float(value["end"]))


@dataclass(frozen=True)
class RuntimeDialogue:
    uniq_id: str
    duration: float
    turns: tuple[RuntimeTurn, ...]
    source_tar: str
    tar_member: str
    audio_sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeDialogue":
        return cls(
            str(value["uniq_id"]), float(value["duration"]),
            tuple(RuntimeTurn.from_dict(x) for x in value["turns"]),
            str(value["source_tar"]), str(value["tar_member"]), str(value["audio_sha256"]),
        )


@dataclass(frozen=True)
class Pass0RuntimeManifest:
    raw: Mapping[str, Any]
    entries: tuple[RuntimeDialogue, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class ScoreTurn:
    index: int
    speaker_id: str
    reference_text: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScoreTurn":
        return cls(int(value["index"]), str(value["speaker_id"]), str(value["reference_text"]))


@dataclass(frozen=True)
class ScoreDialogue:
    uniq_id: str
    entity_list: tuple[str, ...]
    turns: tuple[ScoreTurn, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScoreDialogue":
        return cls(str(value["uniq_id"]), tuple(str(x) for x in value["entity_list"]), tuple(ScoreTurn.from_dict(x) for x in value["turns"]))


@dataclass(frozen=True)
class Pass0ScoreManifest:
    raw: Mapping[str, Any]
    entries: tuple[ScoreDialogue, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class RuntimeTarget:
    target_id: str
    uniq_id: str
    turn_index: int
    speaker_id: str
    start: float
    end: float
    global_terms: tuple[str, ...]
    speaker_terms: tuple[str, ...]
    wrong_terms: tuple[str, ...]
    source_tar: str
    tar_member: str
    audio_sha256: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuntimeTarget":
        return cls(
            str(value["target_id"]), str(value["uniq_id"]), int(value["turn_index"]), str(value["speaker_id"]),
            float(value["start"]), float(value["end"]), tuple(str(x) for x in value["global_terms"]),
            tuple(str(x) for x in value["speaker_terms"]), tuple(str(x) for x in value["wrong_terms"]),
            str(value["source_tar"]), str(value["tar_member"]), str(value["audio_sha256"]),
        )


@dataclass(frozen=True)
class RuntimeBinding:
    raw: Mapping[str, Any]
    targets: tuple[RuntimeTarget, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class ScoreTarget:
    target_id: str
    uniq_id: str
    reference_text: str
    carry_entities: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScoreTarget":
        return cls(str(value["target_id"]), str(value["uniq_id"]), str(value["reference_text"]), tuple(str(x) for x in value["carry_entities"]))


@dataclass(frozen=True)
class ScoreBinding:
    raw: Mapping[str, Any]
    targets: tuple[ScoreTarget, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class ConfirmatoryRequest:
    request_id: str
    arm: str
    target: RuntimeTarget
    head_request: HeadRequest
    injected_terms: tuple[str, ...]


def _load(path: str | Path, schema: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != schema:
        raise ValueError(f"unsupported schema: {document.get('schema_version')!r}; expected {schema}")
    expected = config_hash({str(k): v for k, v in document.items() if k != "content_hash"})
    if document.get("content_hash") != expected:
        raise ValueError(f"manifest hash mismatch: recorded={document.get('content_hash')!r}, computed={expected}")
    return document


def load_pass0_runtime(path: str | Path) -> Pass0RuntimeManifest:
    raw = _load(path, "e4-cf-pass0-runtime-v1")
    return Pass0RuntimeManifest(raw, tuple(RuntimeDialogue.from_dict(x) for x in raw["entries"]))


def load_pass0_score(path: str | Path) -> Pass0ScoreManifest:
    raw = _load(path, "e4-cf-pass0-score-v1")
    return Pass0ScoreManifest(raw, tuple(ScoreDialogue.from_dict(x) for x in raw["entries"]))


def load_runtime_binding(path: str | Path) -> RuntimeBinding:
    raw = _load(path, "e4-cf-runtime-binding-v1")
    targets = tuple(RuntimeTarget.from_dict(x) for x in raw["targets"])
    for target in targets:
        if not target.speaker_terms or len({len(target.global_terms), len(target.speaker_terms), len(target.wrong_terms)}) != 1:
            raise ValueError(f"non-equal or empty state at {target.target_id}")
    return RuntimeBinding(raw, targets)


def load_score_binding(path: str | Path) -> ScoreBinding:
    raw = _load(path, "e4-cf-score-binding-v1")
    return ScoreBinding(raw, tuple(ScoreTarget.from_dict(x) for x in raw["targets"]))


def build_head_request(target: RuntimeTarget, arm: str) -> tuple[HeadRequest, tuple[str, ...]]:
    if arm not in ARMS:
        raise ValueError(f"unknown confirmatory arm: {arm}")
    terms: tuple[str, ...] = ()
    supplied: tuple[str, ...] = ()
    if arm != "CF0-bare":
        terms = {"CF1-global": target.global_terms, "CF2-speaker": target.speaker_terms, "CF3-wrong": target.wrong_terms}[arm]
        supplied = build_supplied_text(
            f"=== CURRENT SPEAKER ===\n{target.speaker_id}",
            "=== POSSIBLE TERMS (use only when heard) ===\n" + "\n".join(f"- {term}" for term in terms),
        )
    return HeadRequest(SYSTEM_INSTRUCTION, supplied, {}, TEMPLATE_ID, TEMPLATE_SHA256), terms


def build_requests(binding: RuntimeBinding) -> tuple[ConfirmatoryRequest, ...]:
    requests: list[ConfirmatoryRequest] = []
    for index, target in enumerate(binding.targets):
        rotated = ARMS[index % 4:] + ARMS[:index % 4]
        for arm in rotated:
            head, terms = build_head_request(target, arm)
            requests.append(ConfirmatoryRequest(f"e4cf-{target.target_id}-{arm.lower()}", arm, target, head, terms))
    return tuple(requests)


__all__ = [
    "ARMS", "ConfirmatoryRequest", "Pass0RuntimeManifest", "Pass0ScoreManifest", "RuntimeBinding", "RuntimeDialogue",
    "RuntimeTarget", "RuntimeTurn", "ScoreBinding", "ScoreDialogue", "ScoreTarget", "ScoreTurn", "TEMPLATE_SHA256",
    "build_head_request", "build_requests", "load_pass0_runtime", "load_pass0_score", "load_runtime_binding", "load_score_binding",
]
