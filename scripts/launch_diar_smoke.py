#!/usr/bin/env python3
"""DIAR-SMOKE flight launcher -- MACHINERY ONLY.

This engineering mission builds and import/wiring-verifies this script; it
never runs a tool subprocess, downloads a checkpoint, or touches a GPU (task
scope: "no model runs, no downloads, no GPU, no installs"). A later,
separate flight mission runs it against real pinned tools once the
acquisition prerequisite (``docs/readiness/2026-08-18-diar-smoke-
preregistration.md`` SS6) has landed.

Wires: an ``--arm-config`` JSON (per-arm :class:`~meeting_minutes_agent.
chunking.diarization.ToolDiarizationConfig`) -> the registered six-meeting
roster -> :class:`~meeting_minutes_agent.chunking.diarization.
PinnedToolDiarization` per ``(arm, meeting)`` -> a per-arm/meeting receipt
(wall seconds, an advisory GPU-utilization snapshot, and every tool contact
record) -> a flight-level summary, mirroring the archive-ready layout of
``docs/checks/2026-08-18-pattr-smoke-flight/``.

``--summary-only`` is the one mode safe to run right now: it prints the
registered roster/arms/ceilings and exits -- no tool contact, no
``--arm-config`` required.

Budget guard (prereg SS7: <=1.0 GPU-h, <=2h wall): checked BEFORE every
contact against usage already recorded from completed ones (a diarization
tool's wall time is not knowable in advance, unlike an LLM request's
audio-seconds); a breach stops the flight and still writes the summary so
far, rather than losing what already ran.

Resume (``--resume``): a ``(arm, meeting)`` whose receipt already exists AND
records ``ok: true`` is skipped; an errored prior attempt is retried --
mirrors ``scripts/launch_pattr_smoke.py``'s own resume semantics. Every
receipt write is fsynced before the next contact starts, so a crash costs
at most the in-flight contact.

Usage (safe right now -- no tool contact)::

    python scripts/launch_diar_smoke.py --data-dir "$SPEECHRL_DATA_DIR" --summary-only

Usage (a real flight, once ``--arm-config`` names a pinned tool)::

    python scripts/launch_diar_smoke.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --arm-config configs/probes/diar-smoke/<...>.json \\
        --arms A B \\
        --out-dir docs/checks/<campaign>/<release-id>-flight \\
        --resume
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.diarization import PinnedToolDiarization  # noqa: E402
from meeting_minutes_agent.probes.diar_smoke import (  # noqa: E402
    ALL_ARMS,
    ARM_C,
    DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    GPU_HOUR_CEILING,
    REGISTERED_MEETINGS,
    REQUIRED_ARMS,
    WALL_HOUR_CEILING,
    SmokeBudget,
    SmokeBudgetExceeded,
    assert_registered_meetings_exposable,
    estimate_gpu_seconds,
    load_arm_configs,
    query_gpu_utilization_snapshot,
    require_meeting_audio_path,
)


def receipt_path(out_dir: Path, arm: str, meeting_id: str) -> Path:
    return out_dir / "receipts" / arm / f"{meeting_id}-receipt.json"


def rttm_dir(out_dir: Path, arm: str) -> Path:
    return out_dir / "rttm" / arm


def _fsync_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def already_done(out_dir: Path, arm: str, meeting_id: str) -> bool:
    """Resume support: a prior receipt recording ``ok: true`` is done and
    is skipped on ``--resume``; a missing, unparsable, or errored receipt is
    NOT done -- it (or the meeting/arm) will be retried."""

    path = receipt_path(out_dir, arm, meeting_id)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return bool(data.get("ok"))


def run_one(
    arm: str,
    meeting_id: str,
    *,
    data_dir: Path,
    arm_configs: Mapping[str, object],
    out_dir: Path,
    budget: SmokeBudget,
    ami_audio_root_relative: str,
    run_subprocess: Callable[..., object] | None = None,
    query_gpu: Callable[[], Mapping[str, float] | None] | None = None,
) -> dict[str, Any]:
    """One ``(arm, meeting_id)`` pinned-tool contact: budget check, resolve
    the Mix-Headset WAV, call :class:`PinnedToolDiarization`, sample GPU
    utilization, and write a fsynced receipt. Raises
    :class:`SmokeBudgetExceeded` BEFORE the contact if the ceiling is
    already reached; every other failure (a bad audio path, a tool
    invocation error) is caught and recorded ON the receipt rather than
    propagated, so one meeting/arm failing never aborts the rest of the
    flight."""

    budget.check_before_contact()
    audio_path = require_meeting_audio_path(
        meeting_id, data_dir=data_dir, ami_audio_root_relative=ami_audio_root_relative
    )
    backend = PinnedToolDiarization(arm_configs[arm], output_dir=rttm_dir(out_dir, arm), run_subprocess=run_subprocess)

    started = time.monotonic()
    error_text: str | None = None
    n_turns = 0
    try:
        result = backend.diarize(meeting_id, audio_path)
        n_turns = len(result.turns)
    except Exception as error:  # noqa: BLE001 -- recorded on the receipt, never silently swallowed
        error_text = f"{type(error).__name__}: {error}"
    wall_seconds = time.monotonic() - started

    snapshot = (query_gpu or query_gpu_utilization_snapshot)()
    gpu_seconds = estimate_gpu_seconds(wall_seconds, snapshot)
    budget.record(wall_seconds=wall_seconds, gpu_seconds=gpu_seconds)

    receipt = {
        "arm": arm,
        "meeting_id": meeting_id,
        "audio_path": str(audio_path),
        "ok": error_text is None,
        "error": error_text,
        "n_turns": n_turns,
        "wall_seconds": wall_seconds,
        "gpu_seconds_estimate": gpu_seconds,
        "gpu_snapshot": snapshot,
        "rttm_path": str(rttm_dir(out_dir, arm) / f"{meeting_id}.rttm"),
        "contacts": [c.to_dict() for c in backend.contact_log],
        "budget_after": budget.to_dict(),
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
    }
    _fsync_write_json(receipt_path(out_dir, arm, meeting_id), receipt)
    return receipt


def build_flight_summary(outcomes: list[dict[str, Any]], *, budget: SmokeBudget, stopped_reason: str | None) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "n_contacts": len(outcomes),
        "n_ok": sum(1 for o in outcomes if o["ok"]),
        "n_error": sum(1 for o in outcomes if not o["ok"]),
        "budget": budget.to_dict(),
        "ceilings": {"max_gpu_hours": GPU_HOUR_CEILING, "max_wall_hours": WALL_HOUR_CEILING},
        "stopped_reason": stopped_reason,
        "outcomes": outcomes,
    }


def run_flight(
    *,
    data_dir: Path,
    arm_configs: Mapping[str, object],
    arms: list[str],
    meetings: list[str],
    out_dir: Path,
    resume: bool,
    ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    skip_registry_check: bool = False,
    run_subprocess: Callable[..., object] | None = None,
    query_gpu: Callable[[], Mapping[str, float] | None] | None = None,
    budget: SmokeBudget | None = None,
) -> dict[str, Any]:
    """The whole flight loop: every ``(meeting, arm)`` pair, in meeting-major
    order, budget-guarded and resumable. ``skip_registry_check`` is a test
    seam only (the committed AMI role registry is real repository data; a
    unit test exercising this loop's own budget/resume/receipt logic on a
    synthetic meeting id should not have to also carry a registry
    fixture) -- a real flight always leaves it ``False``. ``budget`` is
    likewise an injection seam (defaults to a fresh :class:`SmokeBudget`) so
    a test can pre-load usage or a tight ceiling to exercise the
    budget-stop path deterministically, without depending on real wall-clock
    timing."""

    if not skip_registry_check:
        assert_registered_meetings_exposable(meetings)

    if budget is None:
        budget = SmokeBudget()
    outcomes: list[dict[str, Any]] = []
    for meeting_id in meetings:
        for arm in arms:
            if resume and already_done(out_dir, arm, meeting_id):
                print(f"resume: skipping {arm}/{meeting_id} (already ok)", file=sys.stderr)
                continue
            try:
                receipt = run_one(
                    arm,
                    meeting_id,
                    data_dir=data_dir,
                    arm_configs=arm_configs,
                    out_dir=out_dir,
                    budget=budget,
                    ami_audio_root_relative=ami_audio_root_relative,
                    run_subprocess=run_subprocess,
                    query_gpu=query_gpu,
                )
            except SmokeBudgetExceeded as error:
                print(f"BUDGET STOP before {arm}/{meeting_id}: {error}", file=sys.stderr)
                summary = build_flight_summary(outcomes, budget=budget, stopped_reason=str(error))
                _fsync_write_json(out_dir / "flight-summary.json", summary)
                return summary
            outcomes.append(receipt)

    summary = build_flight_summary(outcomes, budget=budget, stopped_reason=None)
    _fsync_write_json(out_dir / "flight-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument(
        "--arm-config", default=None,
        help='JSON {"A": {...}, "B": {...}, "C": {...}}, each value a ToolDiarizationConfig.from_dict input',
    )
    parser.add_argument("--arms", nargs="+", default=list(REQUIRED_ARMS), choices=ALL_ARMS)
    parser.add_argument("--meetings", nargs="+", default=list(REGISTERED_MEETINGS))
    parser.add_argument("--out-dir", default=None, help="archive root: <out-dir>/{rttm,receipts}/<arm>/... + flight-summary.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ami-audio-root-relative", default=DEFAULT_AMI_AUDIO_ROOT_RELATIVE)
    parser.add_argument(
        "--include-arm-c", action="store_true",
        help="also run the contingent Arm C (flag-gated, prereg SS2) when --arms names it",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="print the registered roster/arms/ceilings and exit -- no tool contact, no --arm-config required",
    )
    args = parser.parse_args(argv)

    if args.summary_only:
        print(
            json.dumps(
                {
                    "meetings": list(REGISTERED_MEETINGS),
                    "required_arms": list(REQUIRED_ARMS),
                    "all_arms": list(ALL_ARMS),
                    "gpu_hour_ceiling": GPU_HOUR_CEILING,
                    "wall_hour_ceiling": WALL_HOUR_CEILING,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    arms = list(dict.fromkeys(args.arms))
    if ARM_C in arms and not args.include_arm_c:
        parser.error("Arm C is contingent and flag-gated: pass --include-arm-c to run it")

    missing = [name for name, value in (("--arm-config", args.arm_config), ("--out-dir", args.out_dir)) if value is None]
    if missing:
        parser.error(f"the following arguments are required for a real flight (omit only with --summary-only): {missing}")

    arm_configs = load_arm_configs(args.arm_config)
    missing_cfg = [a for a in arms if a not in arm_configs]
    if missing_cfg:
        parser.error(f"--arm-config {args.arm_config!r} carries no configuration for arm(s) {missing_cfg}")

    summary = run_flight(
        data_dir=Path(args.data_dir),
        arm_configs=arm_configs,
        arms=arms,
        meetings=list(args.meetings),
        out_dir=Path(args.out_dir),
        resume=args.resume,
        ami_audio_root_relative=args.ami_audio_root_relative,
    )
    print(
        json.dumps(
            {"n_ok": summary["n_ok"], "n_error": summary["n_error"], "stopped_reason": summary["stopped_reason"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
