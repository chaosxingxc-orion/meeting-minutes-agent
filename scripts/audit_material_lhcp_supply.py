#!/usr/bin/env python3
"""Zero-model readability and candidate-supply audit for LHCP materials."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.meeting_materials import extract_candidate_surfaces  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(value: str) -> str:
    return " ".join(value.split())


def replace_lone_surrogates(value: str) -> str:
    """Make extractor output valid Unicode without changing legal code points."""

    return "".join("\ufffd" if 0xD800 <= ord(character) <= 0xDFFF else character for character in value)


def excerpt(text: str, surface: str, radius: int) -> str:
    value = compact(text)
    position = value.casefold().find(surface.casefold())
    if position < 0:
        return value[: radius * 2]
    return value[max(0, position - radius) : min(len(value), position + len(surface) + radius)]


def extract_pdf(path: Path) -> list[tuple[int, str]]:
    document = PdfReader(path, strict=False)
    return [(index, page.extract_text() or "") for index, page in enumerate(document.pages, 1)]


def extract_pptx(path: Path) -> list[tuple[int, str]]:
    pattern = re.compile(r"ppt/slides/slide([0-9]+)[.]xml$")
    pages = []
    with zipfile.ZipFile(path) as archive:
        names = []
        for name in archive.namelist():
            match = pattern.fullmatch(name)
            if match:
                names.append((int(match.group(1)), name))
        if not names:
            raise ValueError("PPTX contains no slide XML")
        for number, name in sorted(names):
            root = ElementTree.fromstring(archive.read(name))
            text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
            pages.append((number, text))
    return pages


def extract_document(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".ppt", ".pptx"}:
        if suffix == ".ppt":
            raise ValueError("legacy PPT is unsupported by the frozen extractor")
        return extract_pptx(path)
    raise ValueError(f"unsupported material suffix: {suffix}")


def audit(
    config: dict[str, Any], download_manifest: dict[str, Any], dataset_root: Path, output_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    rules = config["construction"]
    minimum_characters = int(rules["minimum_visible_characters_per_meeting"])
    minimum_candidates = int(rules["minimum_candidates_per_meeting"])
    documents = []
    page_rows = []
    candidate_rows = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in download_manifest["files"]:
        grouped.setdefault(str(row["audio_path"]), []).append(row)

    meetings = []
    for audio_path in sorted(grouped):
        material_rows = grouped[audio_path]
        candidates: dict[str, dict[str, Any]] = {}
        meeting_characters = 0
        readable_documents = 0
        split = str(material_rows[0]["split"])
        for material in material_rows:
            path = dataset_root / str(material["relative_path"])
            if path.stat().st_size != int(material["bytes"]) or sha256_file(path) != material["sha256"]:
                raise ValueError(f"local material binding mismatch: {path}")
            error = None
            pages: list[tuple[int, str]] = []
            try:
                pages = extract_document(path)
                pages = [(number, replace_lone_surrogates(text)) for number, text in pages]
            except Exception as exc:  # fail is captured per frozen attachment
                error = type(exc).__name__
            visible_characters = sum(len(compact(text)) for _, text in pages)
            if visible_characters:
                readable_documents += 1
            meeting_characters += visible_characters
            document_candidate_keys: set[str] = set()
            for page_number, text in pages:
                compact_text = compact(text)
                page_rows.append(
                    {
                        "audio_path": audio_path,
                        "split": split,
                        "relative_path": material["relative_path"],
                        "page": page_number,
                        "text": text,
                    }
                )
                for candidate in extract_candidate_surfaces(text):
                    canonical = str(candidate["surface"])
                    key = canonical.casefold()
                    document_candidate_keys.add(key)
                    if key not in candidates:
                        candidates[key] = {
                            "audio_path": audio_path,
                            "split": split,
                            "canonical": canonical,
                            "category": str(candidate["kind"]),
                            "occurrences": [],
                        }
                    candidates[key]["occurrences"].append(
                        {
                            "relative_path": material["relative_path"],
                            "page": page_number,
                            "source_span": excerpt(
                                compact_text,
                                canonical,
                                int(rules["source_excerpt_radius_characters"]),
                            ),
                        }
                    )
            documents.append(
                {
                    "audio_path": audio_path,
                    "split": split,
                    "relative_path": material["relative_path"],
                    "suffix": path.suffix.casefold(),
                    "pages": len(pages),
                    "visible_characters": visible_characters,
                    "candidate_count": len(document_candidate_keys),
                    "parse_error": error,
                }
            )
        ordered_candidates = [candidates[key] for key in sorted(candidates)]
        candidate_rows.extend(ordered_candidates)
        reasons = []
        if readable_documents < 1:
            reasons.append("no_readable_document")
        if meeting_characters < minimum_characters:
            reasons.append("visible_characters_below_gate")
        if len(ordered_candidates) < minimum_candidates:
            reasons.append("candidate_count_below_gate")
        meetings.append(
            {
                "audio_path": audio_path,
                "split": split,
                "attachments": len(material_rows),
                "readable_documents": readable_documents,
                "visible_characters": meeting_characters,
                "candidate_count": len(ordered_candidates),
                "passed": not reasons,
                "failure_reasons": reasons,
            }
        )

    output_root.mkdir(parents=True)
    with (output_root / "material-pages.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in page_rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    (output_root / "candidate-pool.json").write_text(
        json.dumps({"schema": "material-lhcp-candidate-pool-v1", "reference_reads": 0, "candidates": candidate_rows}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    failed = [row for row in meetings if not row["passed"]]
    split_counts = Counter(row["split"] for row in meetings)
    split_passed = Counter(row["split"] for row in meetings if row["passed"])
    parsed_documents = sum(row["parse_error"] is None for row in documents)
    verdict = {
        "schema": "material-lhcp-supply-verdict-v1",
        "experiment_id": config["experiment_id"],
        "counts": {
            "meetings": len(meetings),
            "passed_meetings": len(meetings) - len(failed),
            "failed_meetings": len(failed),
            "split_meetings": dict(sorted(split_counts.items())),
            "split_passed": dict(sorted(split_passed.items())),
            "documents": len(documents),
            "parsed_documents": parsed_documents,
            "failed_documents": len(documents) - parsed_documents,
            "pages_or_slides": len(page_rows),
            "visible_characters": sum(row["visible_characters"] for row in meetings),
            "unique_candidates_meeting_sum": sum(row["candidate_count"] for row in meetings),
            "minimum_meeting_candidates": min((row["candidate_count"] for row in meetings), default=0),
            "minimum_meeting_visible_characters": min((row["visible_characters"] for row in meetings), default=0),
        },
        "gates": {
            "minimum_visible_characters_per_meeting": minimum_characters,
            "minimum_candidates_per_meeting": minimum_candidates,
            "required_passing_meetings": int(config["passing_gates"]["meetings"]),
        },
        "meetings": meetings,
        "documents": documents,
        "failed_meeting_ids": [row["audio_path"] for row in failed],
        "reference_reads": 0,
        "audio_downloads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "verdict": (
            "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_READY"
            if len(meetings) == int(config["passing_gates"]["meetings"]) and not failed
            else "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT"
        ),
    }
    artifacts = {
        name: {"sha256": sha256_file(output_root / name), "bytes": (output_root / name).stat().st_size}
        for name in ("material-pages.jsonl", "candidate-pool.json")
    }
    receipt = {
        "schema": "material-lhcp-supply-receipt-v1",
        "experiment_id": config["experiment_id"],
        "artifacts": artifacts,
        "verdict": verdict["verdict"],
    }
    (output_root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return verdict, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--download-manifest", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--verdict-out", required=True, type=Path)
    args = parser.parse_args()
    if args.output_root.exists() or args.verdict_out.exists():
        raise ValueError("output exists; audit is append-only")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    frozen_code = {
        "supply_script_sha256": Path(__file__).resolve(),
        "candidate_extractor_sha256": SRC / "meeting_minutes_agent" / "state" / "meeting_materials.py",
    }
    for field, path in frozen_code.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"frozen code hash mismatch: {field}")
    download_manifest = json.loads(args.download_manifest.read_text(encoding="utf-8"))
    if download_manifest.get("source_manifest_sha256") != config["inputs"]["admission_manifest_sha256"]:
        raise ValueError("download manifest source binding mismatch")
    verdict, receipt = audit(config, download_manifest, args.dataset_root, args.output_root)
    verdict["config_sha256"] = sha256_file(args.config)
    verdict["download_manifest_sha256"] = sha256_file(args.download_manifest)
    verdict["supply_receipt_sha256"] = sha256_file(args.output_root / "receipt.json")
    args.verdict_out.parent.mkdir(parents=True, exist_ok=True)
    args.verdict_out.write_text(
        json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"verdict": verdict["verdict"], "counts": verdict["counts"]}, indent=2))
    return 0 if verdict["verdict"] == "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_READY" else 3


if __name__ == "__main__":
    raise SystemExit(main())
