#!/usr/bin/env python3
"""Acquire the frozen LHCP development audio without reading references."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any
import wave

import requests


DEV_SPLITS = frozenset({"dev_2020", "dev_2022"})
AUDIO_PATH_RE = re.compile(r"^[0-9]+c[0-9]+[.]wav$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class CountingRangeReader(io.RawIOBase):
    """Seekable HTTP range reader with explicit transfer accounting."""

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
        pieces: list[bytes] = []
        cursor = self.position
        maximum_subrange = 16 * 1024 * 1024
        while cursor <= end:
            subrange_end = min(end, cursor + maximum_subrange - 1)
            payload: bytes | None = None
            for attempt in range(1, 6):
                self.requests += 1
                try:
                    response = self._session.get(
                        self.url,
                        headers={"Range": f"bytes={cursor}-{subrange_end}"},
                        timeout=120,
                    )
                    if response.status_code != 206:
                        status = response.status_code
                        response.close()
                        raise RuntimeError(f"remote source rejected range request: {status}")
                    payload = response.content
                    response.close()
                    if len(payload) != subrange_end - cursor + 1:
                        raise RuntimeError("range response length mismatch")
                    break
                except (requests.RequestException, RuntimeError):
                    if attempt == 5:
                        raise
            assert payload is not None
            pieces.append(payload)
            self.transferred_bytes += len(payload)
            cursor += len(payload)
        result = b"".join(pieces)
        self.position += len(result)
        return result


def expected_development_items(cohort: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {
        str(row["audio_path"]): row
        for row in cohort["items"]
        if row["cohort_role"] == "development"
    }
    if len(rows) != 25:
        raise ValueError(f"expected 25 unique development items, got {len(rows)}")
    if any(row["split"] not in DEV_SPLITS for row in rows.values()):
        raise ValueError("non-development split entered development cohort")
    return rows


def development_source_files(admission: dict[str, Any]) -> list[dict[str, Any]]:
    files = [
        row
        for row in admission["source"]["huggingface"]["files"]
        if row["split"] in DEV_SPLITS
    ]
    if len(files) != 6:
        raise ValueError(f"expected six development Parquet files, got {len(files)}")
    if {row["split"] for row in files} != DEV_SPLITS:
        raise ValueError("development source split coverage mismatch")
    return sorted(files, key=lambda row: str(row["path"]))


def wav_info(path: Path) -> dict[str, int | float]:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        if frames <= 0 or rate <= 0:
            raise ValueError(f"empty or invalid WAV: {path}")
        return {
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": rate,
            "frames": frames,
            "duration_s": frames / rate,
        }


def write_audio(
    payload: bytes,
    *,
    audio_path: str,
    split: str,
    output_root: Path,
) -> dict[str, Any]:
    if not AUDIO_PATH_RE.fullmatch(audio_path):
        raise ValueError(f"unsafe audio path: {audio_path}")
    destination = output_root / "audio" / split / audio_path
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    reused = destination.exists()
    if reused:
        if destination.stat().st_size != len(payload) or sha256_file(destination) != payload_sha256:
            raise ValueError(f"existing audio differs from frozen source payload: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".wav.part")
        if temporary.exists():
            raise ValueError(f"partial audio requires inspection: {temporary}")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
        temporary.replace(destination)
    info = wav_info(destination)
    return {
        "audio_path": audio_path,
        "split": split,
        "relative_path": destination.relative_to(output_root).as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": payload_sha256,
        "reused_after_exact_source_match": reused,
        **info,
    }


def acquire(
    config: dict[str, Any],
    cohort: dict[str, Any],
    admission: dict[str, Any],
    output_root: Path,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("pyarrow is required for column-pruned Parquet reads") from exc

    expected = expected_development_items(cohort)
    files = development_source_files(admission)
    source = config["source"]
    found: list[dict[str, Any]] = []
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
        if "transcription" not in parquet.schema.names:
            raise ValueError(f"expected firewall leaf missing: {item['path']}")
        file_rows = 0
        for row_group in range(parquet.num_row_groups):
            table = parquet.read_row_group(row_group, columns=["audio.path", "audio.bytes"])
            for projected in table.to_pylist():
                audio = projected["audio"]
                audio_path = str(audio["path"])
                payload = audio["bytes"]
                if audio_path not in expected:
                    raise ValueError(f"unexpected development audio path: {audio_path}")
                if not isinstance(payload, bytes) or not payload:
                    raise ValueError(f"empty audio payload: {audio_path}")
                receipt = write_audio(
                    payload,
                    audio_path=audio_path,
                    split=str(expected[audio_path]["split"]),
                    output_root=output_root,
                )
                receipt["agenda_duration_minutes"] = expected[audio_path]["duration_s"]
                found.append(receipt)
                file_rows += 1
                print(f"[{len(found)}/25] {audio_path} {receipt['duration_s']:.3f}s", flush=True)
        transfers.append(
            {
                "file": item["path"],
                "remote_bytes": reader.size,
                "range_requests": reader.requests,
                "transferred_bytes": reader.transferred_bytes,
                "projected_columns": ["audio.path", "audio.bytes"],
                "forbidden_columns": ["transcription"],
                "rows": file_rows,
            }
        )
        print(f"source [{file_index}/6] complete: {item['path']}", flush=True)
    actual_paths = [row["audio_path"] for row in found]
    if len(actual_paths) != 25 or len(set(actual_paths)) != 25:
        raise ValueError("development audio count or uniqueness mismatch")
    if set(actual_paths) != set(expected):
        raise ValueError("development audio identity set mismatch")
    return sorted(found, key=lambda row: (row["split"], row["audio_path"])), transfers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--admission-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--receipt-out", required=True, type=Path)
    args = parser.parse_args()
    local_manifest_path = args.output_root / "download-manifest.json"
    for output in (local_manifest_path, args.receipt_out):
        if output.exists():
            raise ValueError(f"output exists: {output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    admission = json.loads(args.admission_manifest.read_text(encoding="utf-8"))
    bindings = config["inputs"]
    if sha256_file(args.cohort) != bindings["cohort_sha256"]:
        raise ValueError("cohort hash mismatch")
    if sha256_file(args.admission_manifest) != bindings["admission_manifest_sha256"]:
        raise ValueError("admission manifest hash mismatch")
    if sha256_file(Path(__file__).resolve()) != bindings["downloader_sha256"]:
        raise ValueError("downloader hash mismatch")
    repository_root = Path(__file__).resolve().parents[1]
    amendment = repository_root / "docs/readiness/2026-08-26-material-lhcp-development-audio-amendment-1.md"
    failure = repository_root / "docs/checks/2026-08-26-material-lhcp-supply/development-audio-attempt-1-failure.json"
    if sha256_file(amendment) != bindings["transport_amendment_sha256"]:
        raise ValueError("transport amendment hash mismatch")
    if sha256_file(failure) != bindings["attempt_1_failure_sha256"]:
        raise ValueError("attempt-1 failure receipt hash mismatch")
    with requests.Session() as session:
        files, transfers = acquire(config, cohort, admission, args.output_root, session)
    local_manifest = {
        "schema": "material-lhcp-development-audio-manifest-v1",
        "experiment_id": config["experiment_id"],
        "source_revision": config["source"]["revision"],
        "projected_columns": ["audio.path", "audio.bytes"],
        "forbidden_columns": ["transcription"],
        "files": files,
        "transfers": transfers,
    }
    local_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    local_manifest_path.write_text(
        json.dumps(local_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    duration_s = sum(float(row["duration_s"]) for row in files)
    counts = {
        "audio_files": len(files),
        "audio_bytes": sum(int(row["bytes"]) for row in files),
        "audio_seconds": duration_s,
        "unique_sha256": len({row["sha256"] for row in files}),
        "source_files": len(transfers),
        "remote_bytes": sum(int(row["remote_bytes"]) for row in transfers),
        "transferred_bytes": sum(int(row["transferred_bytes"]) for row in transfers),
    }
    receipt = {
        "schema": "material-lhcp-development-audio-receipt-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "download_manifest_sha256": sha256_file(local_manifest_path),
        "counts": counts,
        "reference_reads": 0,
        "confirmation_audio_reads": 0,
        "model_contact": {"sortformer": 0, "pass0": 0, "embedding": 0, "omni": 0},
        "verdict": "LHCP_DEVELOPMENT_AUDIO_ACQUIRED",
    }
    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"verdict": receipt["verdict"], "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
