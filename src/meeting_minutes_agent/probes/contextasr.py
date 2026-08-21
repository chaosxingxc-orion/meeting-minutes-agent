"""Frozen request design for the ContextASR context-use capability smoke.

This probe is a Tier-M1 diagnostic: the correct entity list is derived from
the reference-side dataset metadata and may only be used by the ``C2-entity``
ceiling arm.  It tests whether the frozen core can *use* supplied spellings;
it does not claim that a deployable meeting loop can discover them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..heads.request import HeadRequest, build_supplied_text
from ..runreceipt import config_hash

ARMS = ("C0-bare", "C1-domain", "C2-entity", "C3-deranged", "C4-corrupt")
TEMPLATE_ID = "contextasr-transcribe-only-v1"
SYSTEM_INSTRUCTION = (
    "Transcribe the supplied English speech exactly as spoken. Return only "
    "the transcript as plain text, with no explanation or formatting. If "
    "context hints are supplied, use their spelling only when supported by "
    "the audio; never insert a hinted term merely because it is listed."
)
TEMPLATE_SHA256 = config_hash(
    {"template_id": TEMPLATE_ID, "system_instruction": SYSTEM_INSTRUCTION}
)


@dataclass(frozen=True)
class ContextAsrEntry:
    uniq_id: str
    language: str
    duration: float
    domain_label: str
    reference_text: str
    entity_list: tuple[str, ...]
    deranged_entity_list: tuple[str, ...]
    corrupt_entity_list: tuple[str, ...]
    source_tar: str
    tar_member: str
    audio_sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ContextAsrEntry":
        return cls(
            uniq_id=str(value["uniq_id"]),
            language=str(value["language"]),
            duration=float(value["duration"]),
            domain_label=str(value["domain_label"]),
            reference_text=str(value["reference_text"]),
            entity_list=tuple(str(x) for x in value["entity_list"]),
            deranged_entity_list=tuple(str(x) for x in value["deranged_entity_list"]),
            corrupt_entity_list=tuple(str(x) for x in value["corrupt_entity_list"]),
            source_tar=str(value["source_tar"]),
            tar_member=str(value["tar_member"]),
            audio_sha256=str(value["audio_sha256"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "uniq_id": self.uniq_id,
            "language": self.language,
            "duration": self.duration,
            "domain_label": self.domain_label,
            "reference_text": self.reference_text,
            "entity_list": list(self.entity_list),
            "deranged_entity_list": list(self.deranged_entity_list),
            "corrupt_entity_list": list(self.corrupt_entity_list),
            "source_tar": self.source_tar,
            "tar_member": self.tar_member,
            "audio_sha256": self.audio_sha256,
        }


@dataclass(frozen=True)
class ContextAsrManifest:
    raw: Mapping[str, Any]
    entries: tuple[ContextAsrEntry, ...]

    @property
    def content_hash(self) -> str:
        return str(self.raw["content_hash"])


@dataclass(frozen=True)
class ContextAsrRequest:
    request_id: str
    arm: str
    entry: ContextAsrEntry
    head_request: HeadRequest
    injected_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "arm": self.arm,
            "uniq_id": self.entry.uniq_id,
            "template_id": self.head_request.template_id,
            "template_sha256": self.head_request.template_sha256,
            "injected_terms": list(self.injected_terms),
        }


def _payload_without_hash(document: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in document.items() if k != "content_hash"}


def load_manifest(path: str | Path) -> ContextAsrManifest:
    resolved = Path(path)
    document = json.loads(resolved.read_text(encoding="utf-8"))
    if document.get("schema_version") != "contextasr-smoke-manifest-v1":
        raise ValueError(f"unsupported ContextASR manifest schema: {document.get('schema_version')!r}")
    expected = config_hash(_payload_without_hash(document))
    if document.get("content_hash") != expected:
        raise ValueError(
            f"ContextASR manifest hash mismatch: recorded={document.get('content_hash')!r}, computed={expected}"
        )
    entries = tuple(ContextAsrEntry.from_dict(x) for x in document["entries"])
    if len({e.uniq_id for e in entries}) != len(entries):
        raise ValueError("ContextASR manifest contains duplicate uniq_id values")
    if any(e.language != "English" for e in entries):
        raise ValueError("v1 smoke admits English records only")
    return ContextAsrManifest(raw=document, entries=entries)


def _render_context(title: str, values: Sequence[str]) -> str:
    return title + "\n" + "\n".join(f"- {value}" for value in values)


def build_head_request(entry: ContextAsrEntry, arm: str) -> tuple[HeadRequest, tuple[str, ...]]:
    if arm not in ARMS:
        raise ValueError(f"unknown ContextASR arm: {arm!r}")
    supplied: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()
    if arm == "C1-domain":
        supplied = (f"=== DOMAIN HINT ===\n{entry.domain_label}",)
    elif arm in {"C2-entity", "C3-deranged", "C4-corrupt"}:
        terms = {
            "C2-entity": entry.entity_list,
            "C3-deranged": entry.deranged_entity_list,
            "C4-corrupt": entry.corrupt_entity_list,
        }[arm]
        supplied = (
            f"=== DOMAIN HINT ===\n{entry.domain_label}",
            _render_context("=== POSSIBLE TERMS (use only when heard) ===", terms),
        )
    return (
        HeadRequest(
            task_instruction=SYSTEM_INSTRUCTION,
            supplied_text=build_supplied_text(*supplied),
            decoding_params={},
            template_id=TEMPLATE_ID,
            template_sha256=TEMPLATE_SHA256,
        ),
        terms,
    )


def build_requests(manifest: ContextAsrManifest) -> tuple[ContextAsrRequest, ...]:
    """Return a deterministic Latin rotation over arms to balance server drift."""

    requests: list[ContextAsrRequest] = []
    for sample_index, entry in enumerate(manifest.entries):
        rotated = ARMS[sample_index % len(ARMS) :] + ARMS[: sample_index % len(ARMS)]
        for arm in rotated:
            head, terms = build_head_request(entry, arm)
            requests.append(
                ContextAsrRequest(
                    request_id=f"cctx-{entry.uniq_id}-{arm.lower()}",
                    arm=arm,
                    entry=entry,
                    head_request=head,
                    injected_terms=terms,
                )
            )
    return tuple(requests)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "ARMS",
    "ContextAsrEntry",
    "ContextAsrManifest",
    "ContextAsrRequest",
    "SYSTEM_INSTRUCTION",
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "build_head_request",
    "build_requests",
    "load_manifest",
    "sha256_bytes",
]
