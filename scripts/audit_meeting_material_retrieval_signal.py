#!/usr/bin/env python3
"""Zero-model audit of correct-vs-deranged official-material retrieval signal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.external_identity_retrieval import (  # noqa: E402
    contains_identity,
    identity_tokens,
)
from meeting_minutes_agent.state.material_retrieval import (  # noqa: E402
    MaterialBm25Index,
    retrieval_features,
    select_balanced_keys,
    summarize_signal,
    word_tokens,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_provenance(
    candidates: dict[str, object], material_pages: list[dict[str, object]]
) -> tuple[int, int]:
    pages = {
        (str(row["file_id"]), str(row["document_sha256"]), int(row["page"])): str(row["text"])
        for row in material_pages
    }
    checked = 0
    missing = 0
    for meeting in candidates["meetings"]:
        file_id = str(meeting["file_id"])
        document_sha256 = str(meeting["document_sha256"])
        for candidate in meeting["candidates"]:
            checked += 1
            page = pages.get((file_id, document_sha256, int(candidate["page"])), "")
            source = identity_tokens(str(candidate["source_span"]))
            page_tokens = identity_tokens(page)
            width = len(source)
            if not width or not any(
                page_tokens[index : index + width] == source
                for index in range(len(page_tokens) - width + 1)
            ):
                missing += 1
    return checked, missing


def audit(
    config: dict[str, object],
    candidates: dict[str, object],
    runtime: dict[str, object],
    response_dir: Path,
    material_pages: list[dict[str, object]],
) -> dict[str, object]:
    width = int(config["balanced_key_width"])
    keys = select_balanced_keys(
        candidates["meetings"], width=width, salt=str(config["selection_salt"])
    )
    bm25 = config["bm25"]
    index = MaterialBm25Index(keys, k1=float(bm25["k1"]), b=float(bm25["b"]))
    file_ids = sorted({key.file_id for key in keys})
    deranged = {
        file_id: file_ids[(position + 1) % len(file_ids)]
        for position, file_id in enumerate(file_ids)
    }
    keys_by_id = {file_id: [key for key in keys if key.file_id == file_id] for file_id in file_ids}
    meetings_by_id = {str(row["file_id"]): row for row in runtime["meetings"]}
    minimum_tokens = int(config["minimum_query_content_tokens"])
    all_rows: list[dict[str, object]] = []
    meeting_results = []
    examples = []
    excluded_exact = 0
    excluded_short = 0
    for file_id in file_ids:
        response_path = response_dir / f"{file_id}-responses.jsonl"
        expected_hash = str(config["pass0_sha256"][file_id])
        if sha256_file(response_path) != expected_hash:
            raise ValueError(f"Pass0 response hash mismatch: {file_id}")
        responses = {int(row["turn_index"]): row for row in json_rows(response_path)}
        local_rows: list[dict[str, object]] = []
        compared_keys = keys_by_id[file_id] + keys_by_id[deranged[file_id]]
        aliases = tuple(alias for key in compared_keys for alias in key.aliases)
        for turn in meetings_by_id[file_id]["turns"]:
            turn_index = int(turn["index"])
            text = str(responses[turn_index].get("text", ""))
            if contains_identity(text, aliases):
                excluded_exact += 1
                continue
            if len(word_tokens(text)) < minimum_tokens:
                excluded_short += 1
                continue
            query = retrieval_features(text)
            correct_key, correct_score = index.best(query, file_id)
            wrong_key, wrong_score = index.best(query, deranged[file_id])
            best_score = max(correct_score, wrong_score)
            denominator = correct_score + wrong_score
            normalized_margin = (correct_score - wrong_score) / denominator if denominator else 0.0
            row = {
                "file_id": file_id,
                "turn_index": turn_index,
                "speaker_id": str(turn["speaker_id"]),
                "correct_key": correct_key.canonical,
                "correct_page": correct_key.page,
                "correct_score": correct_score,
                "deranged_file_id": deranged[file_id],
                "deranged_key": wrong_key.canonical,
                "deranged_page": wrong_key.page,
                "deranged_score": wrong_score,
                "best_score": best_score,
                "normalized_margin": normalized_margin,
            }
            local_rows.append(row)
            all_rows.append(row)
            if best_score > 0.0 and len(examples) < 30:
                examples.append({**row, "query_excerpt": text[:160]})
        meeting_results.append(
            {
                "file_id": file_id,
                "deranged_file_id": deranged[file_id],
                **summarize_signal(local_rows),
            }
        )
    totals = summarize_signal(all_rows)
    gates_config = config["gates"]
    meetings_over_floor = sum(
        float(row["attribution_precision"]) >= float(gates_config["per_meeting_precision_floor"])
        for row in meeting_results
    )
    provenance_checked, provenance_missing = validate_provenance(candidates, material_pages)
    gates = {
        "minimum_meetings": len(file_ids) >= int(gates_config["minimum_meetings"]),
        "minimum_eligible_turns": int(totals["eligible_turns"]) >= int(gates_config["minimum_eligible_turns"]),
        "minimum_dispatch_coverage": float(totals["dispatch_coverage"]) >= float(gates_config["minimum_dispatch_coverage"]),
        "minimum_attribution_precision": float(totals["attribution_precision"]) >= float(gates_config["minimum_attribution_precision"]),
        "minimum_distributed_meetings": meetings_over_floor >= int(gates_config["minimum_meetings_over_precision_floor"]),
        "minimum_median_margin": float(totals["median_normalized_margin"]) >= float(gates_config["minimum_median_normalized_margin"]),
        "complete_provenance": provenance_checked > 0 and provenance_missing == 0,
        "no_reference_contact": True,
    }
    selected_keys = [
        {
            "file_id": key.file_id,
            "canonical": key.canonical,
            "category": key.category,
            "page": key.page,
            "source_span": key.source_span,
        }
        for key in keys
    ]
    return {
        "schema": "meeting-material-retrieval-signal-read-v1",
        "experiment_id": config["experiment_id"],
        "verdict": "RETRIEVAL-SIGNAL-PRESENT" if all(gates.values()) else "RETRIEVAL-SIGNAL-INSUFFICIENT",
        "totals": totals,
        "meetings": meeting_results,
        "meetings_over_precision_floor": meetings_over_floor,
        "excluded_exact_alias_turns": excluded_exact,
        "excluded_short_query_turns": excluded_short,
        "provenance_checked": provenance_checked,
        "provenance_missing": provenance_missing,
        "gates": gates,
        "selected_keys": selected_keys,
        "examples": examples,
        "claim_boundary": config["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--candidate-registry", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--material-pages", required=True, type=Path)
    parser.add_argument("--response-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing a second structural read")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for label, path in (
        ("runtime_sha256", args.runtime),
        ("candidate_registry_sha256", args.candidate_registry),
        ("material_pages_sha256", args.material_pages),
    ):
        if sha256_file(path) != str(config[label]):
            parser.error(f"{label} mismatch")
    result = audit(
        config,
        json.loads(args.candidate_registry.read_text(encoding="utf-8")),
        json.loads(args.runtime.read_text(encoding="utf-8")),
        args.response_dir,
        json_rows(args.material_pages),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "meetings": result["meetings"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
