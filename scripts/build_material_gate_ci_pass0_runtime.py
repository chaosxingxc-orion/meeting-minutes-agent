#!/usr/bin/env python3
"""Build the reference-blind Pass-0 runtime manifest for the material gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import sha256_file  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


MAX_TURN_SECONDS = 120.0


def split_overlong_turn(start: float, end: float, speaker: str) -> list[dict[str, object]]:
    pieces = max(1, math.ceil((end - start) / MAX_TURN_SECONDS))
    return [
        {
            "speaker_id": speaker,
            "start": start + index * MAX_TURN_SECONDS,
            "end": min(end, start + (index + 1) * MAX_TURN_SECONDS),
        }
        for index in range(pieces)
    ]


def build(registration: Path, data_dir: Path) -> dict[str, object]:
    frozen = json.loads(registration.read_text(encoding="utf-8"))
    if frozen.get("experiment_id") != "E-MATERIAL-RUNTIME-GATE-CI":
        raise ValueError("registration experiment mismatch")
    meetings = []
    total_calls = 0
    total_audio_seconds = 0.0
    for item in frozen["cohort"]:
        file_id = str(item["file_id"])
        wav = data_dir / "wav" / f"{file_id}.wav"
        rttm = data_dir / "rttm" / f"{file_id}.rttm"
        if not wav.is_file() or not rttm.is_file():
            raise ValueError(f"missing frozen audio/RTTM for {file_id}")
        pieces = [
            piece
            for turn in parse_rttm_file(rttm)
            for piece in split_overlong_turn(turn.start, turn.end, turn.speaker)
        ]
        turns = [
            {"index": index, **piece, "duration": float(piece["end"]) - float(piece["start"])}
            for index, piece in enumerate(pieces)
        ]
        calls = len(turns)
        audio_seconds = sum(float(turn["duration"]) for turn in turns)
        total_calls += calls
        total_audio_seconds += audio_seconds
        meetings.append(
            {
                "file_id": file_id,
                "split": item["split"],
                "wav_relative": wav.relative_to(data_dir).as_posix(),
                "wav_sha256": sha256_file(wav),
                "rttm_relative": rttm.relative_to(data_dir).as_posix(),
                "rttm_sha256": sha256_file(rttm),
                "calls": calls,
                "audio_seconds": audio_seconds,
                "turns": turns,
            }
        )
    runtime: dict[str, object] = {
        "schema": "material-runtime-gate-ci-pass0-runtime-v1",
        "experiment_id": "E-MATERIAL-RUNTIME-GATE-CI",
        "evidence_tier": "CONSTRUCTION_ISOLATED_EXPLORATORY",
        "registration_sha256": sha256_file(registration),
        "prompt": {
            "template_id": "T1-A1",
            "content_sha256": "f2f32b5572adbceacf678536239682d4271411851f57a80e3a43a6477379e0d2",
        },
        "meetings": meetings,
        "budget": {"calls": total_calls, "audio_seconds": total_audio_seconds},
    }
    runtime["content_hash"] = config_hash(runtime)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    runtime = build(args.registration.resolve(), args.data_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"meetings": len(runtime["meetings"]), **runtime["budget"], "content_hash": runtime["content_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
