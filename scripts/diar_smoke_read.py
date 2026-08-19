#!/usr/bin/env python3
"""DIAR-SMOKE registered one-shot scoring read.

Reads a flight's RTTM outputs (``scripts/launch_diar_smoke.py``'s
``<flight-dir>/rttm/<arm>/<meeting_id>.rttm``) plus the NXT oracle turn
table (resolved via :mod:`meeting_minutes_agent.corpora.nxt` -- SCORING-SIDE
reference ONLY, prereg SS3), computes every registered metric
(:mod:`meeting_minutes_agent.probes.diar_smoke_scoring`), and writes
``verdict.json`` + ``report.txt`` to ``--out-dir``, mirroring the P-ATTR/
P-PROMPT read pair's own layout and one-shot guard
(``scripts/pprompt_read.py``).

Real I/O, zero model/tool contact: this script reads already-flown RTTM
files (never invokes a tool subprocess), resolves the AMI gold
transcript for the registered six meetings via
:mod:`meeting_minutes_agent.corpora.nxt` (already-licensed, already-acquired
annotation XML -- the same corpus access every other scoring/read path in
this repository uses), and reads each registered meeting's Mix-Headset WAV
for the two audio-derived slicer inputs the real transport packer always
receives (header duration + signal-derived energy pause transitions --
never gold, never a model contact).

Usage::

    python scripts/diar_smoke_read.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --flight-dir docs/checks/<campaign>/<release-id>-flight \\
        --out-dir docs/checks/<campaign>/<release-id>-read
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.adapters import turn_table_from_resolved_meeting  # noqa: E402
from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.chunking.slicer import detect_energy_pause_transitions, read_audio_duration  # noqa: E402
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting  # noqa: E402
from meeting_minutes_agent.probes.diar_smoke import (  # noqa: E402
    REGISTERED_MEETINGS,
    REQUIRED_ARMS,
    require_meeting_audio_path,
)
from meeting_minutes_agent.probes.diar_smoke_scoring import (  # noqa: E402
    CONVENTION_NO_COLLAR_WITH_OVERLAP,
    assert_one_shot_output_dir,
    evaluate_diar_smoke_verdict,
    pool_meeting_metrics_by_convention,
    score_meeting,
)
from meeting_minutes_agent.runreceipt import read_git_state  # noqa: E402

DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE = "datasets/ami/annotations/manual_1.6.2"


def rttm_path_for(flight_dir: Path, arm: str, meeting_id: str) -> Path:
    return flight_dir / "rttm" / arm / f"{meeting_id}.rttm"


def load_hypothesis_turns(flight_dir: Path, arm: str, meeting_id: str):
    """The RTTM-parsed tool turn table for one ``(arm, meeting_id)``, or
    ``None`` if the flight never produced one (no RTTM file on disk) --
    that arm/meeting counts toward ``a_load_failed``/``b_load_failed``,
    never toward a fabricated zero-turn score."""

    path = rttm_path_for(flight_dir, arm, meeting_id)
    if not path.is_file():
        return None
    return parse_rttm_file(path)


def audio_derived_slicer_inputs(data_dir: Path, meeting_id: str) -> tuple[float, tuple[float, ...]]:
    """The two audio-derived inputs the REAL transport packer always
    receives (``build_slice_manifest`` / ``scripts/build_pattr_manifest.py``
    ``build_meeting_entry``): the meeting WAV's header duration and its
    signal-derived energy pause transitions. Without them a >120 s
    boundary-free stretch in a turn table cannot fall back to a pause split
    and trips the transport hard cap (``TransportBoundViolation`` -- the
    2026-08-19 read attempt-1 crash, first hit on TS3004d's ORACLE turn
    table together with the slicer's interior gap-tiling room-cap fix;
    ``docs/checks/2026-08-18-diar-smoke-read/attempt-1-transportbound-crash.log``).
    Signal-derived only: never gold annotation, never a model contact."""

    audio_path = require_meeting_audio_path(meeting_id, data_dir=data_dir)
    return read_audio_duration(audio_path), detect_energy_pause_transitions(audio_path)


def build_report_text(document: Mapping[str, Any]) -> str:
    verdict = document["verdict"]
    lines = [
        "DIAR-SMOKE -- registered one-shot scoring read",
        "=" * 78,
        f"created_utc  : {document['created_utc']}",
        f"study_commit : {document['study_commit']}",
        f"meetings     : {', '.join(document['meetings'])}",
        f"arms         : {', '.join(document['arms'])}",
        "",
        "VERDICT (mechanical, prereg SS5)",
        "-" * 78,
        f"status : {verdict['status']}",
        f"DER(A) [no collar, with overlap] : {verdict['der_a_no_collar_overlap']}",
        f"DER(B) [no collar, with overlap] : {verdict['der_b_no_collar_overlap']}",
        f"best_arm : {verdict['best_arm']}  best_arm_der : {verdict['best_arm_der']}",
        "clauses:",
    ]
    for name, clause in verdict["clauses"].items():
        lines.append(f"  {name:24s} fires={clause['fires']!s:5s} margin={clause['margin']}  {clause['detail']}")
    lines += ["", "IN-DOMAIN CAVEAT (carried in ALL outcomes)", "-" * 78, verdict["in_domain_caveat"], ""]
    return "\n".join(lines)


def run_read(
    *,
    data_dir: Path,
    flight_dir: Path,
    out_dir: Path,
    force: bool,
    meetings: Sequence[str] = REGISTERED_MEETINGS,
    arms: Sequence[str] = REQUIRED_ARMS,
    ami_annotations_root_relative: str = DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE,
    resolved_meetings: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """``resolved_meetings`` is an injection seam (defaults to ``None``,
    meaning "resolve every meeting for real": the NXT gold transcript via
    :mod:`meeting_minutes_agent.corpora.nxt` AND the meeting WAV's
    audio-derived slicer inputs via :func:`audio_derived_slicer_inputs`): a
    test supplies a small hand-built ``{meeting_id: ResolvedMeeting}``
    mapping instead, exercising this function's scoring/pooling/verdict
    wiring without real AMI annotation or audio bytes (the injected path
    scores packing without duration/pause-transition fallbacks)."""

    assert_one_shot_output_dir(out_dir, force=force)

    slicer_inputs: dict[str, tuple[float | None, tuple[float, ...]]]
    if resolved_meetings is None:
        annotations_root = Path(data_dir) / ami_annotations_root_relative
        corpus = NxtCorpus(annotations_root)
        resolved_meetings = {m: resolve_meeting(corpus, m) for m in meetings}
        slicer_inputs = {m: audio_derived_slicer_inputs(Path(data_dir), m) for m in meetings}
    else:
        slicer_inputs = {m: (None, ()) for m in meetings}

    per_arm_meeting_metrics: dict[str, dict[str, Any]] = {arm: {} for arm in arms}
    per_arm_load_failed: dict[str, bool] = {arm: True for arm in arms}
    per_meeting_records: dict[str, dict[str, Any]] = {}

    for meeting_id in meetings:
        oracle_turns = turn_table_from_resolved_meeting(resolved_meetings[meeting_id])
        meeting_record: dict[str, Any] = {}
        for arm in arms:
            hypothesis_turns = load_hypothesis_turns(flight_dir, arm, meeting_id)
            if not hypothesis_turns:
                meeting_record[arm] = None
                continue
            per_arm_load_failed[arm] = False
            total_duration_s, pause_transitions = slicer_inputs[meeting_id]
            metrics = score_meeting(
                meeting_id,
                oracle_turns,
                hypothesis_turns,
                total_duration_s=total_duration_s,
                fallback_pause_transitions=pause_transitions,
            )
            per_arm_meeting_metrics[arm][meeting_id] = metrics
            meeting_record[arm] = metrics.to_dict()
        per_meeting_records[meeting_id] = meeting_record

    pooled: dict[str, Any] = {}
    for arm in arms:
        scored = list(per_arm_meeting_metrics[arm].values())
        pooled[arm] = pool_meeting_metrics_by_convention(scored, CONVENTION_NO_COLLAR_WITH_OVERLAP) if scored else None

    der_a = pooled.get("A").der if pooled.get("A") is not None else None
    der_b = pooled.get("B").der if pooled.get("B") is not None else None
    verdict = evaluate_diar_smoke_verdict(
        der_a=der_a,
        der_b=der_b,
        a_load_failed=per_arm_load_failed.get("A", True),
        b_load_failed=per_arm_load_failed.get("B", True),
    )

    created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    git = read_git_state(Path(__file__).resolve().parent.parent)

    document = {
        "created_utc": created_utc,
        "study_commit": git.commit,
        "meetings": list(meetings),
        "arms": list(arms),
        "per_meeting": per_meeting_records,
        "audio_slicer_inputs": {
            m: {"total_duration_s": slicer_inputs[m][0], "n_pause_transitions": len(slicer_inputs[m][1])}
            for m in meetings
        },
        "pooled_no_collar_with_overlap": {a: (v.to_dict() if v is not None else None) for a, v in pooled.items()},
        "verdict": verdict.to_dict(),
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdict.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "report.txt").write_text(build_report_text(document), encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument("--flight-dir", required=True, help="the runner's --out-dir")
    parser.add_argument("--out-dir", required=True, help="where to write verdict.json + report.txt")
    parser.add_argument(
        "--ami-annotations-root-relative", default=DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE
    )
    parser.add_argument("--arms", nargs="+", default=list(REQUIRED_ARMS))
    parser.add_argument("--meetings", nargs="+", default=list(REGISTERED_MEETINGS))
    parser.add_argument("--force", action="store_true", help="overwrite a prior read's output (breaks one-shot discipline)")
    args = parser.parse_args(argv)

    document = run_read(
        data_dir=Path(args.data_dir),
        flight_dir=Path(args.flight_dir),
        out_dir=Path(args.out_dir),
        force=args.force,
        meetings=list(args.meetings),
        arms=list(args.arms),
        ami_annotations_root_relative=args.ami_annotations_root_relative,
    )
    print(json.dumps({"verdict": document["verdict"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
