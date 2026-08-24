#!/usr/bin/env python3
"""Profile, prepare, fly, and score the Earnings-22 Sortformer experiment."""

from __future__ import annotations

import argparse
from collections import defaultdict
import concurrent.futures
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.chunking.slicer import TurnSpan  # noqa: E402
from meeting_minutes_agent.metrics.diarization_error import (  # noqa: E402
    compute_der,
    pool_der_breakdowns,
)


PINNED_SOURCE_COMMIT = "c05ab6fd8b4b627d123c922a22a39e993dd37635"
PINNED_MODEL_SHA256 = "0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a"
PINNED_BINARY_SHA256 = "1a3e3f4fe7db4c48e5d6e44a76d5adf2bbfef80024c023b0eab2766eb61aca78"
TURN_GAP_SECONDS = 1.0
SPEAKER_BINS = ((0, 4, "le4"), (5, 8, "5to8"), (9, 16, "9to16"), (17, 10_000, "gt16"))


@dataclass(frozen=True)
class WordSpan:
    speaker: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def speaker_bin(count: int) -> str:
    for lower, upper, name in SPEAKER_BINS:
        if lower <= count <= upper:
            return name
    raise AssertionError(count)


def load_words(path: Path) -> tuple[list[WordSpan], set[str], int]:
    words: list[WordSpan] = []
    all_speakers: set[str] = set()
    total_tokens = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        for row in reader:
            total_tokens += 1
            speaker = row.get("speaker", "")
            if speaker:
                all_speakers.add(speaker)
            if not speaker or not row.get("ts") or not row.get("endTs"):
                continue
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except ValueError:
                continue
            if end > start >= 0:
                words.append(WordSpan(speaker, start, end))
    words.sort(key=lambda word: (word.start, word.end, word.speaker))
    return words, all_speakers, total_tokens


def reference_profile(path: Path) -> dict[str, object]:
    words, all_speakers, total_tokens = load_words(path)
    duration_by_speaker: dict[str, float] = defaultdict(float)
    for word in words:
        duration_by_speaker[word.speaker] += word.duration
    ranked = sorted(duration_by_speaker.items(), key=lambda item: (-item[1], item[0]))
    total_aligned = sum(duration_by_speaker.values())
    top1 = ranked[0][1] / total_aligned if ranked and total_aligned else 0.0
    top2 = sum(value for _, value in ranked[:2]) / total_aligned if total_aligned else 0.0
    return {
        "reference_speaker_count": len(all_speakers),
        "speaker_count_bin": speaker_bin(len(all_speakers)),
        "total_tokens": total_tokens,
        "aligned_tokens": len(words),
        "aligned_token_fraction": len(words) / total_tokens if total_tokens else 0.0,
        "aligned_word_seconds": total_aligned,
        "top1_aligned_speech_share": top1,
        "top2_aligned_speech_share": top2,
    }


def command_profile(args: argparse.Namespace) -> int:
    root = args.earnings22_root.resolve()
    upstream = json.loads((root / ".upstream-audio-manifest.json").read_text(encoding="utf-8"))
    if upstream["source_commit"] != PINNED_SOURCE_COMMIT:
        raise SystemExit("unexpected Earnings-22 source commit")
    records = []
    for item in upstream["objects"]:
        file_id = Path(item["path"]).stem
        reference = root / "transcripts" / "force_aligned_nlp_references" / f"{file_id}.aligned.nlp"
        profile = reference_profile(reference)
        records.append(
            {
                "file_id": file_id,
                "audio_relative": f"media/{file_id}.mp3",
                "audio_lfs_sha256": item["lfs_oid_sha256"],
                "audio_bytes": item["size_bytes"],
                "reference_relative": f"transcripts/force_aligned_nlp_references/{file_id}.aligned.nlp",
                "reference_sha256": sha256_file(reference),
                **profile,
            }
        )
    records.sort(key=lambda row: row["file_id"])
    over4 = [row for row in records if row["reference_speaker_count"] > 4]
    primary = [
        row
        for row in over4
        if row["aligned_token_fraction"] >= 0.8
        and row["aligned_word_seconds"] >= 300
        and row["top2_aligned_speech_share"] >= 0.6
    ]
    document = {
        "schema": "earnings22-sortformer-roster-v1",
        "source_commit": PINNED_SOURCE_COMMIT,
        "turn_gap_seconds_for_proxy_der": TURN_GAP_SECONDS,
        "meeting_count": len(records),
        "summary": {
            "meetings_above_four_speakers": len(over4),
            "primary_above_four_top2_dominant_meetings": len(primary),
            "median_top2_share_above_four": _quantile(
                [float(row["top2_aligned_speech_share"]) for row in over4], 0.5
            ),
            "speaker_count_bins": {
                name: sum(row["speaker_count_bin"] == name for row in records)
                for _, _, name in SPEAKER_BINS
            },
        },
        "meetings": records,
    }
    atomic_json(args.output.resolve(), document)
    print(json.dumps(document["summary"], indent=2, sort_keys=True))
    return 0


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def command_prepare(args: argparse.Namespace) -> int:
    root = args.earnings22_root.resolve()
    roster = json.loads(args.roster.resolve().read_text(encoding="utf-8"))
    wav_dir = args.wav_dir.resolve()
    wav_dir.mkdir(parents=True, exist_ok=True)
    def convert(row: dict[str, object]) -> dict[str, object]:
        file_id = row["file_id"]
        source = root / str(row["audio_relative"])
        destination = wav_dir / f"{file_id}.wav"
        if not destination.exists():
            temporary = destination.with_suffix(".wav.part")
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-v", "error", "-i", str(source),
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", "-y", str(temporary),
                ],
                check=True,
            )
            temporary.replace(destination)
        return {
            "file_id": file_id,
            "wav_relative": destination.name,
            "wav_bytes": destination.stat().st_size,
            "wav_sha256": sha256_file(destination),
        }

    receipts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(convert, row) for row in roster["meetings"]]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            receipt = future.result()
            receipts.append(receipt)
            print(f"prepare {index:03d}/{len(roster['meetings']):03d}: {receipt['file_id']}", flush=True)
    receipts.sort(key=lambda row: str(row["file_id"]))
    atomic_json(
        args.receipt.resolve(),
        {
            "schema": "earnings22-sortformer-wav-conversion-v1",
            "conversion": "ffmpeg -ac 1 -ar 16000 -c:a pcm_s16le",
            "meetings": receipts,
        },
    )
    return 0


def command_flight(args: argparse.Namespace) -> int:
    roster = json.loads(args.roster.resolve().read_text(encoding="utf-8"))
    binary, model = args.binary.resolve(), args.model.resolve()
    if sha256_file(binary) != PINNED_BINARY_SHA256:
        raise SystemExit("binary SHA-256 does not match pin")
    if sha256_file(model) != PINNED_MODEL_SHA256:
        raise SystemExit("model SHA-256 does not match pin")
    out = args.output_dir.resolve()
    rttm_dir, receipt_dir, log_dir = out / "rttm", out / "receipts", out / "logs"
    for directory in (rttm_dir, receipt_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    started_all = time.monotonic()
    outcomes = []
    for index, row in enumerate(roster["meetings"], start=1):
        if time.monotonic() - started_all >= args.max_wall_hours * 3600:
            raise SystemExit("registered wall-time ceiling reached before next contact")
        file_id = row["file_id"]
        receipt_path = receipt_dir / f"{file_id}.json"
        rttm_path = rttm_dir / f"{file_id}.rttm"
        if args.resume and receipt_path.exists() and rttm_path.exists():
            prior = json.loads(receipt_path.read_text(encoding="utf-8"))
            if prior.get("ok"):
                print(f"resume {index:03d}: {file_id}", flush=True)
                outcomes.append(prior)
                continue
        command = [
            str(binary), "diarize", str(args.wav_dir.resolve() / f"{file_id}.wav"),
            "--model", str(model), "--format", "rttm", "--recording-id", file_id,
            "--output", str(rttm_path), "--force",
        ]
        began = time.monotonic()
        with (log_dir / f"{file_id}.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
        wall = time.monotonic() - began
        outcome = {
            "file_id": file_id,
            "ok": process.returncode == 0 and rttm_path.exists(),
            "return_code": process.returncode,
            "wall_seconds": wall,
            "rttm_sha256": sha256_file(rttm_path) if rttm_path.exists() else None,
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(receipt_path, outcome)
        outcomes.append(outcome)
        print(f"flight {index:03d}/{len(roster['meetings']):03d}: {file_id} ok={outcome['ok']} wall={wall:.1f}s", flush=True)
    summary = {
        "schema": "earnings22-sortformer-flight-v1",
        "tool": "nemo-speech.cpp-cuda-q8_0 DiarStream",
        "binary_sha256": PINNED_BINARY_SHA256,
        "model_sha256": PINNED_MODEL_SHA256,
        "n_contacts": len(outcomes),
        "n_ok": sum(bool(row["ok"]) for row in outcomes),
        "n_error": sum(not bool(row["ok"]) for row in outcomes),
        "wall_seconds": time.monotonic() - started_all,
        "outcomes": outcomes,
    }
    atomic_json(out / "flight-summary.json", summary)
    return 0 if summary["n_error"] == 0 else 1


def _best_mapping(matrix: dict[str, dict[str, float]], gold: list[str], hyp: list[str]) -> dict[str, str]:
    # Exact maximum-weight one-to-one matching. The hypothesis side has at
    # most four labels, so a 2^H dynamic program avoids factorial growth in
    # the number of reference speakers.
    states: dict[int, tuple[float, dict[str, str]]] = {0: (0.0, {})}
    for gold_speaker in gold:
        updated = dict(states)
        for mask, (score, mapping) in states.items():
            for index, hyp_speaker in enumerate(hyp):
                bit = 1 << index
                if mask & bit:
                    continue
                candidate = score + matrix.get(gold_speaker, {}).get(hyp_speaker, 0.0)
                new_mask = mask | bit
                if new_mask not in updated or candidate > updated[new_mask][0]:
                    updated[new_mask] = (candidate, {**mapping, gold_speaker: hyp_speaker})
        states = updated
    return max(states.values(), key=lambda item: item[0])[1]


def _word_assignment_metrics(words: list[WordSpan], hypotheses: tuple[TurnSpan, ...]) -> dict[str, object]:
    gold_speakers = sorted({word.speaker for word in words})
    hyp_speakers = sorted({turn.speaker for turn in hypotheses})
    matrix: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    duration_by_gold: dict[str, float] = defaultdict(float)
    missed_by_gold: dict[str, float] = defaultdict(float)
    for word in words:
        duration_by_gold[word.speaker] += word.duration
        midpoint = (word.start + word.end) / 2
        active = [turn for turn in hypotheses if turn.start <= midpoint < turn.end]
        if not active:
            missed_by_gold[word.speaker] += word.duration
            continue
        chosen = max(
            active,
            key=lambda turn: min(word.end, turn.end) - max(word.start, turn.start),
        )
        matrix[word.speaker][chosen.speaker] += word.duration
    ranked = sorted(gold_speakers, key=lambda speaker: (-duration_by_gold[speaker], speaker))
    mapping = _best_mapping(matrix, gold_speakers, hyp_speakers)

    def subset_metrics(subset: list[str]) -> dict[str, float]:
        total = sum(duration_by_gold[speaker] for speaker in subset)
        correct = sum(matrix[speaker].get(mapping.get(speaker, ""), 0.0) for speaker in subset)
        missed = sum(missed_by_gold[speaker] for speaker in subset)
        return {
            "reference_seconds": total,
            "correct_seconds": correct,
            "missed_seconds": missed,
            "error_rate": 1.0 - correct / total if total else 0.0,
        }

    return {
        "mapping": mapping,
        "reference_speaker_ranking": ranked,
        "all": subset_metrics(ranked),
        "top1": subset_metrics(ranked[:1]),
        "top2": subset_metrics(ranked[:2]),
        "tail": subset_metrics(ranked[2:]),
    }


def _reference_turns(words: list[WordSpan]) -> list[TurnSpan]:
    turns: list[TurnSpan] = []
    for word in words:
        if turns and turns[-1].speaker == word.speaker and word.start - turns[-1].end <= TURN_GAP_SECONDS:
            previous = turns[-1]
            turns[-1] = TurnSpan(previous.start, max(previous.end, word.end), previous.speaker)
        else:
            turns.append(TurnSpan(word.start, word.end, word.speaker))
    return turns


def command_score(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("score output exists; refusing a second read")
    root = args.earnings22_root.resolve()
    roster = json.loads(args.roster.resolve().read_text(encoding="utf-8"))
    per_meeting = []
    der_no_collar: dict[str, object] = {}
    der_collar: dict[str, object] = {}
    for row in roster["meetings"]:
        file_id = row["file_id"]
        words, _, _ = load_words(root / row["reference_relative"])
        hypotheses = parse_rttm_file(args.flight_dir.resolve() / "rttm" / f"{file_id}.rttm")
        if not words:
            per_meeting.append(
                {
                    "file_id": file_id,
                    "reference_speaker_count": row["reference_speaker_count"],
                    "speaker_count_bin": row["speaker_count_bin"],
                    "top2_aligned_speech_share": row["top2_aligned_speech_share"],
                    "aligned_token_fraction": row["aligned_token_fraction"],
                    "aligned_word_seconds": row["aligned_word_seconds"],
                    "hypothesis_speaker_count": len({turn.speaker for turn in hypotheses}),
                    "scorable": False,
                }
            )
            continue
        word_metrics = _word_assignment_metrics(words, hypotheses)
        reference_turns = _reference_turns(words)
        mapping = word_metrics["mapping"]
        no_collar = compute_der(reference_turns, hypotheses, collar=0.0, skip_overlap=False, speaker_mapping=mapping)
        collar = compute_der(reference_turns, hypotheses, collar=0.25, skip_overlap=True, speaker_mapping=mapping)
        der_no_collar[file_id] = no_collar
        der_collar[file_id] = collar
        per_meeting.append(
            {
                "file_id": file_id,
                "reference_speaker_count": row["reference_speaker_count"],
                "speaker_count_bin": row["speaker_count_bin"],
                "top2_aligned_speech_share": row["top2_aligned_speech_share"],
                "aligned_token_fraction": row["aligned_token_fraction"],
                "aligned_word_seconds": row["aligned_word_seconds"],
                "hypothesis_speaker_count": len({turn.speaker for turn in hypotheses}),
                "scorable": True,
                "word_attribution": word_metrics,
                "proxy_der_no_collar": no_collar.to_dict(),
                "proxy_der_collar_0_25": collar.to_dict(),
            }
        )

    def aggregate(rows: list[dict[str, object]], indices: list[int]) -> dict[str, object]:
        indices = [index for index in indices if rows[index].get("scorable")]
        def pool_word(part: str) -> dict[str, float]:
            values = [rows[index]["word_attribution"][part] for index in indices]  # type: ignore[index]
            total = sum(float(value["reference_seconds"]) for value in values)
            correct = sum(float(value["correct_seconds"]) for value in values)
            missed = sum(float(value["missed_seconds"]) for value in values)
            return {
                "reference_seconds": total,
                "correct_seconds": correct,
                "missed_seconds": missed,
                "error_rate": 1.0 - correct / total if total else 0.0,
            }
        return {
            "meetings": len(indices),
            "word_attribution_all": pool_word("all"),
            "word_attribution_top1": pool_word("top1"),
            "word_attribution_top2": pool_word("top2"),
            "word_attribution_tail": pool_word("tail"),
            "proxy_der_no_collar": pool_der_breakdowns([der_no_collar[str(rows[index]["file_id"])] for index in indices]).to_dict(),
            "proxy_der_collar_0_25": pool_der_breakdowns([der_collar[str(rows[index]["file_id"])] for index in indices]).to_dict(),
        }

    groups = {"all": list(range(len(per_meeting)))}
    for _, _, name in SPEAKER_BINS:
        groups[f"speaker_bin_{name}"] = [
            index for index, row in enumerate(per_meeting) if row["speaker_count_bin"] == name
        ]
    groups["above_four"] = [
        index for index, row in enumerate(per_meeting) if int(row["reference_speaker_count"]) > 4
    ]
    groups["primary_evaluable"] = [
        index
        for index, row in enumerate(per_meeting)
        if float(row["aligned_token_fraction"]) >= 0.8 and float(row["aligned_word_seconds"]) >= 300
    ]
    groups["primary_above_four"] = [
        index
        for index in groups["primary_evaluable"]
        if int(per_meeting[index]["reference_speaker_count"]) > 4
    ]
    groups["primary_above_four_top2_dominant"] = [
        index
        for index in groups["primary_above_four"]
        if float(per_meeting[index]["top2_aligned_speech_share"]) >= 0.6
    ]
    aggregates = {name: aggregate(per_meeting, indices) for name, indices in groups.items() if indices}
    target = aggregates["primary_above_four_top2_dominant"]
    top2_error = float(target["word_attribution_top2"]["error_rate"])  # type: ignore[index]
    top1_error = float(target["word_attribution_top1"]["error_rate"])  # type: ignore[index]
    if top2_error <= 0.25 and top1_error <= 0.20:
        verdict = "MAIN-SPEAKER-DIARIZATION-USABLE"
    elif top2_error > 0.40 or top1_error > 0.35:
        verdict = "MAIN-SPEAKER-DIARIZATION-POOR"
    else:
        verdict = "MAIN-SPEAKER-DIARIZATION-UNCERTAIN"
    document = {
        "schema": "earnings22-sortformer-score-v1",
        "verdict": verdict,
        "thresholds": {"usable_top2_error_max": 0.25, "usable_top1_error_max": 0.20, "poor_top2_error_gt": 0.40, "poor_top1_error_gt": 0.35},
        "scoring_limit": "Gold is force-aligned word timing, not human RTTM. Word attribution is primary; reconstructed-turn DER is a proxy using a fixed 1.0 s same-speaker gap.",
        "primary_population": "aligned_token_fraction >= 0.8, aligned_word_seconds >= 300, reference speakers > 4, top2 share >= 0.6",
        "aggregates": aggregates,
        "per_meeting": per_meeting,
    }
    atomic_json(output, document)
    print(json.dumps({"verdict": verdict, "primary_target": target}, indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser()
    sub = main.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("--earnings22-root", required=True, type=Path)
    profile.add_argument("--output", required=True, type=Path)
    profile.set_defaults(func=command_profile)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--earnings22-root", required=True, type=Path)
    prepare.add_argument("--roster", required=True, type=Path)
    prepare.add_argument("--wav-dir", required=True, type=Path)
    prepare.add_argument("--receipt", required=True, type=Path)
    prepare.add_argument("--jobs", type=int, default=4)
    prepare.set_defaults(func=command_prepare)
    flight = sub.add_parser("flight")
    flight.add_argument("--roster", required=True, type=Path)
    flight.add_argument("--wav-dir", required=True, type=Path)
    flight.add_argument("--binary", required=True, type=Path)
    flight.add_argument("--model", required=True, type=Path)
    flight.add_argument("--output-dir", required=True, type=Path)
    flight.add_argument("--max-wall-hours", type=float, default=4.0)
    flight.add_argument("--resume", action="store_true")
    flight.set_defaults(func=command_flight)
    score = sub.add_parser("score")
    score.add_argument("--earnings22-root", required=True, type=Path)
    score.add_argument("--roster", required=True, type=Path)
    score.add_argument("--flight-dir", required=True, type=Path)
    score.add_argument("--output", required=True, type=Path)
    score.set_defaults(func=command_score)
    return main


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.func(arguments))
