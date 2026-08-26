"""Append-only persistence and invariant checks for material dispatch traces."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping


TRACE_SCHEMA = "material-new-surface-dispatch-trace-row-v1"
REQUIRED_TOP_LEVEL = frozenset({
    "schema", "experiment_id", "trace_run_id", "recorded_utc", "split",
    "item_id", "meeting_id", "turn_id", "audio_role", "audio_sha256",
    "audio_duration_ms", "pass0", "runtime_context", "retrieval", "decision",
    "deranged_control", "artifact_bindings",
})
FORBIDDEN_REFERENCE_FIELDS = frozenset({"reference_text", "answer_text", "gold_material_match", "downstream_wer"})


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def row_content_sha256(row: Mapping[str, Any]) -> str:
    copy = json.loads(canonical_json(row))
    copy["artifact_bindings"]["row_sha256"] = ""
    return sha256_text(canonical_json(copy))


def candidate_keyset_sha256(candidates: list[Mapping[str, Any]]) -> str:
    """Bind candidate identities, key text, and prompt values before scoring."""

    frozen = [
        {
            "candidate_id": candidate["candidate_id"],
            "meeting_id": candidate["meeting_id"],
            "key_text": candidate["key_text"],
            "key_sha256": candidate["key_sha256"],
            "value": candidate["value"],
        }
        for candidate in candidates
    ]
    return sha256_text(canonical_json(frozen))


def _validate_candidates(candidates: list[Mapping[str, Any]], meeting_id: str, label: str) -> list[str]:
    errors: list[str] = []
    for rank, candidate in enumerate(candidates, 1):
        if int(candidate.get("rank", -1)) != rank:
            errors.append(f"{label} candidate rank mismatch")
        if str(candidate.get("meeting_id")) != meeting_id:
            errors.append(f"{label} candidate meeting mismatch")
        if sha256_text(str(candidate.get("key_text", ""))) != candidate.get("key_sha256"):
            errors.append(f"{label} candidate key hash mismatch")
        value = candidate.get("value", {})
        if sha256_text(str(value.get("prompt_text", ""))) != value.get("prompt_sha256"):
            errors.append(f"{label} candidate prompt hash mismatch")
    return errors


def _forbidden_paths(value: object, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_REFERENCE_FIELDS:
                found.append(path)
            found.extend(_forbidden_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{prefix}[{index}]"))
    return found


def validate_trace_row(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL.difference(row)
    if missing:
        errors.append(f"missing top-level fields: {','.join(sorted(missing))}")
        return errors
    if row.get("schema") != TRACE_SCHEMA:
        errors.append("trace schema mismatch")
    forbidden = _forbidden_paths(row)
    if forbidden:
        errors.append(f"forbidden reference fields: {','.join(forbidden)}")

    decision = row["decision"]
    candidates = row["retrieval"]["candidates"]
    if len(candidates) < 2:
        errors.append("fewer than two retrieval candidates")
    else:
        ordered = sorted(candidates, key=lambda candidate: (-float(candidate["score"]), str(candidate["candidate_id"])))
        if candidates != ordered:
            errors.append("candidates are not in deterministic score order")
        top1, top2 = ordered[:2]
        if decision.get("top1_candidate_id") != top1.get("candidate_id"):
            errors.append("top1 candidate mismatch")
        if decision.get("top2_candidate_id") != top2.get("candidate_id"):
            errors.append("top2 candidate mismatch")
        if not math.isclose(float(decision.get("top1_score", float("nan"))), float(top1["score"]), rel_tol=1e-9, abs_tol=1e-9):
            errors.append("top1 score mismatch")
        if not math.isclose(float(decision.get("top2_score", float("nan"))), float(top2["score"]), rel_tol=1e-9, abs_tol=1e-9):
            errors.append("top2 score mismatch")
        if decision.get("selected_value") != top1.get("value"):
            errors.append("selected correct value mismatch")
        gap = float(top1["score"]) - float(top2["score"])
        if not math.isclose(float(decision.get("selector_gap", float("nan"))), gap, rel_tol=1e-9, abs_tol=1e-9):
            errors.append("selector gap mismatch")
        if bool(decision.get("dispatch")) != (gap >= float(decision["threshold"])):
            errors.append("dispatch decision mismatch")
        errors.extend(_validate_candidates(candidates, str(row["meeting_id"]), "correct"))
        if candidate_keyset_sha256(candidates) != row["retrieval"].get("keyset_sha256"):
            errors.append("correct keyset hash mismatch")
    if row["deranged_control"].get("meeting_id") == row.get("meeting_id"):
        errors.append("deranged control uses the current meeting")
    deranged = row["deranged_control"]
    deranged_candidates = deranged.get("candidates", [])
    if len(deranged_candidates) < 2:
        errors.append("fewer than two deranged candidates")
    else:
        deranged_ordered = sorted(
            deranged_candidates,
            key=lambda candidate: (-float(candidate["score"]), str(candidate["candidate_id"])),
        )
        if deranged_candidates != deranged_ordered:
            errors.append("deranged candidates are not in deterministic score order")
        deranged_top1 = deranged_ordered[0]
        if deranged.get("candidate_id") != deranged_top1.get("candidate_id"):
            errors.append("deranged top1 candidate mismatch")
        if not math.isclose(float(deranged.get("score", float("nan"))), float(deranged_top1["score"]), rel_tol=1e-9, abs_tol=1e-9):
            errors.append("deranged top1 score mismatch")
        if deranged.get("selected_value") != deranged_top1.get("value"):
            errors.append("selected deranged value mismatch")
        errors.extend(_validate_candidates(deranged_candidates, str(deranged["meeting_id"]), "deranged"))
        if candidate_keyset_sha256(deranged_candidates) != deranged.get("keyset_sha256"):
            errors.append("deranged keyset hash mismatch")

    hash_pairs = (
        (row["pass0"]["transcript_text"], row["pass0"]["transcript_sha256"], "Pass0 transcript"),
        (row["retrieval"]["query_text"], row["retrieval"]["query_sha256"], "query"),
        (canonical_json({
            "predicted_speaker_id": row["runtime_context"]["predicted_speaker_id"],
            "prior_context_text": row["runtime_context"]["prior_context_text"],
            "prior_topic_keywords": row["runtime_context"]["prior_topic_keywords"],
        }), row["runtime_context"]["context_sha256"], "runtime context"),
    )
    for value, expected, label in hash_pairs:
        if sha256_text(value) != expected:
            errors.append(f"{label} hash mismatch")
    if row_content_sha256(row) != row["artifact_bindings"]["row_sha256"]:
        errors.append("row content hash mismatch")
    return errors


def append_trace_row(path: Path, row: Mapping[str, Any]) -> None:
    """Validate and durably append one trace row without rewriting prior rows."""

    errors = validate_trace_row(row)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = (str(row["item_id"]), str(row["turn_id"]), str(row["audio_role"]))
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            existing = json.loads(line)
            existing_identity = (
                str(existing.get("item_id")), str(existing.get("turn_id")), str(existing.get("audio_role"))
            )
            if existing_identity == identity:
                raise ValueError(f"duplicate trace identity: {identity}")
            if existing.get("trace_run_id") != row.get("trace_run_id"):
                raise ValueError("trace_run_id differs from existing append-only trace")
    payload = canonical_json(row) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


__all__ = [
    "TRACE_SCHEMA",
    "append_trace_row",
    "candidate_keyset_sha256",
    "canonical_json",
    "row_content_sha256",
    "sha256_text",
    "validate_trace_row",
]
