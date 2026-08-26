#!/usr/bin/env python3
"""Build the frozen zero-model PDF snapshot for sealed confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import build_material_new_surface_snapshot as base  # noqa: E402


def build_confirmation(
    config: dict[str, Any], cohort: dict[str, Any], dataset_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    items = [item for item in cohort["items"] if item["split"] == "confirmation"]
    if len(items) != 40:
        raise ValueError(f"expected 40 confirmation items, got {len(items)}")
    combined: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]] = ([], [], [], [])
    for start in (0, 20):
        projected = {
            **cohort,
            "items": [{**item, "split": "development"} for item in items[start : start + 20]],
        }
        built = base.build(config, projected, dataset_root)
        for target, values in zip(combined, built, strict=True):
            target.extend(values)
    return combined


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
        "confirmation_snapshot_builder_sha256": Path(__file__).resolve(),
        "base_snapshot_builder_sha256": Path(base.__file__).resolve(),
    }
    for field, path in paths.items():
        if base.sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    pass0_read = json.loads(args.pass0_read.read_text(encoding="utf-8"))
    if (
        pass0_read.get("verdict") != "PASS0_TRACE_COMPLETE"
        or pass0_read.get("reference_access") != "NONE"
        or int(pass0_read.get("calls_completed", -1)) != 80
    ):
        raise ValueError("confirmation Pass0 structural prerequisite failed")
    meetings, pages, candidates, selected = build_confirmation(config, cohort, args.dataset_root)
    args.output_root.mkdir(parents=True)
    base._write_jsonl(args.output_root / "material-pages.jsonl", pages)
    (args.output_root / "candidate-pool.json").write_text(
        json.dumps({"schema": "material-new-surface-candidate-pool-v1", "split": "confirmation", "reference_reads": 0, "candidates": candidates}, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    selected_path = args.output_root / "selected-candidates.json"
    selected_path.write_text(
        json.dumps({"schema": "material-new-surface-selected-candidates-v1", "split": "confirmation", "reference_reads": 0, "candidates": selected}, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    receipt = {
        "schema": "material-new-surface-snapshot-receipt-v1",
        "experiment_id": config["experiment_id"],
        "split": "confirmation",
        "config_sha256": base.sha256_file(args.config),
        "reference_reads": 0,
        "meetings": meetings,
        "totals": {"meetings": len(meetings), "pages": len(pages), "candidates": len(candidates), "selected_candidates": len(selected)},
        "artifacts": {
            name: {"sha256": base.sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
            for name in ("material-pages.jsonl", "candidate-pool.json", "selected-candidates.json")
        },
        "verdict": "MATERIAL_SNAPSHOT_READY",
    }
    (args.output_root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["totals"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
