#!/usr/bin/env python3
"""Build a provenance-bearing zero-model snapshot from official PDF/HTML files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.meeting_materials import (  # noqa: E402
    classify_material_document,
    extract_candidate_surfaces,
    extract_visible_html_text,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--materials-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists; refusing to overwrite a snapshot")

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    registry_sha256 = sha256_file(args.registry)
    receipt_rows: list[dict[str, object]] = []
    pages: list[dict[str, object]] = []
    pool: dict[tuple[str, str], dict[str, object]] = {}

    for meeting in registry["meetings"]:
        file_id = str(meeting["file_id"])
        for source in meeting["sources"]:
            local_name = source.get("local_name")
            if not local_name:
                continue
            path = args.materials_dir / str(local_name)
            exists = path.is_file()
            header = path.read_bytes()[:1024] if exists else b""
            document_type = classify_material_document(header, path.suffix) if exists else "unsupported"
            is_pdf = document_type == "pdf"
            is_html = document_type == "html"
            row = {
                "file_id": file_id,
                "issuer": meeting["issuer"],
                "period": meeting["period"],
                "kind": source["kind"],
                "url": source["url"],
                "resolved_asset_url": source.get("resolved_asset_url"),
                "local_name": local_name,
                "exists": exists,
                "is_pdf": is_pdf,
                "is_html": is_html,
                "document_type": document_type,
                "bytes": path.stat().st_size if exists else 0,
                "sha256": sha256_file(path) if exists else None,
                "temporal_status": source["temporal_status"],
                "use_for_candidates": bool(source.get("use_for_candidates")),
            }
            receipt_rows.append(row)
            if not (exists and (is_pdf or is_html) and source.get("use_for_candidates")):
                continue
            if is_pdf:
                reader = PdfReader(path)
                document_pages = [
                    (page_index, page.extract_text() or "")
                    for page_index, page in enumerate(reader.pages, start=1)
                ]
            else:
                html = path.read_text(encoding="utf-8", errors="replace")
                document_pages = [(1, extract_visible_html_text(html))]
            for page_index, text in document_pages:
                page_row = {
                    "file_id": file_id,
                    "document_sha256": row["sha256"],
                    "local_name": local_name,
                    "page": page_index,
                    "text": text,
                }
                pages.append(page_row)
                for candidate in extract_candidate_surfaces(text):
                    key = (file_id, candidate["surface"].casefold())
                    entry = pool.setdefault(
                        key,
                        {
                            "file_id": file_id,
                            "surface": candidate["surface"],
                            "kind": candidate["kind"],
                            "occurrences": [],
                        },
                    )
                    entry["occurrences"].append(
                        {
                            "document_sha256": row["sha256"],
                            "local_name": local_name,
                            "page": page_index,
                        }
                    )

    args.output_dir.mkdir(parents=True)
    receipt = {
        "schema": "meeting-material-acquisition-receipt-v1",
        "experiment_id": registry["experiment_id"],
        "registry_sha256": registry_sha256,
        "materials_dir": str(args.materials_dir),
        "sources": receipt_rows,
    }
    (args.output_dir / "acquisition-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    with (args.output_dir / "material-pages.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in pages:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    candidate_pool = {
        "schema": "meeting-material-candidate-pool-v1",
        "experiment_id": registry["experiment_id"],
        "construction_reference_reads": 0,
        "candidates": sorted(pool.values(), key=lambda row: (row["file_id"], row["surface"].casefold())),
    }
    (args.output_dir / "candidate-pool.json").write_text(
        json.dumps(candidate_pool, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"sources": len(receipt_rows), "pages": len(pages), "candidates": len(pool)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
