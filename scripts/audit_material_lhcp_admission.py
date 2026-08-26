#!/usr/bin/env python3
"""Metadata-only LHCP-ASR to CERN Indico admission audit."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import requests


PATH_PATTERN = re.compile(r"^(?P<event_id>[0-9]+)c(?P<friendly_id>[0-9]+)[.]wav$")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_tokens(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


class CountingRangeReader(io.RawIOBase):
    """Seekable remote reader that refuses non-range responses."""

    def __init__(self, url: str, session: requests.Session) -> None:
        self._session = session
        response = session.head(url, allow_redirects=True, timeout=60)
        response.raise_for_status()
        self.url = response.url
        self.size = int(response.headers["content-length"])
        self.position = 0
        self.transferred_bytes = 0
        self.requests = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        positions = {
            io.SEEK_SET: offset,
            io.SEEK_CUR: self.position + offset,
            io.SEEK_END: self.size + offset,
        }
        if whence not in positions:
            raise ValueError(f"unsupported whence: {whence}")
        position = positions[whence]
        if position < 0:
            raise ValueError("negative seek position")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.size:
            return b""
        if size is None or size < 0:
            size = self.size - self.position
        end = min(self.size - 1, self.position + size - 1)
        response = self._session.get(
            self.url,
            headers={"Range": f"bytes={self.position}-{end}"},
            stream=True,
            timeout=120,
        )
        if response.status_code != 206:
            response.close()
            raise RuntimeError(f"remote source rejected range request: {response.status_code}")
        payload = response.content
        response.close()
        if len(payload) != end - self.position + 1:
            raise RuntimeError("range response length mismatch")
        self.position += len(payload)
        self.transferred_bytes += len(payload)
        self.requests += 1
        return payload


def hf_file_metadata(config: dict[str, Any], session: requests.Session) -> list[dict[str, Any]]:
    dataset = config["huggingface"]["dataset"]
    revision = config["huggingface"]["revision"]
    url = f"https://huggingface.co/api/datasets/{dataset}/revision/{revision}?blobs=true"
    response = session.get(url, timeout=60)
    response.raise_for_status()
    expected = set(config["huggingface"]["expected_splits"])
    files = []
    for item in response.json().get("siblings", []):
        name = str(item.get("rfilename", ""))
        match = re.fullmatch(r"longform/([^/]+)-[0-9]+-of-[0-9]+[.]parquet", name)
        if match and match.group(1) in expected:
            files.append({"path": name, "split": match.group(1), "size": int(item["size"])})
    return sorted(files, key=lambda row: row["path"])


def read_hf_paths(
    config: dict[str, Any], files: list[dict[str, Any]], session: requests.Session
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("pyarrow is required for column-pruned Parquet reads") from exc

    dataset = config["huggingface"]["dataset"]
    revision = config["huggingface"]["revision"]
    rows: list[dict[str, str]] = []
    transfers: list[dict[str, Any]] = []
    for item in files:
        url = f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/{item['path']}"
        reader = CountingRangeReader(url, session)
        parquet = pq.ParquetFile(reader)
        leaf_columns = list(parquet.schema.names)
        if "path" not in leaf_columns or "bytes" not in leaf_columns or "transcription" not in leaf_columns:
            raise RuntimeError(f"unexpected Parquet schema in {item['path']}: {leaf_columns}")
        table = parquet.read(columns=["audio.path"])
        projected = table.to_pylist()
        for row in projected:
            rows.append({"split": item["split"], "audio_path": str(row["audio"]["path"])})
        transfers.append(
            {
                "file": item["path"],
                "remote_bytes": reader.size,
                "range_requests": reader.requests,
                "transferred_bytes": reader.transferred_bytes,
                "projected_columns": ["audio.path"],
                "rows": table.num_rows,
            }
        )
    return rows, transfers


def project_indico_event(event_id: int, session: requests.Session) -> dict[str, Any]:
    url = f"https://indico.cern.ch/export/event/{event_id}.json?detail=contributions"
    response = session.get(url, timeout=120)
    response.raise_for_status()
    raw = response.json()["results"]
    if len(raw) != 1:
        raise RuntimeError(f"unexpected Indico event result count for {event_id}: {len(raw)}")
    event = raw[0]
    contributions = []
    for contribution in event.get("contributions", []):
        attachments = []
        for folder in contribution.get("folders") or []:
            for attachment in folder.get("attachments") or []:
                attachments.append(
                    {
                        "id": attachment.get("id"),
                        "filename": attachment.get("filename"),
                        "download_url": attachment.get("download_url"),
                        "content_type": attachment.get("content_type"),
                        "size": attachment.get("size"),
                        "checksum": attachment.get("checksum"),
                    }
                )
        contributions.append(
            {
                "id": contribution.get("id"),
                "db_id": contribution.get("db_id"),
                "friendly_id": contribution.get("friendly_id"),
                "title": contribution.get("title"),
                "title_tokens": normalized_tokens(str(contribution.get("title", ""))),
                "duration_s": contribution.get("duration"),
                "speakers": [speaker.get("fullName") for speaker in contribution.get("speakers") or []],
                "attachments": attachments,
            }
        )
    projected = {"event_id": event_id, "title": event.get("title"), "contributions": contributions}
    projected["projection_sha256"] = sha256_bytes(
        (json.dumps(projected, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return projected


def audit(config: dict[str, Any], session: requests.Session) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    files = hf_file_metadata(config, session)
    rows, transfers = read_hf_paths(config, files, session)
    events = {
        int(event_id): project_indico_event(int(event_id), session)
        for event_id in config["indico"]["events"].values()
    }
    contribution_index = {
        (event_id, int(contribution["friendly_id"])): contribution
        for event_id, event in events.items()
        for contribution in event["contributions"]
        if contribution["friendly_id"] is not None
    }
    material_extensions = {value.casefold() for value in config["indico"]["material_extensions"]}
    joined: list[dict[str, Any]] = []
    orphans: list[dict[str, str]] = []
    ambiguities: list[dict[str, str]] = []
    for row in rows:
        match = PATH_PATTERN.fullmatch(row["audio_path"])
        if match is None:
            orphans.append({**row, "reason": "audio_path_identifier_parse_failed"})
            continue
        event_id = int(match.group("event_id"))
        friendly_id = int(match.group("friendly_id"))
        contribution = contribution_index.get((event_id, friendly_id))
        if contribution is None:
            orphans.append({**row, "reason": "indico_contribution_not_found"})
            continue
        materials = [
            attachment
            for attachment in contribution["attachments"]
            if Path(str(attachment.get("filename", ""))).suffix.casefold() in material_extensions
            and int(attachment.get("size") or 0) > 0
            and attachment.get("download_url")
        ]
        joined.append(
            {
                **row,
                "join_evidence": "event_id_plus_friendly_id",
                "event_id": event_id,
                "contribution_id": contribution["id"],
                "contribution_db_id": contribution["db_id"],
                "contribution_friendly_id": friendly_id,
                "title": contribution["title"],
                "duration_s": contribution["duration_s"],
                "speakers": contribution["speakers"],
                "materials": materials,
            }
        )

    split_counts = Counter(row["split"] for row in rows)
    expected_splits = config["huggingface"]["expected_splits"]
    if dict(sorted(split_counts.items())) != dict(sorted(expected_splits.items())):
        errors.append(f"split counts differ: actual={dict(split_counts)} expected={expected_splits}")
    if len(rows) != int(config["passing_gates"]["hf_rows"]):
        errors.append(f"HF row count differs: {len(rows)}")
    if len({row["audio_path"] for row in rows}) != len(rows):
        errors.append("HF audio paths are not unique")
    contribution_keys = [(row["event_id"], row["contribution_friendly_id"]) for row in joined]
    duplicate_contributions = len(contribution_keys) - len(set(contribution_keys))
    material_covered = sum(bool(row["materials"]) for row in joined)
    material_urls = [item["download_url"] for row in joined for item in row["materials"]]
    material_checksums = [item["checksum"] for row in joined for item in row["materials"] if item.get("checksum")]
    duplicate_material_urls = len(material_urls) - len(set(material_urls))
    duplicate_material_checksums = len(material_checksums) - len(set(material_checksums))
    if len(joined) != int(config["passing_gates"]["joined_rows"]):
        errors.append(f"joined row count differs: {len(joined)}")
    if duplicate_contributions:
        errors.append(f"duplicate contribution bindings: {duplicate_contributions}")
    if orphans:
        errors.append(f"orphan rows: {len(orphans)}")
    if ambiguities:
        errors.append(f"ambiguous rows: {len(ambiguities)}")
    if material_covered != int(config["passing_gates"]["material_covered_rows"]):
        errors.append(f"material-covered rows differ: {material_covered}")
    if duplicate_material_urls != int(config["passing_gates"]["duplicate_material_bindings"]):
        errors.append(f"duplicate material URLs: {duplicate_material_urls}")
    if duplicate_material_checksums != int(config["passing_gates"]["duplicate_material_bindings"]):
        errors.append(f"duplicate material checksums: {duplicate_material_checksums}")

    manifest = {
        "schema": "material-lhcp-admission-manifest-v1",
        "experiment_id": config["experiment_id"],
        "reference_firewall": {
            "projected_hf_columns": ["audio.path"],
            "reference_reads": 0,
            "audio_body_reads": 0,
            "material_body_reads": 0,
        },
        "source": {
            "huggingface": {
                "dataset": config["huggingface"]["dataset"],
                "revision": config["huggingface"]["revision"],
                "files": files,
                "range_transfers": transfers,
            },
            "indico": [
                {
                    "event_id": event_id,
                    "title": event["title"],
                    "contribution_count": len(event["contributions"]),
                    "projection_sha256": event["projection_sha256"],
                }
                for event_id, event in sorted(events.items())
            ],
        },
        "items": joined,
        "orphans": orphans,
        "ambiguities": ambiguities,
    }
    counts = {
        "hf_rows": len(rows),
        "splits": dict(sorted(split_counts.items())),
        "joined_rows": len(joined),
        "unique_contributions": len(set(contribution_keys)),
        "orphan_rows": len(orphans),
        "ambiguous_rows": len(ambiguities),
        "material_covered_rows": material_covered,
        "material_attachment_count": len(material_urls),
        "duplicate_material_urls": duplicate_material_urls,
        "duplicate_material_checksums": duplicate_material_checksums,
        "duplicate_material_bindings": duplicate_material_urls + duplicate_material_checksums,
        "hf_remote_bytes": sum(row["remote_bytes"] for row in transfers),
        "hf_transferred_bytes": sum(row["transferred_bytes"] for row in transfers),
        "hf_range_requests": sum(row["range_requests"] for row in transfers),
    }
    verdict = {
        "schema": "material-lhcp-admission-verdict-v1",
        "experiment_id": config["experiment_id"],
        "counts": counts,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "reference_contact": 0,
        "errors": errors,
        "verdict": (
            "LHCP_METADATA_JOIN_AND_MATERIAL_COVERAGE_CLOSED"
            if not errors
            else "LHCP_ADMISSION_INCOMPLETE"
        ),
    }
    return manifest, verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--verdict-out", required=True, type=Path)
    args = parser.parse_args()
    for output in (args.manifest_out, args.verdict_out):
        if output.exists():
            raise ValueError(f"output exists: {output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    with requests.Session() as session:
        manifest, verdict = audit(config, session)
    config_sha256 = sha256_file(args.config)
    manifest["config_sha256"] = config_sha256
    manifest_payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    verdict["config_sha256"] = config_sha256
    verdict["manifest_sha256"] = sha256_bytes(manifest_payload.encode("utf-8"))
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(manifest_payload, encoding="utf-8", newline="\n")
    args.verdict_out.parent.mkdir(parents=True, exist_ok=True)
    args.verdict_out.write_text(
        json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"verdict": verdict["verdict"], "counts": verdict["counts"], "errors": verdict["errors"]}, indent=2))
    return 0 if not verdict["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
