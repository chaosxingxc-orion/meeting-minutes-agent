"""Frozen six-arm request surface for the E4 speaker-conditioning smoke."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..heads.request import HeadRequest, build_supplied_text
from ..runreceipt import config_hash
from .contextasr import SYSTEM_INSTRUCTION

ARMS = ("E4-0-bare", "E4-1-label", "E4-2-global", "E4-3-speaker", "E4-4-wrong", "E4-5-corrupt")
TEMPLATE_ID = "e4-speaker-conditioned-v1"
TEMPLATE_SHA256 = config_hash({"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION})


@dataclass(frozen=True)
class E4Target:
    uniq_id: str
    turn_index: int
    speaker_id: str
    start: float
    end: float
    reference_text: str
    carry_entities: tuple[str, ...]
    pass0_text: str
    speaker_terms: tuple[str, ...]
    global_terms: tuple[str, ...]
    wrong_terms: tuple[str, ...]
    corrupt_terms: tuple[str, ...]
    source_tar: str
    tar_member: str
    audio_sha256: str

    @property
    def target_id(self) -> str:
        return f"{self.uniq_id}-turn{self.turn_index:03d}"

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "E4Target":
        return cls(
            uniq_id=str(value["uniq_id"]), turn_index=int(value["turn_index"]),
            speaker_id=str(value["speaker_id"]), start=float(value["start"]), end=float(value["end"]),
            reference_text=str(value["reference_text"]), carry_entities=tuple(str(x) for x in value["carry_entities"]),
            pass0_text=str(value["pass0_text"]), speaker_terms=tuple(str(x) for x in value["speaker_terms"]),
            global_terms=tuple(str(x) for x in value["global_terms"]), wrong_terms=tuple(str(x) for x in value["wrong_terms"]),
            corrupt_terms=tuple(str(x) for x in value["corrupt_terms"]), source_tar=str(value["source_tar"]),
            tar_member=str(value["tar_member"]), audio_sha256=str(value["audio_sha256"]),
        )


@dataclass(frozen=True)
class E4Manifest:
    raw: Mapping[str, Any]
    targets: tuple[E4Target, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class E4Request:
    request_id: str
    arm: str
    target: E4Target
    head_request: HeadRequest
    injected_terms: tuple[str, ...]


def load_manifest(path: str | Path) -> E4Manifest:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != "e4-conditioning-manifest-v1":
        raise ValueError(f"unsupported E4 manifest schema: {document.get('schema_version')!r}")
    payload = {str(k): v for k, v in document.items() if k != "content_hash"}
    expected = config_hash(payload)
    if document.get("content_hash") != expected:
        raise ValueError(f"E4 manifest hash mismatch: recorded={document.get('content_hash')!r}, computed={expected}")
    targets = tuple(E4Target.from_dict(x) for x in document["targets"])
    if len({target.target_id for target in targets}) != len(targets):
        raise ValueError("duplicate E4 target ids")
    for target in targets:
        sizes = {len(target.speaker_terms), len(target.global_terms), len(target.wrong_terms), len(target.corrupt_terms)}
        if len(sizes) != 1 or not target.speaker_terms:
            raise ValueError(f"E4 target {target.target_id} does not have non-empty equal-length state arms")
    return E4Manifest(document, targets)


def _state_block(target: E4Target, terms: Sequence[str] | None) -> tuple[str, ...]:
    parts = [f"=== CURRENT SPEAKER ===\n{target.speaker_id}"]
    if terms is not None:
        parts.append("=== POSSIBLE TERMS (use only when heard) ===\n" + "\n".join(f"- {term}" for term in terms))
    return build_supplied_text(*parts)


def build_head_request(target: E4Target, arm: str) -> tuple[HeadRequest, tuple[str, ...]]:
    if arm not in ARMS:
        raise ValueError(f"unknown E4 arm: {arm}")
    terms: tuple[str, ...] = ()
    supplied: tuple[str, ...] = ()
    if arm == "E4-1-label":
        supplied = _state_block(target, None)
    elif arm != "E4-0-bare":
        terms = {
            "E4-2-global": target.global_terms,
            "E4-3-speaker": target.speaker_terms,
            "E4-4-wrong": target.wrong_terms,
            "E4-5-corrupt": target.corrupt_terms,
        }[arm]
        supplied = _state_block(target, terms)
    return HeadRequest(SYSTEM_INSTRUCTION, supplied, {}, TEMPLATE_ID, TEMPLATE_SHA256), terms


def build_requests(manifest: E4Manifest) -> tuple[E4Request, ...]:
    requests: list[E4Request] = []
    for index, target in enumerate(manifest.targets):
        rotated = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
        for arm in rotated:
            head, terms = build_head_request(target, arm)
            requests.append(E4Request(f"e4-{target.target_id}-{arm.lower()}", arm, target, head, terms))
    return tuple(requests)


__all__ = ["ARMS", "E4Manifest", "E4Request", "E4Target", "TEMPLATE_SHA256", "build_head_request", "build_requests", "load_manifest"]
