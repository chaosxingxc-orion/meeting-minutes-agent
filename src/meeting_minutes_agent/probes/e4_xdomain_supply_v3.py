"""Reserve-only narrow-class supply audit for Earnings-22."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .e4_xdomain_supply_v2 import (
    EXPECTED_SOURCE_COMMIT,
    RESERVE_SIZE,
    SLICE_SECONDS,
    EntityMention,
    Earnings22AuditError,
    load_entity_mentions,
    sha256_file,
)

EXPECTED_PARENT_CONTENT_HASH = "67f0fc955ff9057ee5819ee3f05957ad1a04d2603564ba75366d4d319e2bd313"
EXPECTED_PARENT_SCHEMA = "e4-xdomain-supply-v2-input-v1"
ALLOWED_CLASSES = frozenset({"ABBREVIATION", "ALPHANUMERIC"})

MIN_ELIGIBLE_MEETINGS = 20
MIN_EXCLUSIVE_CARRY = 100
MAX_SURFACE_SHARE = 0.20


@dataclass(frozen=True)
class ReserveInput:
    file_id: str
    path: Path


@dataclass(frozen=True)
class NarrowMeetingCounts:
    candidate_units: int
    admitted_mentions: int
    excluded_unaligned_mentions: int
    same_speaker_carry: int
    shared_carry: int
    global_only_carry: int
    exclusive_by_surface: Mapping[str, int]
    candidate_units_by_class: Mapping[str, int]
    exclusive_units_by_class: Mapping[str, int]

    @property
    def exclusive_carry(self) -> int:
        return sum(self.exclusive_by_surface.values())

    @property
    def eligible(self) -> bool:
        return self.exclusive_carry >= 2


def _canonical_hash(document: Mapping[str, Any], *, omit: str = "content_hash") -> str:
    payload = {key: value for key, value in document.items() if key != omit}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _validate_parent_manifest(parent: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if parent.get("schema_version") != EXPECTED_PARENT_SCHEMA:
        raise Earnings22AuditError("parent manifest schema mismatch")
    if parent.get("source_commit") != EXPECTED_SOURCE_COMMIT:
        raise Earnings22AuditError("parent source commit mismatch")
    if parent.get("content_hash") != EXPECTED_PARENT_CONTENT_HASH:
        raise Earnings22AuditError("parent content hash mismatch")
    if _canonical_hash(parent) != EXPECTED_PARENT_CONTENT_HASH:
        raise Earnings22AuditError("parent manifest canonical hash mismatch")
    rows = parent.get("inputs")
    if not isinstance(rows, list) or len(rows) != 125:
        raise Earnings22AuditError("parent manifest must contain exactly 125 inputs")
    splits = Counter(row.get("split") for row in rows if isinstance(row, Mapping))
    if splits != {"discovery": 80, "reserve": RESERVE_SIZE}:
        raise Earnings22AuditError("parent split counts mismatch")
    return rows


def _safe_path(root: Path, relative: str) -> Path:
    expected_prefix = "transcripts/force_aligned_nlp_references/"
    if not relative.startswith(expected_prefix) or not relative.endswith(".aligned.nlp"):
        raise Earnings22AuditError("reserve path is outside the force-aligned reference layer")
    resolved_root = root.resolve()
    resolved = (root / Path(relative)).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise Earnings22AuditError("reserve path escapes Earnings-22 root")
    return resolved


def build_reserve_manifest(parent: Mapping[str, Any], root: Path) -> dict[str, Any]:
    """Verify and freeze reserve bytes without opening discovery files."""

    rows = _validate_parent_manifest(parent)
    reserve_rows = []
    seen_ids: set[str] = set()
    for row in rows:
        if row["split"] != "reserve":
            continue
        file_id = row.get("file_id")
        relative = row.get("path")
        expected_hash = row.get("sha256")
        expected_bytes = row.get("bytes")
        if not isinstance(file_id, str) or not isinstance(relative, str):
            raise Earnings22AuditError("malformed reserve manifest row")
        if file_id in seen_ids:
            raise Earnings22AuditError("duplicate reserve file id")
        seen_ids.add(file_id)
        path = _safe_path(root, relative)
        if not path.is_file():
            raise Earnings22AuditError(f"missing reserve file: {file_id}")
        if path.stat().st_size != expected_bytes or sha256_file(path) != expected_hash:
            raise Earnings22AuditError(f"reserve byte identity mismatch: {file_id}")
        reserve_rows.append(
            {
                "file_id": file_id,
                "path": relative,
                "bytes": expected_bytes,
                "sha256": expected_hash,
            }
        )
    if len(reserve_rows) != RESERVE_SIZE:
        raise Earnings22AuditError("reserve roster must contain exactly 45 files")
    payload: dict[str, Any] = {
        "schema_version": "e4-xdomain-supply-v3-reserve-input-v1",
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "parent_manifest_content_hash": EXPECTED_PARENT_CONTENT_HASH,
        "allowed_classes": sorted(ALLOWED_CLASSES),
        "inputs": reserve_rows,
    }
    payload["content_hash"] = _canonical_hash(payload)
    return payload


def assert_reserve_manifest_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    if dict(expected) != dict(actual):
        raise Earnings22AuditError("reserve input manifest does not match frozen manifest")


def reserve_inputs(manifest: Mapping[str, Any], root: Path) -> tuple[ReserveInput, ...]:
    if manifest.get("schema_version") != "e4-xdomain-supply-v3-reserve-input-v1":
        raise Earnings22AuditError("reserve manifest schema mismatch")
    if manifest.get("allowed_classes") != sorted(ALLOWED_CLASSES):
        raise Earnings22AuditError("reserve manifest class mismatch")
    if manifest.get("content_hash") != _canonical_hash(manifest):
        raise Earnings22AuditError("reserve manifest canonical hash mismatch")
    rows = manifest.get("inputs")
    if not isinstance(rows, list) or len(rows) != RESERVE_SIZE:
        raise Earnings22AuditError("reserve manifest must contain exactly 45 inputs")
    output = []
    for row in rows:
        if "split" in row or set(row) != {"file_id", "path", "bytes", "sha256"}:
            raise Earnings22AuditError("reserve-only row schema drift")
        output.append(ReserveInput(row["file_id"], _safe_path(root, row["path"])))
    return tuple(output)


def analyse_narrow_mentions(mentions: Sequence[EntityMention]) -> NarrowMeetingCounts:
    units: dict[int, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    admitted_mentions = excluded_unaligned = 0
    for mention in mentions:
        if mention.entity_class not in ALLOWED_CLASSES:
            continue
        admitted_mentions += 1
        if mention.timestamp is None:
            excluded_unaligned += 1
            continue
        slice_index = int(mention.timestamp // SLICE_SECONDS)
        units[slice_index][mention.speaker][mention.surface].add(mention.entity_class)

    seen: dict[str, set[str]] = defaultdict(set)
    exclusive = Counter()
    class_candidates = Counter()
    class_exclusive = Counter()
    candidate_units = same = shared = global_only = 0
    for slice_index in sorted(units):
        current_slice = units[slice_index]
        for speaker in sorted(current_slice):
            for surface, classes in current_slice[speaker].items():
                candidate_units += 1
                class_candidates.update(classes)
                prior = seen[surface]
                prior_same = speaker in prior
                prior_other = bool(prior - {speaker})
                if prior_same:
                    same += 1
                    if prior_other:
                        shared += 1
                    else:
                        exclusive[surface] += 1
                        class_exclusive.update(classes)
                elif prior_other:
                    global_only += 1
        for speaker, surfaces in current_slice.items():
            for surface in surfaces:
                seen[surface].add(speaker)

    return NarrowMeetingCounts(
        candidate_units=candidate_units,
        admitted_mentions=admitted_mentions,
        excluded_unaligned_mentions=excluded_unaligned,
        same_speaker_carry=same,
        shared_carry=shared,
        global_only_carry=global_only,
        exclusive_by_surface=dict(exclusive),
        candidate_units_by_class=dict(class_candidates),
        exclusive_units_by_class=dict(class_exclusive),
    )


def _percentile(values: Sequence[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def summarise_reserve(meetings: Sequence[NarrowMeetingCounts]) -> dict[str, Any]:
    if len(meetings) != RESERVE_SIZE:
        raise Earnings22AuditError("reserve analysis must contain exactly 45 meetings")
    surfaces: Counter[str] = Counter()
    class_candidates: Counter[str] = Counter()
    class_exclusive: Counter[str] = Counter()
    for meeting in meetings:
        surfaces.update(meeting.exclusive_by_surface)
        class_candidates.update(meeting.candidate_units_by_class)
        class_exclusive.update(meeting.exclusive_units_by_class)
    exclusive = sum(surfaces.values())
    distribution = [meeting.exclusive_carry for meeting in meetings]
    max_share = max(surfaces.values(), default=0) / exclusive if exclusive else 0.0
    report: dict[str, Any] = {
        "meetings": len(meetings),
        "eligible_meetings": sum(meeting.eligible for meeting in meetings),
        "admitted_mentions": sum(meeting.admitted_mentions for meeting in meetings),
        "excluded_unaligned_mentions": sum(meeting.excluded_unaligned_mentions for meeting in meetings),
        "candidate_units": sum(meeting.candidate_units for meeting in meetings),
        "same_speaker_carry": sum(meeting.same_speaker_carry for meeting in meetings),
        "shared_carry": sum(meeting.shared_carry for meeting in meetings),
        "global_only_carry": sum(meeting.global_only_carry for meeting in meetings),
        "speaker_exclusive_carry": exclusive,
        "exclusive_per_meeting": {
            "min": min(distribution, default=0),
            "p25": _percentile(distribution, 0.25),
            "median": _percentile(distribution, 0.50),
            "p75": _percentile(distribution, 0.75),
            "max": max(distribution, default=0),
        },
        "max_single_surface_share": max_share,
        "candidate_units_by_class": dict(sorted(class_candidates.items())),
        "exclusive_units_by_class": dict(sorted(class_exclusive.items())),
    }
    gates = {
        "eligible_meetings": report["eligible_meetings"] >= MIN_ELIGIBLE_MEETINGS,
        "exclusive_carry": report["speaker_exclusive_carry"] >= MIN_EXCLUSIVE_CARRY,
        "surface_concentration": max_share <= MAX_SURFACE_SHARE,
    }
    report["gates"] = gates
    report["passes"] = all(gates.values())
    return report


def build_verdict(inputs: Sequence[ReserveInput], manifest: Mapping[str, Any]) -> dict[str, Any]:
    if len(inputs) != RESERVE_SIZE:
        raise Earnings22AuditError("reader accepts exactly 45 reserve inputs")
    meetings = [analyse_narrow_mentions(load_entity_mentions(item.path)) for item in inputs]
    reserve = summarise_reserve(meetings)
    return {
        "schema_version": "e4-xdomain-supply-v3-verdict-v1",
        "analysis_class": "holdout-zero-model-narrow-technical-supply",
        "input_manifest_hash": manifest["content_hash"],
        "allowed_classes": sorted(ALLOWED_CLASSES),
        "reserve_meetings": RESERVE_SIZE,
        "discovery_files_read": 0,
        "pseudo_slice_seconds": SLICE_SECONDS,
        "thresholds": {
            "min_eligible_meetings": MIN_ELIGIBLE_MEETINGS,
            "min_exclusive_carry": MIN_EXCLUSIVE_CARRY,
            "max_single_surface_share": MAX_SURFACE_SHARE,
        },
        "reserve": reserve,
        "decision": (
            "EARNINGS22-NARROW-SUPPLY-FEASIBLE"
            if reserve["passes"]
            else "INSUFFICIENT-EARNINGS22-NARROW-SUPPLY"
        ),
        "model_calls": 0,
        "effect_identified": False,
        "audio_ready": False,
        "limitations": [
            "Abbreviation and alphanumeric tags are narrow technical proxies, not semantic entity labels.",
            "Fixed timestamp bins approximate, but do not reproduce, production diarizer-aware slices.",
            "Supply feasibility does not estimate transcription benefit or false-hint safety.",
            "Audio licensing and acquisition remain unresolved.",
        ],
    }


def render_report(verdict: Mapping[str, Any]) -> str:
    value = verdict["reserve"]
    return "\n".join(
        [
            f"decision: {verdict['decision']}",
            "model_calls: 0",
            "effect_identified: false",
            "audio_ready: false",
            f"reserve_meetings: {value['meetings']}",
            "discovery_files_read: 0",
            f"eligible_meetings: {value['eligible_meetings']}",
            f"speaker_exclusive_carry: {value['speaker_exclusive_carry']}",
            f"max_single_surface_share: {value['max_single_surface_share']:.4f}",
            f"excluded_unaligned_mentions: {value['excluded_unaligned_mentions']}",
            "",
            "This audit measures narrow holdout supply only; it does not identify model effect.",
            "",
        ]
    )


__all__ = [
    "ALLOWED_CLASSES", "EXPECTED_PARENT_CONTENT_HASH", "MAX_SURFACE_SHARE",
    "MIN_ELIGIBLE_MEETINGS", "MIN_EXCLUSIVE_CARRY", "NarrowMeetingCounts", "ReserveInput",
    "analyse_narrow_mentions", "assert_reserve_manifest_matches", "build_reserve_manifest",
    "build_verdict", "render_report", "reserve_inputs", "summarise_reserve",
]
