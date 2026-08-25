#!/usr/bin/env python3
"""Offline admission audit for a downloaded Earnings-22 audio tree."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys


EXPECTED_COMMIT = "c05ab6fd8b4b627d123c922a22a39e993dd37635"
EXPECTED_OBJECTS = 125
EXPECTED_BYTES = 1_908_056_329
MAX_FILE_DURATION_DELTA_S = 2.0
MAX_AGGREGATE_DURATION_RELATIVE_DELTA = 0.001


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, object]:
    process = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(process.stdout)
    streams = [
        stream for stream in result.get("streams", []) if stream.get("codec_type") == "audio"
    ]
    if not streams:
        raise RuntimeError(f"no audio stream: {path}")
    return {
        "duration_seconds": float(result["format"]["duration"]),
        "codec_names": sorted(
            {str(stream["codec_name"]) for stream in streams if stream.get("codec_name")}
        ),
        "sample_rates_hz": sorted(
            {int(stream["sample_rate"]) for stream in streams if stream.get("sample_rate")}
        ),
        "channel_counts": sorted(
            {int(stream["channels"]) for stream in streams if stream.get("channels")}
        ),
    }


def _reference_speaker_count(path: Path) -> int:
    speakers: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        next(handle)
        for line in handle:
            columns = line.rstrip("\n").split("|", 2)
            if len(columns) >= 2 and columns[1]:
                speakers.add(columns[1])
    return len(speakers)


def audit(root: Path, jobs: int) -> dict[str, object]:
    inventory_path = root / ".upstream-audio-manifest.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    objects = inventory["objects"]
    media_dir = root / "media"
    reference_dir = root / "transcripts" / "force_aligned_nlp_references"

    with (root / "metadata.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        metadata_rows = list(csv.DictReader(handle))
    metadata = {row["File ID"]: int(row["File Length (seconds)"]) for row in metadata_rows}
    references = {
        path.name.removesuffix(".aligned.nlp"): path
        for path in reference_dir.glob("*.aligned.nlp")
    }
    audio = {Path(item["path"]).stem: item for item in objects}

    identity_ok = (
        inventory.get("source_commit") == EXPECTED_COMMIT
        and inventory.get("object_count") == EXPECTED_OBJECTS
        and inventory.get("total_size_bytes") == EXPECTED_BYTES
    )
    join_ok = set(audio) == set(metadata) == set(references)

    def inspect(file_id: str) -> dict[str, object]:
        item = audio[file_id]
        path = media_dir / f"{file_id}.mp3"
        expected_size = int(item["size_bytes"])
        expected_hash = str(item["lfs_oid_sha256"])
        size_ok = path.is_file() and path.stat().st_size == expected_size
        hash_ok = size_ok and _sha256(path) == expected_hash
        probe = _probe(path) if hash_ok else None
        duration = float(probe["duration_seconds"]) if probe else None
        return {
            "file_id": file_id,
            "size_ok": size_ok,
            "sha256_ok": hash_ok,
            "probe": probe,
            "metadata_duration_seconds": metadata.get(file_id),
            "duration_delta_seconds": (
                abs(duration - metadata[file_id])
                if duration is not None and file_id in metadata
                else None
            ),
            "reference_speaker_count": (
                _reference_speaker_count(references[file_id])
                if file_id in references
                else None
            ),
        }

    rows: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        for row in executor.map(inspect, sorted(audio)):
            rows.append(row)

    hashes_ok = all(row["size_ok"] and row["sha256_ok"] for row in rows)
    probes_ok = all(row["probe"] is not None for row in rows)
    file_durations_ok = all(
        row["duration_delta_seconds"] is not None
        and float(row["duration_delta_seconds"]) <= MAX_FILE_DURATION_DELTA_S
        for row in rows
    )
    probed_seconds = sum(float(row["probe"]["duration_seconds"]) for row in rows)  # type: ignore[index]
    metadata_seconds = sum(metadata.values())
    aggregate_relative_delta = abs(probed_seconds - metadata_seconds) / metadata_seconds
    aggregate_duration_ok = aggregate_relative_delta <= MAX_AGGREGATE_DURATION_RELATIVE_DELTA

    speaker_distribution: dict[str, int] = {}
    for row in rows:
        count = str(row["reference_speaker_count"])
        speaker_distribution[count] = speaker_distribution.get(count, 0) + 1

    duration_mismatches = sorted(
        (
            {
                "file_id": str(row["file_id"]),
                "metadata_seconds": int(row["metadata_duration_seconds"]),
                "probed_seconds": float(row["probe"]["duration_seconds"]),  # type: ignore[index]
                "absolute_delta_seconds": float(row["duration_delta_seconds"]),
            }
            for row in rows
            if float(row["duration_delta_seconds"]) > MAX_FILE_DURATION_DELTA_S
        ),
        key=lambda item: float(item["absolute_delta_seconds"]),
        reverse=True,
    )

    admitted = all(
        [identity_ok, join_ok, hashes_ok, probes_ok, file_durations_ok, aggregate_duration_ok]
    )
    return {
        "schema": "earnings22-audio-admission-v1",
        "verdict": (
            "EARNINGS22-AUDIO-ADMITTED" if admitted else "EARNINGS22-AUDIO-NOT-ADMITTED"
        ),
        "source_commit": inventory.get("source_commit"),
        "checks": {
            "identity_ok": identity_ok,
            "exact_id_join_ok": join_ok,
            "all_sizes_and_sha256_ok": hashes_ok,
            "all_ffprobe_ok": probes_ok,
            "all_file_duration_deltas_le_2s": file_durations_ok,
            "aggregate_duration_relative_delta_le_0_001": aggregate_duration_ok,
        },
        "summary": {
            "audio_objects": len(audio),
            "metadata_rows": len(metadata),
            "reference_files": len(references),
            "expected_bytes": sum(int(item["size_bytes"]) for item in objects),
            "metadata_duration_seconds": metadata_seconds,
            "probed_duration_seconds": probed_seconds,
            "aggregate_duration_relative_delta": aggregate_relative_delta,
            "max_file_duration_delta_seconds": max(
                float(row["duration_delta_seconds"]) for row in rows
            ),
            "duration_mismatches_over_2s": duration_mismatches,
            "reference_speaker_count_distribution": dict(
                sorted(speaker_distribution.items(), key=lambda pair: int(pair[0]))
            ),
            "meetings_above_four_reference_speakers": sum(
                int(row["reference_speaker_count"]) > 4 for row in rows
            ),
            "meeting_ids_at_or_below_four_reference_speakers": [
                str(row["file_id"])
                for row in rows
                if int(row["reference_speaker_count"]) <= 4
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--earnings22-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be between 1 and 8")
    result = audit(args.earnings22_root.resolve(), args.jobs)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["verdict"] == "EARNINGS22-AUDIO-ADMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
