#!/usr/bin/env python3
"""Download and verify the frozen LHCP official-material inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(value).name).strip("._")
    if not cleaned:
        raise ValueError("empty material filename")
    return cleaned


def session_with_retries() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def material_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in manifest["items"]:
        for material in item["materials"]:
            rows.append(
                {
                    "audio_path": item["audio_path"],
                    "split": item["split"],
                    "event_id": int(item["event_id"]),
                    "contribution_friendly_id": int(item["contribution_friendly_id"]),
                    **material,
                }
            )
    return sorted(rows, key=lambda row: (row["event_id"], row["contribution_friendly_id"], str(row["id"])))


def download_one(row: dict[str, Any], output_root: Path, session: requests.Session) -> dict[str, Any]:
    url = str(row["download_url"])
    if urlparse(url).hostname != "indico.cern.ch":
        raise ValueError(f"unexpected material host: {url}")
    name = f"{row['id']}-{safe_filename(str(row['filename']))}"
    relative = Path("materials") / str(row["event_id"]) / str(row["contribution_friendly_id"]) / name
    destination = output_root / relative
    expected_bytes = int(row["size"])
    expected_md5 = str(row["checksum"]).casefold()
    if destination.exists():
        if destination.stat().st_size != expected_bytes or md5_file(destination) != expected_md5:
            raise ValueError(f"existing material binding mismatch: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        if temporary.exists():
            raise ValueError(f"partial file requires manual inspection: {temporary}")
        response = session.get(url, stream=True, timeout=(30, 180))
        response.raise_for_status()
        with temporary.open("xb") as handle:
            for block in response.iter_content(1024 * 1024):
                if block:
                    handle.write(block)
        response.close()
        if temporary.stat().st_size != expected_bytes or md5_file(temporary) != expected_md5:
            raise ValueError(f"downloaded material binding mismatch: {temporary}")
        temporary.replace(destination)
    return {
        **row,
        "relative_path": relative.as_posix(),
        "bytes": destination.stat().st_size,
        "md5": md5_file(destination),
        "sha256": sha256_file(destination),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--admission-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--receipt-out", required=True, type=Path)
    args = parser.parse_args()
    if args.receipt_out.exists():
        raise ValueError(f"output exists: {args.receipt_out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    repository_root = Path(__file__).resolve().parents[1]
    frozen_code = {
        "download_script_sha256": Path(__file__).resolve(),
        "supply_script_sha256": repository_root / "scripts" / "audit_material_lhcp_supply.py",
        "candidate_extractor_sha256": repository_root / "src" / "meeting_minutes_agent" / "state" / "meeting_materials.py",
    }
    for field, path in frozen_code.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"frozen code hash mismatch: {field}")
    if sha256_file(args.admission_manifest) != config["inputs"]["admission_manifest_sha256"]:
        raise ValueError("admission manifest hash mismatch")
    local_manifest_path = args.output_root / "download-manifest.json"
    if local_manifest_path.exists():
        raise ValueError(f"completed download manifest already exists: {local_manifest_path}")
    manifest = json.loads(args.admission_manifest.read_text(encoding="utf-8"))
    rows = material_rows(manifest)
    if len(rows) != int(config["acquisition"]["expected_attachments"]):
        raise ValueError(f"attachment count differs: {len(rows)}")
    downloaded = []
    with session_with_retries() as session:
        for index, row in enumerate(rows, 1):
            downloaded.append(download_one(row, args.output_root, session))
            print(f"[{index}/{len(rows)}] {row['audio_path']} {row['filename']}", flush=True)
    local_manifest = {
        "schema": "material-lhcp-download-manifest-v1",
        "experiment_id": config["experiment_id"],
        "source_manifest_sha256": sha256_file(args.admission_manifest),
        "files": downloaded,
    }
    local_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    local_manifest_path.write_text(
        json.dumps(local_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    counts = {
        "files": len(downloaded),
        "bytes": sum(row["bytes"] for row in downloaded),
        "unique_sha256": len({row["sha256"] for row in downloaded}),
        "unique_md5": len({row["md5"] for row in downloaded}),
    }
    receipt = {
        "schema": "material-lhcp-acquisition-receipt-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "source_manifest_sha256": sha256_file(args.admission_manifest),
        "download_manifest_sha256": sha256_file(local_manifest_path),
        "counts": counts,
        "reference_reads": 0,
        "audio_downloads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "verdict": "LHCP_MATERIAL_ACQUISITION_COMPLETE",
    }
    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": receipt["verdict"], "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
