#!/usr/bin/env python3
"""Acquire the authorized LHCP development reference column only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import (  # noqa: E402
    CountingRangeReader,
    development_source_files,
    expected_development_items,
    sha256_file,
)


def write_json_exclusive(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def acquire(
    config: dict[str, Any],
    cohort: dict[str, Any],
    admission: dict[str, Any],
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyarrow is required for column-pruned Parquet reads") from exc
    expected = expected_development_items(cohort)
    files = development_source_files(admission)
    source = config["source"]
    references: list[dict[str, Any]] = []
    transfers: list[dict[str, Any]] = []
    for file_index, item in enumerate(files, 1):
        url = (
            f"https://huggingface.co/datasets/{source['dataset']}/resolve/"
            f"{source['revision']}/{item['path']}"
        )
        reader = CountingRangeReader(url, session)
        if reader.size != int(item["size"]):
            raise ValueError(f"remote size mismatch: {item['path']}")
        parquet = pq.ParquetFile(reader)
        if "path" not in parquet.schema.names or "transcription" not in parquet.schema.names:
            raise ValueError(f"source schema drift: {item['path']}")
        file_rows = 0
        for row_group in range(parquet.num_row_groups):
            table = parquet.read_row_group(row_group, columns=["audio.path", "transcription"])
            for projected in table.to_pylist():
                audio_path = str(projected["audio"]["path"])
                if audio_path not in expected:
                    raise ValueError(f"unexpected development identity: {audio_path}")
                transcription = projected["transcription"]
                if not isinstance(transcription, str) or not transcription.strip():
                    raise ValueError(f"empty reference: {audio_path}")
                references.append({
                    "schema": "material-lhcp-development-reference-row-v1",
                    "audio_path": audio_path,
                    "meeting_id": Path(audio_path).stem,
                    "split": str(expected[audio_path]["split"]),
                    "transcription": transcription,
                    "transcription_sha256": hashlib.sha256(transcription.encode("utf-8")).hexdigest(),
                    "characters": len(transcription),
                    "source_file": str(item["path"]),
                })
                file_rows += 1
        transfers.append({
            "file": item["path"],
            "remote_bytes": reader.size,
            "range_requests": reader.requests,
            "transferred_bytes": reader.transferred_bytes,
            "projected_columns": ["audio.path", "transcription"],
            "forbidden_columns": ["audio.bytes"],
            "rows": file_rows,
        })
        print(f"source [{file_index}/6] {item['path']} rows={file_rows}", flush=True)
    identities = [str(row["audio_path"]) for row in references]
    if len(identities) != 25 or len(set(identities)) != 25 or set(identities) != set(expected):
        raise ValueError("development reference identity closure failed")
    return sorted(references, key=lambda row: (str(row["split"]), str(row["audio_path"]))), transfers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--admission-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    admission = json.loads(args.admission_manifest.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(config["inputs"]["preregistration_path"]),
        "cohort_sha256": args.cohort,
        "admission_manifest_sha256": args.admission_manifest,
        "acquirer_sha256": Path(__file__).resolve(),
        "range_reader_sha256": ROOT / str(config["inputs"]["range_reader_path"]),
        "reader_sha256": ROOT / str(config["inputs"]["reader_path"]),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    source = admission["source"]["huggingface"]
    if source["dataset"] != config["source"]["dataset"] or source["revision"] != config["source"]["revision"]:
        raise ValueError("source identity drift")
    session = requests.Session()
    session.headers.update({"User-Agent": "meeting-minutes-agent-lhcp-reference-audit/1"})
    references, transfers = acquire(config, cohort, admission, session)
    args.output_root.mkdir(parents=True)
    references_path = args.output_root / "references.jsonl"
    write_jsonl_exclusive(references_path, references)
    receipt = {
        "schema": "material-lhcp-development-reference-acquisition-receipt-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "reference_reads": len(references),
        "development_references": len(references),
        "confirmation_access": 0,
        "test_split_access": 0,
        "audio_body_reads": 0,
        "source_transfers": transfers,
        "artifacts": {
            "references.jsonl": {
                "sha256": sha256_file(references_path),
                "bytes": references_path.stat().st_size,
            }
        },
        "verdict": "LHCP_DEVELOPMENT_REFERENCES_ACQUIRED",
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    print(json.dumps({
        "verdict": receipt["verdict"],
        "references": len(references),
        "transferred_bytes": sum(int(row["transferred_bytes"]) for row in transfers),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
