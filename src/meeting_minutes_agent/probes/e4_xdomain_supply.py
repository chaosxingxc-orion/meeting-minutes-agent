"""Zero-model cross-domain lexical carry supply audit."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..corpora.roles import AmiRoleRegistry, MeetingRole

EXPECTED_QMSUM_COMMIT = "83d7768c1f2b4dfeb091385d3dc7e239b8e5bb7e"
EXPECTED_ROLE_REGISTRY_SHA256 = "e21a297a31594204bfc96670aa507534340f329688b6baa03db1d65141e8200f"
DOMAINS = ("Product", "Academic")

MIN_MEETINGS = 20
MIN_ELIGIBLE_MEETINGS = 20
MIN_EXCLUSIVE_CARRY = 100
MIN_STRICT_EXCLUSIVE_CARRY = 10
MAX_SURFACE_SHARE = 0.20

_LEXEME = re.compile(r"\{[^}]*\}|[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|[.!?]")
_STOP_SURFACES = frozenset(
    {
        "and", "but", "good", "hello", "here", "hmm", "how", "maybe", "mm", "no",
        "now", "okay", "right", "so", "sorry", "sure", "thanks", "that", "the", "then",
        "there", "they", "this", "um", "uh", "well", "what", "when", "where", "who",
        "why", "yeah", "yes", "you",
    }
)


class SupplyAuditError(ValueError):
    """Fail-closed input, schema, or governance refusal."""


@dataclass(frozen=True)
class CorpusInput:
    domain: str
    meeting_id: str
    transcript_path: Path
    audio_path: Path


@dataclass(frozen=True)
class Segment:
    speaker: str
    content: str


@dataclass(frozen=True)
class MeetingCounts:
    meeting_id: str
    segments: int
    candidate_units: int
    strict_candidate_units: int
    same_speaker_carry: int
    shared_carry: int
    global_only_carry: int
    exclusive_by_surface: Mapping[str, int]
    strict_exclusive_carry: int

    @property
    def exclusive_carry(self) -> int:
        return sum(self.exclusive_by_surface.values())

    @property
    def eligible(self) -> bool:
        return self.exclusive_carry >= 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise_surface(token: str) -> str:
    value = token.replace("’", "'")
    if value.lower().endswith("'s"):
        value = value[:-2]
    return value.lower()


def extract_candidates(content: str) -> dict[str, str]:
    """Return segment-deduplicated ``surface -> frozen proxy kind``."""

    candidates: dict[str, str] = {}
    sentence_start = True
    for match in _LEXEME.finditer(content):
        token = match.group(0)
        if token.startswith("{"):
            continue
        if token in ".!?":
            sentence_start = True
            continue
        base = token[:-2] if token.lower().endswith("'s") else token
        surface = _normalise_surface(token)
        letters = "".join(character for character in base if character.isalpha())
        strict = (
            len(letters) >= 2 and letters.isupper()
        ) or (any(character.isalpha() for character in base) and any(character.isdigit() for character in base))
        name_like = len(letters) >= 3 and base.istitle() and not sentence_start
        if surface not in _STOP_SURFACES and (strict or name_like):
            kind = "strict_technical" if strict else "name_like"
            if candidates.get(surface) != "strict_technical":
                candidates[surface] = kind
        sentence_start = False
    return candidates


def analyse_meeting(meeting_id: str, segments: Sequence[Segment]) -> MeetingCounts:
    seen: dict[str, set[str]] = defaultdict(set)
    exclusive = Counter()
    candidate_units = strict_units = same = shared = global_only = strict_exclusive = 0
    for segment in segments:
        if not segment.speaker.strip():
            raise SupplyAuditError(f"{meeting_id}: empty speaker")
        current = extract_candidates(segment.content)
        candidate_units += len(current)
        strict_units += sum(kind == "strict_technical" for kind in current.values())
        for surface, kind in current.items():
            prior = seen[surface]
            prior_same = segment.speaker in prior
            prior_other = bool(prior - {segment.speaker})
            if prior_same:
                same += 1
                if prior_other:
                    shared += 1
                else:
                    exclusive[surface] += 1
                    strict_exclusive += kind == "strict_technical"
            elif prior_other:
                global_only += 1
        for surface in current:
            seen[surface].add(segment.speaker)
    return MeetingCounts(
        meeting_id=meeting_id,
        segments=len(segments),
        candidate_units=candidate_units,
        strict_candidate_units=strict_units,
        same_speaker_carry=same,
        shared_carry=shared,
        global_only_carry=global_only,
        exclusive_by_surface=dict(exclusive),
        strict_exclusive_carry=strict_exclusive,
    )


def load_segments(path: Path) -> tuple[Segment, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "meeting_transcripts" not in raw:
        raise SupplyAuditError(f"{path.name}: missing meeting_transcripts")
    transcripts = raw["meeting_transcripts"]
    if not isinstance(transcripts, list) or not transcripts:
        raise SupplyAuditError(f"{path.name}: meeting_transcripts must be a non-empty list")
    output: list[Segment] = []
    for index, item in enumerate(transcripts):
        if not isinstance(item, dict) or set(item) != {"speaker", "content"}:
            raise SupplyAuditError(f"{path.name}: transcript {index} schema drift")
        if not isinstance(item["speaker"], str) or not isinstance(item["content"], str):
            raise SupplyAuditError(f"{path.name}: transcript {index} fields must be strings")
        output.append(Segment(item["speaker"], item["content"]))
    return tuple(output)


def select_inputs(
    qmsum_root: Path,
    ami_root: Path,
    icsi_root: Path,
    registry: AmiRoleRegistry,
) -> tuple[CorpusInput, ...]:
    selected: list[CorpusInput] = []
    product_dir = qmsum_root / "data" / "Product" / "train"
    academic_dir = qmsum_root / "data" / "Academic" / "train"
    for path in sorted(product_dir.glob("*.json")):
        meeting_id = path.stem
        role = registry.role_of(meeting_id)
        if role is not MeetingRole.GLOSSARY_DISCOVERY:
            continue
        registry.assert_exposable(meeting_id, for_role=MeetingRole.GLOSSARY_DISCOVERY)
        audio = ami_root / "amicorpus" / meeting_id / "audio" / f"{meeting_id}.Mix-Headset.wav"
        if not audio.is_file():
            raise SupplyAuditError(f"missing Product audio for {meeting_id}")
        selected.append(CorpusInput("Product", meeting_id, path, audio))
    for path in sorted(academic_dir.glob("*.json")):
        meeting_id = path.stem
        audio = icsi_root / "audio" / f"{meeting_id}.interaction.wav"
        if not audio.is_file():
            raise SupplyAuditError(f"missing Academic audio for {meeting_id}")
        selected.append(CorpusInput("Academic", meeting_id, path, audio))
    for domain in DOMAINS:
        if not any(item.domain == domain for item in selected):
            raise SupplyAuditError(f"empty selected roster for {domain}")
    return tuple(selected)


def build_input_manifest(inputs: Sequence[CorpusInput], qmsum_root: Path) -> dict[str, Any]:
    rows = []
    for item in inputs:
        try:
            relative = item.transcript_path.relative_to(qmsum_root).as_posix()
        except ValueError as exc:
            raise SupplyAuditError("transcript path escapes QMSum root") from exc
        if "/train/" not in f"/{relative}":
            raise SupplyAuditError(f"non-train input prohibited: {relative}")
        rows.append(
            {
                "domain": item.domain,
                "meeting_id": item.meeting_id,
                "transcript": relative,
                "transcript_sha256": sha256_file(item.transcript_path),
                "audio_bytes": item.audio_path.stat().st_size,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "e4-xdomain-supply-input-v1",
        "qmsum_commit": EXPECTED_QMSUM_COMMIT,
        "role_registry_sha256": EXPECTED_ROLE_REGISTRY_SHA256,
        "inputs": rows,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["content_hash"] = hashlib.sha256(canonical).hexdigest()
    return payload


def assert_manifest_matches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    if dict(expected) != dict(actual):
        raise SupplyAuditError("selected input manifest does not match frozen manifest")


def _percentile(values: Sequence[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def summarise_domain(domain: str, meetings: Sequence[MeetingCounts]) -> dict[str, Any]:
    surface_counts: Counter[str] = Counter()
    for meeting in meetings:
        surface_counts.update(meeting.exclusive_by_surface)
    exclusive = sum(surface_counts.values())
    distribution = [meeting.exclusive_carry for meeting in meetings]
    max_surface_share = max(surface_counts.values(), default=0) / exclusive if exclusive else 0.0
    report: dict[str, Any] = {
        "domain": domain,
        "meetings": len(meetings),
        "segments": sum(item.segments for item in meetings),
        "candidate_units": sum(item.candidate_units for item in meetings),
        "strict_candidate_units": sum(item.strict_candidate_units for item in meetings),
        "same_speaker_carry": sum(item.same_speaker_carry for item in meetings),
        "shared_carry": sum(item.shared_carry for item in meetings),
        "global_only_carry": sum(item.global_only_carry for item in meetings),
        "speaker_exclusive_carry": exclusive,
        "strict_speaker_exclusive_carry": sum(item.strict_exclusive_carry for item in meetings),
        "eligible_meetings": sum(item.eligible for item in meetings),
        "exclusive_per_meeting": {
            "min": min(distribution, default=0),
            "p25": _percentile(distribution, 0.25),
            "median": _percentile(distribution, 0.50),
            "p75": _percentile(distribution, 0.75),
            "max": max(distribution, default=0),
        },
        "max_single_surface_share": max_surface_share,
    }
    gates = {
        "meetings": report["meetings"] >= MIN_MEETINGS,
        "eligible_meetings": report["eligible_meetings"] >= MIN_ELIGIBLE_MEETINGS,
        "exclusive_carry": report["speaker_exclusive_carry"] >= MIN_EXCLUSIVE_CARRY,
        "strict_exclusive_carry": report["strict_speaker_exclusive_carry"] >= MIN_STRICT_EXCLUSIVE_CARRY,
        "surface_concentration": max_surface_share <= MAX_SURFACE_SHARE,
    }
    report["gates"] = gates
    report["passes"] = all(gates.values())
    return report


def choose_decision(domains: Mapping[str, Mapping[str, Any]]) -> str:
    passes = [bool(domains[name]["passes"]) for name in DOMAINS]
    if all(passes):
        return "XDOMAIN-SUPPLY-FEASIBLE"
    if any(passes):
        return "DOMAIN-LIMITED-SUPPLY"
    return "INSUFFICIENT-XDOMAIN-SUPPLY"


def build_verdict(inputs: Sequence[CorpusInput], manifest: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[MeetingCounts]] = {domain: [] for domain in DOMAINS}
    for item in inputs:
        grouped[item.domain].append(analyse_meeting(item.meeting_id, load_segments(item.transcript_path)))
    domains = {domain: summarise_domain(domain, grouped[domain]) for domain in DOMAINS}
    return {
        "schema_version": "e4-xdomain-supply-verdict-v1",
        "analysis_class": "exploratory-zero-model-lexical-proxy-supply",
        "input_manifest_hash": manifest["content_hash"],
        "thresholds": {
            "min_meetings": MIN_MEETINGS,
            "min_eligible_meetings": MIN_ELIGIBLE_MEETINGS,
            "min_exclusive_carry": MIN_EXCLUSIVE_CARRY,
            "min_strict_exclusive_carry": MIN_STRICT_EXCLUSIVE_CARRY,
            "max_single_surface_share": MAX_SURFACE_SHARE,
        },
        "domains": domains,
        "decision": choose_decision(domains),
        "model_calls": 0,
        "effect_identified": False,
        "limitations": [
            "Lexical capitalization/acronym proxies are not professional-entity annotations.",
            "QMSum transcript segments are speaker turns, not the frozen production audio chunks.",
            "Supply feasibility does not estimate transcription benefit or false-hint safety.",
        ],
    }


def render_report(verdict: Mapping[str, Any]) -> str:
    lines = [
        f"decision: {verdict['decision']}",
        "model_calls: 0",
        "effect_identified: false",
        "",
        "domain\tmeetings\teligible\texclusive\tstrict_exclusive\tmax_surface_share\tpasses",
    ]
    for domain in DOMAINS:
        value = verdict["domains"][domain]
        lines.append(
            f"{domain}\t{value['meetings']}\t{value['eligible_meetings']}\t"
            f"{value['speaker_exclusive_carry']}\t{value['strict_speaker_exclusive_carry']}\t"
            f"{value['max_single_surface_share']:.4f}\t{str(value['passes']).lower()}"
        )
    lines.extend(["", "This audit measures lexical-proxy supply only; it does not identify model effect."])
    return "\n".join(lines) + "\n"


__all__ = [
    "CorpusInput", "DOMAINS", "EXPECTED_QMSUM_COMMIT", "EXPECTED_ROLE_REGISTRY_SHA256",
    "MeetingCounts", "Segment", "SupplyAuditError", "analyse_meeting", "assert_manifest_matches",
    "build_input_manifest", "build_verdict", "choose_decision", "extract_candidates", "load_segments",
    "render_report", "select_inputs", "sha256_file", "summarise_domain",
]
