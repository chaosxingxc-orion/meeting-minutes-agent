#!/usr/bin/env python3
"""P-PROMPT sweep -- registered ONE-SHOT scoring read.

Runs the committed scoring path
(:mod:`meeting_minutes_agent.probes.pprompt_scoring`) over all 14 arms'
flown replies and writes ``verdict.json`` + ``report.txt`` to ``--out-dir``,
mirroring the P-ATTR smoke's own read pair
(``docs/checks/2026-08-18-pattr-smoke-read/``). Refuses (fail-closed) to
overwrite a prior read's output unless ``--force`` is passed
(:func:`~meeting_minutes_agent.probes.pprompt_scoring.assert_one_shot_output_dir`)
-- the "one-shot read" discipline the P-PROMPT preregistration requires
(``docs/readiness/2026-08-18-pprompt-preregistration.md`` SS6).

Real I/O, zero model contact: this script reads already-flown reply JSONLs
(never sends a request) and resolves the AMI gold transcript for the four
P-ATTR-smoke meetings via :mod:`meeting_minutes_agent.corpora.nxt` (already-
licensed, already-acquired annotation XML -- the same corpus access every
other scoring/read path in this repository uses).

Usage::

    python scripts/pprompt_read.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --pattr-manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --responses-dir "$SPEECHRL_DATA_DIR/derived/meeting-minutes/pprompt-sweep/runs/<run-id>" \\
        --out-dir docs/checks/<campaign>/<release-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting  # noqa: E402
from meeting_minutes_agent.metrics.pins import default_metric_pins  # noqa: E402
from meeting_minutes_agent.probes.pattr import load_pattr_manifest  # noqa: E402
from meeting_minutes_agent.probes.pattr_scoring import extract_gold_streams_for_range  # noqa: E402
from meeting_minutes_agent.probes.pprompt import ARM_X1, ARM_X2, ARMS, REFERENCE_CELL  # noqa: E402
from meeting_minutes_agent.probes.pprompt_scoring import (  # noqa: E402
    aggregate_by_arm,
    apply_winner_rule,
    assert_one_shot_output_dir,
    evaluate_all_corrupt_arms,
    score_slice,
)
from meeting_minutes_agent.runreceipt import read_git_state  # noqa: E402


def load_responses(path: Path) -> list[dict]:
    """Every ``outcome == "ok"`` record in one arm's JSONL, in file order.
    A record without ``outcome == "ok"`` (an ``error`` record from a failed
    request) is skipped -- never scored as a reply."""

    if not path.is_file():
        raise FileNotFoundError(f"no responses file for this arm: {path}")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("outcome") == "ok":
            records.append(record)
    return records


def responses_path(responses_dir: Path, arm: str) -> Path:
    return responses_dir / f"{arm}-responses.jsonl"


def score_all_arms(
    pattr_manifest,
    responses_dir: Path,
    resolved_meetings: Mapping[str, object],
    *,
    pins=None,
) -> dict[str, list]:
    """Every arm's per-slice :class:`~.pprompt_scoring.SliceScore` list,
    keyed by arm. Requires a response record for EVERY one of the arm's 24
    slices -- a partial arm (a request that never flew, or errored) raises
    rather than silently scoring fewer than 24 sessions."""

    slice_entries_by_meeting = {
        meeting_id: {entry["index"]: entry for entry in pattr_manifest.slice_entries(meeting_id)}
        for meeting_id in pattr_manifest.selected_meetings
    }

    out: dict[str, list] = {}
    for arm in ARMS:
        records = load_responses(responses_path(responses_dir, arm))
        by_request_id = {r["request_id"]: r for r in records}
        scores = []
        for meeting_id in pattr_manifest.selected_meetings:
            for slice_index, entry in slice_entries_by_meeting[meeting_id].items():
                request_id = f"pprompt-{arm}-{meeting_id}-slice{slice_index:04d}"
                record = by_request_id.get(request_id)
                if record is None:
                    raise RuntimeError(
                        f"arm {arm!r} is missing a flown reply for {request_id!r} in "
                        f"{responses_path(responses_dir, arm)} -- the read requires all 24 slices"
                    )
                start, end = float(entry["start"]), float(entry["end"])
                reference = extract_gold_streams_for_range(resolved_meetings[meeting_id], start=start, end=end)
                scores.append(
                    score_slice(
                        arm,
                        meeting_id,
                        slice_index,
                        reference,
                        record["text"],
                        slice_start=start,
                        slice_end=end,
                        pins=pins,
                    )
                )
        out[arm] = scores
    return out


def build_report_text(*, created_utc: str, study_commit: str, pins_hash: str, meetings, cells, winner, corrupt_verdicts) -> str:
    lines = [
        "P-PROMPT sweep -- registered one-shot scoring read",
        "=" * 78,
        f"created_utc  : {created_utc}",
        f"study_commit : {study_commit}",
        f"pins_hash    : {pins_hash}",
        f"session unit : one transport slice (24 sessions x 14 arms = 336)",
        f"meetings     : {', '.join(meetings)}",
        "",
        "GRID WINNER (mechanical rule, prereg SS4)",
        "-" * 78,
        f"status      : {winner.status}",
        f"winner_arm  : {winner.winner_arm}",
        f"tie_set     : {list(winner.tie_set)}",
        f"eligible    : {list(winner.eligible_arms)}",
        "ranked by mean cpWER:",
    ]
    for arm, cp_wer in winner.ranked_by_cp_wer:
        cell = cells[arm]
        refused = f" orc_refused={cell.n_confusion_refused}/{cell.n_slices}" if cell.n_confusion_refused else ""
        lines.append(
            f"  {arm:6s} mean_cpWER={cp_wer:.4f} mean_confusion={cell.mean_confusion_cost:+.4f} "
            f"mean_compliance={cell.mean_compliance:.4f}{refused}"
        )
    refusal_lines = [
        f"  {s.arm:6s} {s.meeting_id} slice{s.slice_index:04d}: {s.orc_refusal}"
        for cell in cells.values()
        for s in cell.slices
        if s.orc_refusal is not None
    ]
    if refusal_lines:
        lines += [
            "",
            "ORC REFUSALS (confusion term unavailable, cpWER retained; recorded, never dropped)",
            "-" * 78,
            *refusal_lines,
        ]
    lines += [
        "",
        "CORRUPT-CONTEXT VERDICTS (vs reference cell "
        f"{REFERENCE_CELL})",
        "-" * 78,
    ]
    for arm in (ARM_X1, ARM_X2):
        v = corrupt_verdicts[arm]
        lines.append(
            f"  {arm}: {v.verdict} (degradation={v.degradation:+.4f}, "
            f"reference_mean_cpWER={v.reference_mean_cp_wer:.4f}, corrupt_mean_cpWER={v.corrupt_mean_cp_wer:.4f})"
        )
    lines.append("")
    return "\n".join(lines)


def run_read(
    *,
    data_dir: Path,
    pattr_manifest_path: Path,
    responses_dir: Path,
    out_dir: Path,
    force: bool,
    resolved_meetings: Mapping[str, object] | None = None,
) -> dict:
    """``resolved_meetings`` is an injection seam (defaults to ``None``,
    meaning "resolve every selected meeting via :mod:`meeting_minutes_agent.
    corpora.nxt` for real", the production path): a test supplies a small
    hand-built ``{meeting_id: ResolvedMeeting}`` mapping instead, so this
    function's own scoring/winner-rule/verdict wiring is exercisable without
    real AMI annotation bytes."""

    assert_one_shot_output_dir(out_dir, force=force)

    pattr_manifest = load_pattr_manifest(pattr_manifest_path)
    if resolved_meetings is None:
        annotations_root = Path(data_dir) / pattr_manifest.raw["ami_annotations_root_relative"]
        corpus = NxtCorpus(annotations_root)
        resolved_meetings = {
            meeting_id: resolve_meeting(corpus, meeting_id) for meeting_id in pattr_manifest.selected_meetings
        }

    pins = default_metric_pins()
    all_scores = score_all_arms(pattr_manifest, responses_dir, resolved_meetings, pins=pins)
    flat_scores = [s for scores in all_scores.values() for s in scores]
    cells = aggregate_by_arm(flat_scores)

    winner = apply_winner_rule(cells)
    corrupt_verdicts = evaluate_all_corrupt_arms(cells)

    from datetime import datetime, timezone

    created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    git = read_git_state(Path(__file__).resolve().parent.parent)

    verdict = {
        "created_utc": created_utc,
        "study_commit": git.commit,
        "pins_hash": pins.content_hash(),
        "meetings": list(pattr_manifest.selected_meetings),
        "cells": {arm: cell.to_dict() for arm, cell in cells.items()},
        "winner": winner.to_dict(),
        "corrupt_verdicts": {arm: v.to_dict() for arm, v in corrupt_verdicts.items()},
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_text = build_report_text(
        created_utc=created_utc,
        study_commit=git.commit or "<unknown>",
        pins_hash=pins.content_hash(),
        meetings=pattr_manifest.selected_meetings,
        cells=cells,
        winner=winner,
        corrupt_verdicts=corrupt_verdicts,
    )
    (out_dir / "report.txt").write_text(report_text, encoding="utf-8")
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument("--pattr-manifest", required=True, help="frozen P-ATTR manifest JSON")
    parser.add_argument("--responses-dir", required=True, help="directory holding <arm>-responses.jsonl for all 14 arms")
    parser.add_argument("--out-dir", required=True, help="where to write verdict.json + report.txt")
    parser.add_argument("--force", action="store_true", help="overwrite a prior read's output (breaks one-shot discipline)")
    args = parser.parse_args(argv)

    verdict = run_read(
        data_dir=Path(args.data_dir),
        pattr_manifest_path=Path(args.pattr_manifest),
        responses_dir=Path(args.responses_dir),
        out_dir=Path(args.out_dir),
        force=args.force,
    )
    print(json.dumps({"winner": verdict["winner"], "corrupt_verdicts": verdict["corrupt_verdicts"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
