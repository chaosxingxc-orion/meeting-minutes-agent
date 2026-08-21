"""Zero-model Earnings-22 professional-entity carry supply audit."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EXPECTED_SOURCE_COMMIT = "c05ab6fd8b4b627d123c922a22a39e993dd37635"
SPLIT_SALT = "e4-xdomain-supply-v2-2026-08-21"
DISCOVERY_SIZE = 80
RESERVE_SIZE = 45
SLICE_SECONDS = 90.0

MIN_MEETINGS = 20
MIN_ELIGIBLE_MEETINGS = 20
MIN_EXCLUSIVE_CARRY = 100
MAX_SURFACE_SHARE = 0.20

EXPECTED_HEADER = (
    "token", "speaker", "ts", "endTs", "punctuation", "prepunctuation",
    "case", "tags", "oldTs", "oldEndTs", "ali_comment",
)
EXPECTED_HEADER_WITH_WER_TAGS = (
    "token", "speaker", "ts", "endTs", "punctuation", "prepunctuation",
    "case", "tags", "wer_tags", "oldTs", "oldEndTs", "ali_comment",
)
EXCLUDED_CLASSES = frozenset(
    {"DATE", "TIME", "YEAR", "MONEY", "PERCENT", "CARDINAL", "ORDINAL", "QUANTITY", "DURATION", "MEASURE"}
)


class Earnings22AuditError(ValueError):
    """Fail-closed input, schema, split, or governance refusal."""


@dataclass(frozen=True)
class Earnings22Input:
    file_id: str
    path: Path
    split: str


@dataclass(frozen=True)
class EntityMention:
    speaker: str
    timestamp: float | None
    surface: str
    entity_class: str


@dataclass(frozen=True)
class MeetingCounts:
    candidate_units: int
    excluded_unaligned_mentions: int
    same_speaker_carry: int
    shared_carry: int
    global_only_carry: int
    exclusive_by_surface: Mapping[str, int]
    class_candidate_units: Mapping[str, int]
    class_exclusive_units: Mapping[str, int]

    @property
    def exclusive_carry(self) -> int:
        return sum(self.exclusive_by_surface.values())

    @property
    def eligible(self) -> bool:
        return self.exclusive_carry >= 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_id(path: Path) -> str:
    suffix = ".aligned.nlp"
    if not path.name.endswith(suffix):
        raise Earnings22AuditError(f"unexpected aligned filename: {path.name}")
    value = path.name[: -len(suffix)]
    if not value:
        raise Earnings22AuditError("empty file id")
    return value


def deterministic_split(file_ids: Iterable[str]) -> dict[str, str]:
    values = list(file_ids)
    if len(values) != DISCOVERY_SIZE + RESERVE_SIZE or len(set(values)) != len(values):
        raise Earnings22AuditError("expected exactly 125 unique Earnings-22 file ids")
    ranked = sorted(
        values,
        key=lambda value: (
            hashlib.sha256(f"{SPLIT_SALT}\0{value}".encode("utf-8")).hexdigest(),
            value,
        ),
    )
    return {value: ("discovery" if index < DISCOVERY_SIZE else "reserve") for index, value in enumerate(ranked)}


def select_inputs(root: Path) -> tuple[Earnings22Input, ...]:
    aligned = root / "transcripts" / "force_aligned_nlp_references"
    paths = sorted(aligned.glob("*.aligned.nlp"))
    ids = [_file_id(path) for path in paths]
    split = deterministic_split(ids)
    if list(root.rglob("*.mp3")):
        raise Earnings22AuditError("audio files are prohibited in this text-only audit root")
    if not (root / "LICENSE.md").is_file() or not (root / "README.md").is_file():
        raise Earnings22AuditError("missing Earnings-22 license or README")
    return tuple(Earnings22Input(file_id, path, split[file_id]) for file_id, path in zip(ids, paths))


def build_input_manifest(inputs: Sequence[Earnings22Input], root: Path) -> dict[str, Any]:
    rows = []
    for item in inputs:
        try:
            relative = item.path.relative_to(root).as_posix()
        except ValueError as exc:
            raise Earnings22AuditError("input path escapes Earnings-22 root") from exc
        rows.append(
            {
                "file_id": item.file_id,
                "split": item.split,
                "path": relative,
                "sha256": sha256_file(item.path),
                "bytes": item.path.stat().st_size,
            }
        )
    if Counter(row["split"] for row in rows) != {"discovery": DISCOVERY_SIZE, "reserve": RESERVE_SIZE}:
        raise Earnings22AuditError("split count mismatch")
    payload: dict[str, Any] = {
        "schema_version": "e4-xdomain-supply-v2-input-v1",
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "split_salt": SPLIT_SALT,
        "license_sha256": sha256_file(root / "LICENSE.md"),
        "readme_sha256": sha256_file(root / "README.md"),
        "inputs": rows,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["content_hash"] = hashlib.sha256(canonical).hexdigest()
    return payload


def assert_manifest_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    if dict(expected) != dict(actual):
        raise Earnings22AuditError("selected input manifest does not match frozen manifest")


def _parse_tags(raw: str, *, line: int) -> tuple[tuple[str, str], ...]:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError) as exc:
        raise Earnings22AuditError(f"line {line}: malformed tags") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise Earnings22AuditError(f"line {line}: tags must be a string list")
    output = []
    for item in value:
        entity_id, separator, entity_class = item.partition(":")
        if not separator or not entity_id or not entity_class or entity_class != entity_class.upper():
            raise Earnings22AuditError(f"line {line}: malformed entity tag")
        output.append((entity_id, entity_class))
    return tuple(output)


def _normalise_surface(tokens: Sequence[str]) -> str:
    value = " ".join(tokens)
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def load_entity_mentions(path: Path) -> tuple[EntityMention, ...]:
    mentions: list[EntityMention] = []
    active: dict[str, dict[str, Any]] = {}
    closed_ids: set[str] = set()

    def close(entity_id: str) -> None:
        value = active.pop(entity_id)
        surface = _normalise_surface(value["tokens"])
        if not surface:
            raise Earnings22AuditError(f"{path.name}: empty normalized entity")
        timestamps = value["timestamps"]
        mentions.append(
            EntityMention(
                speaker=value["speaker"],
                timestamp=min(timestamps) if timestamps else None,
                surface=surface,
                entity_class=value["class"],
            )
        )
        closed_ids.add(entity_id)

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="|")
        try:
            header = tuple(next(reader))
        except StopIteration as exc:
            raise Earnings22AuditError(f"{path.name}: empty file") from exc
        if header not in {EXPECTED_HEADER, EXPECTED_HEADER_WITH_WER_TAGS}:
            raise Earnings22AuditError(f"{path.name}: header drift")
        columns = {name: index for index, name in enumerate(header)}
        for line, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise Earnings22AuditError(f"{path.name}:{line}: column count drift")
            token = row[columns["token"]]
            speaker = row[columns["speaker"]]
            raw_ts = row[columns["ts"]]
            raw_tags = row[columns["tags"]]
            if not token or not speaker:
                raise Earnings22AuditError(f"{path.name}:{line}: empty token or speaker")
            timestamp: float | None = None
            if raw_ts:
                try:
                    timestamp = float(raw_ts)
                except ValueError as exc:
                    raise Earnings22AuditError(f"{path.name}:{line}: invalid timestamp") from exc
                if not math.isfinite(timestamp) or timestamp < 0:
                    raise Earnings22AuditError(f"{path.name}:{line}: invalid timestamp")
            tags = _parse_tags(raw_tags, line=line)
            current_ids = {entity_id for entity_id, _ in tags}
            if len(current_ids) != len(tags):
                raise Earnings22AuditError(f"{path.name}:{line}: duplicate entity id in tags")
            for entity_id in tuple(active):
                if entity_id not in current_ids:
                    close(entity_id)
            for entity_id, entity_class in tags:
                if entity_id in closed_ids:
                    raise Earnings22AuditError(f"{path.name}:{line}: non-contiguous entity id")
                current = active.setdefault(
                    entity_id, {"speaker": speaker, "class": entity_class, "tokens": [], "timestamps": []}
                )
                if current["speaker"] != speaker or current["class"] != entity_class:
                    raise Earnings22AuditError(f"{path.name}:{line}: entity id changes speaker or class")
                current["tokens"].append(token)
                if timestamp is not None:
                    current["timestamps"].append(timestamp)
    for entity_id in tuple(active):
        close(entity_id)
    return tuple(mentions)


def analyse_mentions(mentions: Sequence[EntityMention]) -> MeetingCounts:
    units: dict[int, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    excluded_unaligned = 0
    for mention in mentions:
        if mention.entity_class in EXCLUDED_CLASSES:
            continue
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
                for entity_class in classes:
                    class_candidates[entity_class] += 1
                prior = seen[surface]
                prior_same = speaker in prior
                prior_other = bool(prior - {speaker})
                if prior_same:
                    same += 1
                    if prior_other:
                        shared += 1
                    else:
                        exclusive[surface] += 1
                        for entity_class in classes:
                            class_exclusive[entity_class] += 1
                elif prior_other:
                    global_only += 1
        for speaker, surfaces in current_slice.items():
            for surface in surfaces:
                seen[surface].add(speaker)
    return MeetingCounts(
        candidate_units=candidate_units,
        excluded_unaligned_mentions=excluded_unaligned,
        same_speaker_carry=same,
        shared_carry=shared,
        global_only_carry=global_only,
        exclusive_by_surface=dict(exclusive),
        class_candidate_units=dict(class_candidates),
        class_exclusive_units=dict(class_exclusive),
    )


def _percentile(values: Sequence[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def build_verdict(inputs: Sequence[Earnings22Input], manifest: Mapping[str, Any]) -> dict[str, Any]:
    discovery = [item for item in inputs if item.split == "discovery"]
    if len(discovery) != DISCOVERY_SIZE:
        raise Earnings22AuditError("discovery roster must contain exactly 80 files")
    meetings = [analyse_mentions(load_entity_mentions(item.path)) for item in discovery]
    surfaces: Counter[str] = Counter()
    class_candidates: Counter[str] = Counter()
    class_exclusive: Counter[str] = Counter()
    for meeting in meetings:
        surfaces.update(meeting.exclusive_by_surface)
        class_candidates.update(meeting.class_candidate_units)
        class_exclusive.update(meeting.class_exclusive_units)
    exclusive = sum(surfaces.values())
    distribution = [meeting.exclusive_carry for meeting in meetings]
    max_share = max(surfaces.values(), default=0) / exclusive if exclusive else 0.0
    summary: dict[str, Any] = {
        "meetings": len(meetings),
        "candidate_units": sum(item.candidate_units for item in meetings),
        "excluded_unaligned_mentions": sum(item.excluded_unaligned_mentions for item in meetings),
        "same_speaker_carry": sum(item.same_speaker_carry for item in meetings),
        "shared_carry": sum(item.shared_carry for item in meetings),
        "global_only_carry": sum(item.global_only_carry for item in meetings),
        "speaker_exclusive_carry": exclusive,
        "eligible_meetings": sum(item.eligible for item in meetings),
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
        "meetings": summary["meetings"] >= MIN_MEETINGS,
        "eligible_meetings": summary["eligible_meetings"] >= MIN_ELIGIBLE_MEETINGS,
        "exclusive_carry": summary["speaker_exclusive_carry"] >= MIN_EXCLUSIVE_CARRY,
        "surface_concentration": max_share <= MAX_SURFACE_SHARE,
    }
    summary["gates"] = gates
    summary["passes"] = all(gates.values())
    return {
        "schema_version": "e4-xdomain-supply-v2-verdict-v1",
        "analysis_class": "exploratory-zero-model-upstream-entity-supply",
        "input_manifest_hash": manifest["content_hash"],
        "split": {"discovery": DISCOVERY_SIZE, "reserve_unread": RESERVE_SIZE},
        "pseudo_slice_seconds": SLICE_SECONDS,
        "thresholds": {
            "min_meetings": MIN_MEETINGS,
            "min_eligible_meetings": MIN_ELIGIBLE_MEETINGS,
            "min_exclusive_carry": MIN_EXCLUSIVE_CARRY,
            "max_single_surface_share": MAX_SURFACE_SHARE,
        },
        "discovery": summary,
        "decision": "EARNINGS22-SUPPLY-FEASIBLE" if summary["passes"] else "INSUFFICIENT-EARNINGS22-SUPPLY",
        "model_calls": 0,
        "effect_identified": False,
        "audio_ready": False,
        "limitations": [
            "Upstream entity annotations are professional-entity proxies, not transcription errors.",
            "Fixed timestamp bins approximate, but do not reproduce, the production diarizer-aware slicer.",
            "Supply feasibility does not estimate transcription benefit or false-hint safety.",
            "Audio licensing and acquisition remain unresolved.",
        ],
    }


def render_report(verdict: Mapping[str, Any]) -> str:
    value = verdict["discovery"]
    lines = [
        f"decision: {verdict['decision']}",
        "model_calls: 0",
        "effect_identified: false",
        "audio_ready: false",
        f"discovery_meetings: {value['meetings']}",
        f"reserve_unread: {verdict['split']['reserve_unread']}",
        f"eligible_meetings: {value['eligible_meetings']}",
        f"speaker_exclusive_carry: {value['speaker_exclusive_carry']}",
        f"max_single_surface_share: {value['max_single_surface_share']:.4f}",
        f"excluded_unaligned_mentions: {value['excluded_unaligned_mentions']}",
        "",
        "This audit measures upstream-labelled entity supply only; it does not identify model effect.",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "DISCOVERY_SIZE", "EXPECTED_SOURCE_COMMIT", "Earnings22AuditError", "Earnings22Input",
    "EntityMention", "MeetingCounts", "RESERVE_SIZE", "SPLIT_SALT", "analyse_mentions",
    "assert_manifest_matches", "build_input_manifest", "build_verdict", "deterministic_split",
    "load_entity_mentions", "render_report", "select_inputs", "sha256_file",
]
