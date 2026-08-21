"""Two-arm exploratory direction pilot for disjoint speaker state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..heads.request import HeadRequest
from ..runreceipt import config_hash
from .contextasr_scoring import normalize_english
from .e4_confirmatory import RuntimeTarget, ScoreTarget, build_head_request

ARMS = ("D0-global", "D1-speaker")


@dataclass(frozen=True)
class DirectionRuntimeBinding:
    raw: Mapping[str, Any]
    targets: tuple[RuntimeTarget, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class DirectionScoreBinding:
    raw: Mapping[str, Any]
    targets: tuple[ScoreTarget, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class DirectionRequest:
    request_id: str
    arm: str
    target: RuntimeTarget
    head_request: HeadRequest
    injected_terms: tuple[str, ...]


def _load(path: str | Path, schema: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != schema:
        raise ValueError(f"unsupported schema: {document.get('schema_version')!r}; expected {schema}")
    expected = config_hash({str(key): value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected:
        raise ValueError("binding hash mismatch")
    return document


def load_runtime_binding(path: str | Path) -> DirectionRuntimeBinding:
    raw = _load(path, "e4-disjoint-dir-runtime-binding-v1")
    targets = tuple(RuntimeTarget.from_dict(item) for item in raw["targets"])
    if len({target.target_id for target in targets}) != len(targets):
        raise ValueError("duplicate runtime target id")
    for target in targets:
        widths = {len(target.global_terms), len(target.speaker_terms), len(target.wrong_terms)}
        if not target.speaker_terms or len(widths) != 1:
            raise ValueError(f"non-equal or empty state at {target.target_id}")
        speaker = {normalize_english(term) for term in target.speaker_terms}
        wrong = {normalize_english(term) for term in target.wrong_terms}
        if speaker & wrong:
            raise ValueError(f"non-disjoint target in direction binding: {target.target_id}")
    return DirectionRuntimeBinding(raw, targets)


def load_score_binding(path: str | Path) -> DirectionScoreBinding:
    raw = _load(path, "e4-disjoint-dir-score-binding-v1")
    targets = tuple(ScoreTarget.from_dict(item) for item in raw["targets"])
    if len({target.target_id for target in targets}) != len(targets):
        raise ValueError("duplicate score target id")
    return DirectionScoreBinding(raw, targets)


def build_requests(binding: DirectionRuntimeBinding) -> tuple[DirectionRequest, ...]:
    requests: list[DirectionRequest] = []
    mapping = {"D0-global": "CF1-global", "D1-speaker": "CF2-speaker"}
    for index, target in enumerate(binding.targets):
        rotated = ARMS[index % 2 :] + ARMS[: index % 2]
        for arm in rotated:
            head, terms = build_head_request(target, mapping[arm])
            request_id = f"e4dir-{target.target_id}-{arm.lower()}"
            requests.append(DirectionRequest(request_id, arm, target, head, terms))
    return tuple(requests)


__all__ = [
    "ARMS",
    "DirectionRequest",
    "DirectionRuntimeBinding",
    "DirectionScoreBinding",
    "build_requests",
    "load_runtime_binding",
    "load_score_binding",
]
