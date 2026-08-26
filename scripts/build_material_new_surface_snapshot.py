#!/usr/bin/env python3
"""Build the frozen development material snapshot without reading references."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.material_retrieval import word_tokens  # noqa: E402
from meeting_minutes_agent.state.material_trace import sha256_text  # noqa: E402
from meeting_minutes_agent.state.meeting_materials import extract_candidate_surfaces  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: str) -> str:
    return " ".join(value.split())


def excerpt(text: str, surface: str, radius: int) -> str:
    value = compact(text)
    position = value.casefold().find(surface.casefold())
    if position < 0:
        return value[: radius * 2]
    return value[max(0, position - radius) : min(len(value), position + len(surface) + radius)]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _value(canonical: str, category: str, page: int, source_span: str) -> dict[str, Any]:
    prompt = f"Official material evidence: {canonical}. Source excerpt: {source_span}"
    return {
        "canonical": canonical,
        "category": category,
        "source_page": page,
        "source_span": source_span,
        "prompt_text": prompt,
        "prompt_sha256": sha256_text(prompt),
    }


def build(config: dict[str, Any], cohort: dict[str, Any], dataset_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rules = config["construction"]
    width = int(rules["key_width"])
    radius = int(rules["source_excerpt_radius_characters"])
    salt = str(rules["key_selection_salt"])
    pages: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    meetings: list[dict[str, Any]] = []
    development = [item for item in cohort["items"] if item["split"] == "development"]
    if len(development) != 20:
        raise ValueError(f"expected 20 development items, got {len(development)}")
    for item in development:
        item_id = str(item["item_id"])
        meeting_id = str(item["call_id"])
        slide = item["slide"]
        pdf_path = dataset_root / str(slide["relative_path"])
        if sha256_file(pdf_path) != slide["sha256"] or pdf_path.stat().st_size != int(slide["bytes"]):
            raise ValueError(f"slide binding mismatch: {item_id}")
        candidates: dict[str, dict[str, Any]] = {}
        document = PdfReader(pdf_path)
        for page_number, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            pages.append({
                "item_id": item_id,
                "meeting_id": meeting_id,
                "document_sha256": slide["sha256"],
                "page": page_number,
                "text": text,
            })
            for candidate in extract_candidate_surfaces(text):
                canonical = str(candidate["surface"])
                key = canonical.casefold()
                occurrence = {"page": page_number, "source_span": excerpt(text, canonical, radius)}
                if key not in candidates:
                    candidates[key] = {
                        "item_id": item_id,
                        "meeting_id": meeting_id,
                        "canonical": canonical,
                        "category": str(candidate["kind"]),
                        "occurrences": [],
                    }
                candidates[key]["occurrences"].append(occurrence)
        rows = sorted(candidates.values(), key=lambda row: str(row["canonical"]).casefold())
        all_candidates.extend(rows)
        ordered = sorted(
            rows,
            key=lambda row: (
                hashlib.sha256(f"{salt}:{meeting_id}:{str(row['canonical']).casefold()}".encode()).hexdigest(),
                str(row["canonical"]).casefold(),
            ),
        )
        if len(ordered) < width:
            raise ValueError(f"meeting {meeting_id} has only {len(ordered)} candidates; requires {width}")
        for selection_index, row in enumerate(ordered[:width], 1):
            occurrence = sorted(row["occurrences"], key=lambda value: (int(value["page"]), str(value["source_span"])))[0]
            canonical = str(row["canonical"])
            source_span = str(occurrence["source_span"])
            key_text = f"Official material candidate: {canonical}. Context: {source_span}"
            candidate_id = f"mns-{meeting_id}-{sha256_text(canonical.casefold())[:12]}"
            selected.append({
                "selection_index": selection_index,
                "candidate_id": candidate_id,
                "item_id": item_id,
                "meeting_id": meeting_id,
                "key_text": key_text,
                "key_sha256": sha256_text(key_text),
                "value": _value(canonical, str(row["category"]), int(occurrence["page"]), source_span),
            })
        meetings.append({
            "item_id": item_id,
            "meeting_id": meeting_id,
            "slide_relative_path": slide["relative_path"],
            "slide_sha256": slide["sha256"],
            "pages": len(document.pages),
            "candidate_count": len(rows),
            "selected_count": width,
        })
    return meetings, pages, all_candidates, selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--pass0-runtime", required=True, type=Path)
    parser.add_argument("--pass0-read", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    paths = {
        "cohort_sha256": args.cohort,
        "pass0_runtime_sha256": args.pass0_runtime,
        "pass0_structural_read_sha256": args.pass0_read,
        "snapshot_builder_sha256": Path(__file__).resolve(),
    }
    for field, path in paths.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    pass0_read = json.loads(args.pass0_read.read_text(encoding="utf-8"))
    if pass0_read.get("verdict") != "PASS0_TRACE_COMPLETE" or pass0_read.get("reference_access") != "NONE":
        raise ValueError("Pass0 structural prerequisite failed")
    meetings, pages, candidates, selected = build(config, cohort, args.dataset_root)
    args.output_root.mkdir(parents=True)
    _write_jsonl(args.output_root / "material-pages.jsonl", pages)
    (args.output_root / "candidate-pool.json").write_text(
        json.dumps({"schema": "material-new-surface-candidate-pool-v1", "reference_reads": 0, "candidates": candidates}, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    selected_path = args.output_root / "selected-candidates.json"
    selected_path.write_text(
        json.dumps({"schema": "material-new-surface-selected-candidates-v1", "reference_reads": 0, "candidates": selected}, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    receipt = {
        "schema": "material-new-surface-snapshot-receipt-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "reference_reads": 0,
        "meetings": meetings,
        "totals": {"meetings": len(meetings), "pages": len(pages), "candidates": len(candidates), "selected_candidates": len(selected)},
        "artifacts": {
            name: {"sha256": sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
            for name in ("material-pages.jsonl", "candidate-pool.json", "selected-candidates.json")
        },
        "verdict": "MATERIAL_SNAPSHOT_READY",
    }
    (args.output_root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["totals"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
