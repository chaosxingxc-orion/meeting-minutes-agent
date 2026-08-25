#!/usr/bin/env python3
"""One-shot offline audit of an RTTM-only dominant-speaker eligibility gate."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402


WINDOW_SECONDS = 600.0
MIN_WINDOW_SPEECH_SECONDS = 30.0
MIN_TOTAL_SPEECH_SECONDS = 300.0
MIN_TOP2_SHARE = 0.60
MIN_STABLE_WINDOW_FRACTION = 0.80
MIN_ACTIVE_WINDOWS_PER_TOP_CLUSTER = 3


def _duration_by_speaker(turns: object, start: float | None = None, end: float | None = None) -> dict[str, float]:
    durations: dict[str, float] = defaultdict(float)
    for turn in turns:  # type: ignore[union-attr]
        left = turn.start if start is None else max(turn.start, start)
        right = turn.end if end is None else min(turn.end, end)
        if right > left:
            durations[turn.speaker] += right - left
    return dict(durations)


def runtime_features(turns: object) -> dict[str, object]:
    durations = _duration_by_speaker(turns)
    ranked = sorted(durations, key=lambda speaker: (-durations[speaker], speaker))
    top2 = ranked[:2]
    total = sum(durations.values())
    top2_share = sum(durations[speaker] for speaker in top2) / total if total else 0.0
    maximum_end = max((turn.end for turn in turns), default=0.0)  # type: ignore[union-attr]
    qualifying = 0
    stable = 0
    active_windows = {speaker: 0 for speaker in top2}
    window_start = 0.0
    while window_start < maximum_end:
        window_durations = _duration_by_speaker(turns, window_start, window_start + WINDOW_SECONDS)
        window_total = sum(window_durations.values())
        if window_total >= MIN_WINDOW_SPEECH_SECONDS:
            qualifying += 1
            pair_share = sum(window_durations.get(speaker, 0.0) for speaker in top2) / window_total
            if pair_share >= MIN_TOP2_SHARE:
                stable += 1
            for speaker in top2:
                if window_durations.get(speaker, 0.0) > 0:
                    active_windows[speaker] += 1
        window_start += WINDOW_SECONDS
    stable_fraction = stable / qualifying if qualifying else 0.0
    occupancy_only = total >= MIN_TOTAL_SPEECH_SECONDS and len(top2) == 2 and top2_share >= MIN_TOP2_SHARE
    admitted = (
        occupancy_only
        and stable_fraction >= MIN_STABLE_WINDOW_FRACTION
        and all(count >= MIN_ACTIVE_WINDOWS_PER_TOP_CLUSTER for count in active_windows.values())
    )
    return {
        "hypothesis_speaker_count": len(ranked),
        "detected_speech_seconds": total,
        "top2_clusters": top2,
        "top2_speech_share": top2_share,
        "qualifying_window_count": qualifying,
        "stable_window_count": stable,
        "stable_window_fraction": stable_fraction,
        "top2_active_window_counts": active_windows,
        "occupancy_only_admitted": occupancy_only,
        "runtime_admitted": admitted,
    }


def _pool_error(rows: list[dict[str, object]], part: str) -> float | None:
    values = [row["word_attribution"][part] for row in rows]  # type: ignore[index]
    reference = sum(float(value["reference_seconds"]) for value in values)
    correct = sum(float(value["correct_seconds"]) for value in values)
    return 1.0 - correct / reference if reference else None


def score_gate(scored: dict[str, object], flight_dir: Path) -> dict[str, object]:
    records = []
    for gold in scored["per_meeting"]:  # type: ignore[index]
        turns = parse_rttm_file(flight_dir / "rttm" / f"{gold['file_id']}.rttm")
        features = runtime_features(turns)
        in_universe = bool(
            gold.get("scorable")
            and float(gold["aligned_token_fraction"]) >= 0.8
            and float(gold["aligned_word_seconds"]) >= 300
            and int(gold["reference_speaker_count"]) > 4
        )
        gold_dominant = bool(in_universe and float(gold["top2_aligned_speech_share"]) >= 0.6)
        top1_error = None
        top2_error = None
        if gold.get("scorable"):
            top1_error = float(gold["word_attribution"]["top1"]["error_rate"])
            top2_error = float(gold["word_attribution"]["top2"]["error_rate"])
        records.append(
            {
                "file_id": gold["file_id"],
                **features,
                "primary_universe": in_universe,
                "gold_top2_dominant": gold_dominant,
                "gold_top1_attribution_error": top1_error,
                "gold_top2_attribution_error": top2_error,
            }
        )

    by_id = {row["file_id"]: row for row in scored["per_meeting"]}  # type: ignore[index]
    universe = [row for row in records if row["primary_universe"]]
    admitted = [row for row in universe if row["runtime_admitted"]]
    true_positive = sum(bool(row["gold_top2_dominant"]) for row in admitted)
    positives = sum(bool(row["gold_top2_dominant"]) for row in universe)
    precision = true_positive / len(admitted) if admitted else 0.0
    recall = true_positive / positives if positives else 0.0
    admitted_gold_rows = [by_id[row["file_id"]] for row in admitted]
    top1_error = _pool_error(admitted_gold_rows, "top1") if admitted_gold_rows else None
    top2_error = _pool_error(admitted_gold_rows, "top2") if admitted_gold_rows else None
    unsafe = sum(float(row["gold_top2_attribution_error"]) > 0.40 for row in admitted)
    unsafe_fraction = unsafe / len(admitted) if admitted else 0.0
    gates = {
        "minimum_admitted_meetings": len(admitted) >= 15,
        "dominance_precision": precision >= 0.70,
        "dominance_recall": recall >= 0.60,
        "pooled_top1_error": top1_error is not None and top1_error <= 0.20,
        "pooled_top2_error": top2_error is not None and top2_error <= 0.25,
        "unsafe_meeting_fraction": unsafe_fraction <= 0.10,
    }
    if not gates["minimum_admitted_meetings"]:
        verdict = "INSUFFICIENT-RUNTIME-SUPPLY"
    elif all(gates.values()):
        verdict = "RUNTIME-DOMINANT-GATE-USABLE"
    else:
        verdict = "RUNTIME-DOMINANT-GATE-UNSAFE"
    return {
        "schema": "earnings22-runtime-dominant-gate-v1",
        "verdict": verdict,
        "limitations": "Retrospective audit on a corpus whose aggregate reference results were previously read; no threshold search was performed.",
        "runtime_rule": {
            "window_seconds": WINDOW_SECONDS,
            "minimum_window_speech_seconds": MIN_WINDOW_SPEECH_SECONDS,
            "minimum_total_speech_seconds": MIN_TOTAL_SPEECH_SECONDS,
            "minimum_top2_share": MIN_TOP2_SHARE,
            "minimum_stable_window_fraction": MIN_STABLE_WINDOW_FRACTION,
            "minimum_active_windows_per_top_cluster": MIN_ACTIVE_WINDOWS_PER_TOP_CLUSTER,
        },
        "primary": {
            "universe_meetings": len(universe),
            "gold_dominant_meetings": positives,
            "admitted_meetings": len(admitted),
            "true_positive_meetings": true_positive,
            "dominance_precision": precision,
            "dominance_recall": recall,
            "pooled_top1_attribution_error": top1_error,
            "pooled_top2_attribution_error": top2_error,
            "unsafe_meetings": unsafe,
            "unsafe_meeting_fraction": unsafe_fraction,
            "decision_gates": gates,
        },
        "diagnostics": {
            "occupancy_only_admitted_in_universe": sum(bool(row["occupancy_only_admitted"]) for row in universe),
            "runtime_admitted_all_125": sum(bool(row["runtime_admitted"]) for row in records),
        },
        "per_meeting": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sortformer-score", required=True, type=Path)
    parser.add_argument("--flight-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists; refusing a second read")
    scored = json.loads(args.sortformer_score.read_text(encoding="utf-8"))
    result = score_gate(scored, args.flight_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "primary": result["primary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
