#!/usr/bin/env python3
"""Build separated runtime/score manifests for E-STABLE-ERROR-SUPPLY."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import load_entity_mentions, sha256_file  # noqa: E402
from meeting_minutes_agent.probes.e4_xdomain_supply_v3 import (  # noqa: E402
    analyse_narrow_mentions,
    reserve_inputs,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


SELECTION_SALT = "e-stable-error-supply-2026-08-24-v1"
MEETING_COUNT = 4
MAX_TURN_SECONDS = 120.0


def select_meetings(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    eligible = [row for row in rows if int(row["exclusive_carry"]) >= 2]
    ranked = sorted(
        eligible,
        key=lambda row: (
            -int(row["exclusive_carry"]),
            hashlib.sha256(f"{SELECTION_SALT}\0{row['file_id']}".encode()).hexdigest(),
            str(row["file_id"]),
        ),
    )
    if len(ranked) < MEETING_COUNT:
        raise ValueError("insufficient eligible reserve meetings")
    return ranked[:MEETING_COUNT]


def split_overlong_turn(start: float, end: float, speaker: str) -> list[dict[str, object]]:
    """Apply only the transport-bound exception; preserve all other RTTM boundaries."""
    pieces = max(1, math.ceil((end - start) / MAX_TURN_SECONDS))
    return [
        {
            "speaker_id": speaker,
            "start": start + index * MAX_TURN_SECONDS,
            "end": min(end, start + (index + 1) * MAX_TURN_SECONDS),
        }
        for index in range(pieces)
    ]


def _metadata(path: Path) -> dict[str, str]:
    output = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            output[str(row["File ID"])] = str(row["Ticker Symbol"]).strip()
    return output


def _write(path: Path, value: object) -> None:
    if path.exists():
        raise ValueError(f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def build(root: Path, reserve_manifest: Path, flight_dir: Path, wav_dir: Path) -> tuple[dict[str, object], dict[str, object]]:
    data_root = root.parents[1]
    reserve = json.loads(reserve_manifest.read_text(encoding="utf-8"))
    candidates = []
    refs = {}
    for item in reserve_inputs(reserve, root):
        mentions = load_entity_mentions(item.path)
        counts = analyse_narrow_mentions(mentions)
        candidates.append({"file_id": item.file_id, "exclusive_carry": counts.exclusive_carry})
        refs[item.file_id] = item.path
    selected = select_meetings(candidates)
    tickers = _metadata(root / "metadata.csv")
    runtime_meetings = []
    score_meetings = []
    total_calls = 0
    total_audio_seconds = 0.0
    for selected_row in selected:
        file_id = str(selected_row["file_id"])
        wav = wav_dir / f"{file_id}.wav"
        rttm = flight_dir / "rttm" / f"{file_id}.rttm"
        if not wav.is_file() or not rttm.is_file():
            raise ValueError(f"missing frozen audio/RTTM for {file_id}")
        turns = parse_rttm_file(rttm)
        pieces = [piece for turn in turns for piece in split_overlong_turn(turn.start, turn.end, turn.speaker)]
        turn_rows = [
            {"index": index, **piece, "duration": float(piece["end"]) - float(piece["start"])}
            for index, piece in enumerate(pieces)
        ]
        total_calls += len(turn_rows)
        total_audio_seconds += sum(float(row["duration"]) for row in turn_rows)
        runtime_meetings.append(
            {
                "file_id": file_id,
                "wav_relative": wav.resolve().relative_to(data_root).as_posix(),
                "wav_sha256": sha256_file(wav),
                "rttm_relative": rttm.resolve().relative_to(data_root).as_posix(),
                "rttm_sha256": sha256_file(rttm),
                "turns": turn_rows,
            }
        )
        reference = refs[file_id]
        score_meetings.append(
            {
                "file_id": file_id,
                "reference_relative": reference.resolve().relative_to(data_root).as_posix(),
                "reference_sha256": sha256_file(reference),
                "ticker_anchor": tickers.get(file_id, ""),
                "selection_exclusive_carry": int(selected_row["exclusive_carry"]),
            }
        )
    runtime: dict[str, object] = {
        "schema": "earnings22-stable-error-runtime-v1",
        "experiment_id": "E-STABLE-ERROR-SUPPLY",
        "selection_salt": SELECTION_SALT,
        "meetings": runtime_meetings,
        "budget": {"calls": total_calls, "audio_seconds": total_audio_seconds},
    }
    runtime["content_hash"] = config_hash(runtime)
    score: dict[str, object] = {
        "schema": "earnings22-stable-error-score-v1",
        "experiment_id": "E-STABLE-ERROR-SUPPLY",
        "runtime_content_hash": runtime["content_hash"],
        "allowed_entity_classes": ["ABBREVIATION", "ALPHANUMERIC"],
        "meetings": score_meetings,
    }
    score["content_hash"] = config_hash(score)
    return runtime, score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--earnings22-root", required=True, type=Path)
    parser.add_argument("--reserve-manifest", required=True, type=Path)
    parser.add_argument("--flight-dir", required=True, type=Path)
    parser.add_argument("--wav-dir", required=True, type=Path)
    parser.add_argument("--runtime-out", required=True, type=Path)
    parser.add_argument("--score-out", required=True, type=Path)
    args = parser.parse_args()
    runtime, score = build(
        args.earnings22_root.resolve(), args.reserve_manifest.resolve(),
        args.flight_dir.resolve(), args.wav_dir.resolve(),
    )
    _write(args.runtime_out, runtime)
    _write(args.score_out, score)
    print(json.dumps({"meetings": [row["file_id"] for row in runtime["meetings"]], "budget": runtime["budget"], "runtime_hash": runtime["content_hash"], "score_hash": score["content_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
