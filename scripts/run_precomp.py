#!/usr/bin/env python3
"""PRECOMP wave runner -- MACHINERY ONLY.

This engineering mission builds and import/wiring-verifies this script; it
never runs a diar subprocess, contacts the frozen core, or downloads
anything (task scope: "MACHINERY ONLY -- no diar runs, no core contact, no
downloads"). A later, separate, coordinator-reviewed mission runs it for
real, per ``docs/readiness/2026-08-19-precomp-preregistration.md``
("REGISTERED -- wave-1 flyable once the machinery lands").

Wires: the wave roster (:mod:`meeting_minutes_agent.precomp.roster`,
fail-closed exposure gate applied unconditionally, to BOTH the default
roster and any operator-supplied ``--meetings`` override) -> the
per-meeting pipeline (:mod:`meeting_minutes_agent.precomp.pipeline.run_meeting`:
pinned Arm B diar -> tool + oracle slice plans -> CPU slice cutting ->
featcache encode-warm pass) -> a fsynced per-meeting receipt
(:mod:`meeting_minutes_agent.precomp.receipts`) -> a wave summary.
``--server-url`` names an ALREADY-RUNNING ``llama-server``: this runner
never starts, stops, or health-checks a server process itself (task
instruction: "the runner never starts the server itself").

``--summary-only`` is the one mode safe to run right now: it prints the
resolved wave roster (after the fail-closed exposure gate) and the wave's
registered ceilings, and exits -- no diar contact, no server contact, no
``--arm-config``/``--server-url``/``--model-path``/``--model-sha256``
required.

Resume (``--resume``): a meeting whose receipt already exists AND is
complete+verified (``schema_version`` matches, ``ok: true``) is skipped --
"resumable at meeting granularity" (prereg SS2/SS6). Every receipt write is
fsynced before the next meeting starts, so a crash costs at most the
in-flight meeting.

Budget guard (prereg SS4): a :class:`~meeting_minutes_agent.precomp.
budget.PrecompBudget` sized to the wave's registered ceilings is shared
across every meeting; a :class:`~meeting_minutes_agent.precomp.budget.
PrecompBudgetExceeded` stops the wave immediately and still writes the wave
summary for whatever already completed, rather than losing it. Before this
process's own loop runs any meeting, the budget is pre-charged
(:meth:`~meeting_minutes_agent.precomp.budget.PrecompBudget.precharge`)
with wave-cumulative usage re-derived from every receipt already on disk
under ``--out-dir`` -- native support for the same reconciliation the
wave-1 operator wrapper's ``docs/checks/2026-08-19-precomp-wave1/
budget_ledger.py`` performed externally, once per meeting-invocation, back
when this runner had no in-flight stop hook. That external per-process
workaround is retired by ``--stop-file <path>``: checked before every
meeting inside a single, long-lived invocation, its presence ends the wave
cleanly (whatever completed is already receipted and fsynced; the wave
summary is written; the process exits 0) and the run resumes at meeting
granularity with ``--resume``, no external wrapper required.

Usage (safe right now -- no diar contact, no server contact)::

    python scripts/run_precomp.py --wave 1 --data-dir "$SPEECHRL_DATA_DIR" --summary-only

Usage (a real wave, once ``--arm-config``/``--server-url`` name a pinned
Arm B tool and an already-running server)::

    python scripts/run_precomp.py \\
        --wave 1 --data-dir "$SPEECHRL_DATA_DIR" \\
        --arm-config configs/probes/diar-smoke/<...>.json \\
        --server-url http://127.0.0.1:8080 \\
        --model-path /home/chao/models/<pinned-gguf> --model-sha256 <sha256> \\
        --out-dir docs/checks/2026-08-19-precomp-wave1 --resume
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.diarization import ToolDiarizationConfig  # noqa: E402
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.featcache import campaign_cache_dir  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.chunking.constants import TRANSPORT_SLICE_MAX_S  # noqa: E402
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.precomp.budget import (  # noqa: E402
    PrecompBudget,
    PrecompBudgetExceeded,
    ceilings_for_wave,
)
from meeting_minutes_agent.precomp.pipeline import (  # noqa: E402
    DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE,
    DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    DEFAULT_WORKERS,
    query_gpu_utilization_snapshot,
    require_meeting_audio_path,
    run_meeting,
)
from meeting_minutes_agent.precomp.receipts import (  # noqa: E402
    already_done,
    build_wave_summary,
    write_meeting_receipt,
    write_wave_summary,
)
from meeting_minutes_agent.precomp.roster import (  # noqa: E402
    WAVES,
    assert_wave_roster_admissible,
    default_wave_meetings,
)
from meeting_minutes_agent.probes.diar_smoke import ArmConfigError  # noqa: E402

#: Match the warm cache directory the server writes and G1 reads
#: (``<root>/ami-q4km/`` -- the same per-dataset directory the P-ATTR/
#: P-PROMPT meeting flights used, `docs/checks/2026-08-19-precomp-wave1/
#: README.md`'s identity table). Overridable per-invocation via
#: ``--featcache-dataset``/``--encoder``; only the *default* changes here.
DEFAULT_FEATCACHE_DATASET = "ami"
DEFAULT_ENCODER_ID = "q4km"
DEFAULT_DERIVED_ROOT_RELATIVE = "derived/meeting-minutes/precomp"
DEFAULT_ENCODE_MAX_TOKENS = 1
REPO_ROOT = Path(__file__).resolve().parent.parent


def default_out_dir(wave: int) -> Path:
    return REPO_ROOT / "docs" / "checks" / f"2026-08-19-precomp-wave{wave}"


def load_arm_b_config(path: Path | str) -> ToolDiarizationConfig:
    """Load the pinned Arm B :class:`ToolDiarizationConfig` from an
    ``--arm-config`` JSON. PRECOMP flies Arm B only (TOOL-LOCKED(B) --
    ``docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md``):
    unlike ``scripts/launch_diar_smoke.py``'s multi-arm loader, this
    refuses a file with no ``"B"`` key rather than also requiring ``"A"``
    (a real PRECOMP arm-config, per the smoke tooling's own read-only
    reference pattern, carries only the arms it needs)."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ArmConfigError(f"--arm-config {path} must be a JSON object keyed by arm letter, got {type(document).__name__}")
    if "B" not in document:
        raise ArmConfigError(f"--arm-config {path} carries no 'B' arm entry -- PRECOMP flies the pinned Arm B only")
    return ToolDiarizationConfig.from_dict(document["B"])


def rttm_dir(derived_root: Path) -> Path:
    return derived_root / "rttm"


def tool_slice_dir(derived_root: Path, meeting_id: str) -> Path:
    return derived_root / "slices" / "tool" / meeting_id


def oracle_slice_dir(derived_root: Path, meeting_id: str) -> Path:
    return derived_root / "slices" / "oracle" / meeting_id


def load_wave_receipts(out_dir: Path) -> list[dict[str, Any]]:
    """Every per-meeting receipt already on disk under ``out_dir/receipts/``,
    parsed as JSON -- the wave-1 operator wrapper's own
    ``docs/checks/2026-08-19-precomp-wave1/budget_ledger.py::load_receipts``,
    ported into the runner itself so :func:`run_wave` can precharge a
    fresh :class:`~meeting_minutes_agent.precomp.budget.PrecompBudget`
    from them on startup. An unparsable or non-object file is skipped
    rather than raising -- never expected from this runner's own fsynced
    ``write_meeting_receipt``, but a resumed wave's output directory is
    otherwise untrusted input, exactly as that operator script treated
    it."""

    receipts_dir = Path(out_dir) / "receipts"
    if not receipts_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("*-receipt.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def run_wave(
    *,
    wave: int,
    data_dir: Path,
    meetings: list[str],
    tool_config: ToolDiarizationConfig,
    transport: LlamaServerTransport,
    out_dir: Path,
    derived_root: Path,
    cache_dir: Path,
    resume: bool,
    workers: int = DEFAULT_WORKERS,
    encode_max_tokens: int = DEFAULT_ENCODE_MAX_TOKENS,
    ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    ami_annotations_root_relative: str = DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE,
    skip_roster_check: bool = False,
    run_subprocess: Any | None = None,
    query_gpu: Any | None = None,
    materialize_fn: Any | None = None,
    flight_receipt: FlightReceipt | None = None,
    budget: PrecompBudget | None = None,
    stop_file: Path | str | None = None,
) -> dict[str, Any]:
    """The whole wave loop: every meeting, in sorted order, budget-guarded
    and resumable at meeting granularity. ``skip_roster_check`` is a test
    seam only (mirrors ``scripts/launch_diar_smoke.py::run_flight``'s own
    ``skip_registry_check``) -- a real wave always leaves it ``False``.

    When ``budget`` is not supplied, the fresh, all-zero
    :class:`~meeting_minutes_agent.precomp.budget.PrecompBudget` this
    function builds is pre-charged (:meth:`~.budget.PrecompBudget.precharge`)
    with wave-cumulative usage re-derived from every receipt already under
    ``out_dir`` (:func:`load_wave_receipts`) BEFORE the loop below runs any
    meeting, then checked (:meth:`~.budget.PrecompBudget.check_all`) --
    fail-closed, exactly like a mid-wave :class:`PrecompBudgetExceeded`,
    including the same wave-summary write and clean return. A caller
    supplying its own ``budget`` (a test seam, matching ``run_subprocess``/
    ``query_gpu``/``materialize_fn`` above) opts out of precharging
    entirely -- that budget is used exactly as given.

    ``stop_file``, checked before every meeting (including the first), is
    the native replacement for the wave-1 operator wrapper's external
    per-meeting invocation loop (``docs/checks/2026-08-19-precomp-wave1/
    README.md``'s "Deviation recorded for coordinator review"): its mere
    presence ends the wave cleanly -- every receipt already written stays
    fsynced and complete, a wave summary is written for whatever finished,
    and the run resumes at meeting granularity with ``--resume``. The file
    itself is never deleted or otherwise touched here; clearing it between
    waves is the operator's job."""

    if not skip_roster_check:
        assert_wave_roster_admissible(meetings)

    if budget is None:
        budget = PrecompBudget(ceilings_for_wave(wave))
        budget.precharge(load_wave_receipts(out_dir))
        try:
            budget.check_all()
        except PrecompBudgetExceeded as error:
            print(f"BUDGET STOP before the wave starts (re-derived from existing receipts): {error}", file=sys.stderr)
            summary = build_wave_summary([], wave=wave, budget_totals=budget.to_dict(), stopped_reason=str(error))
            write_wave_summary(out_dir, summary)
            return summary
    nxt_corpus = NxtCorpus(data_dir / ami_annotations_root_relative)

    kwargs: dict[str, Any] = {}
    if materialize_fn is not None:
        kwargs["materialize_fn"] = materialize_fn

    outcomes: list[dict[str, Any]] = []
    for meeting_id in sorted(meetings):
        if stop_file is not None and Path(stop_file).is_file():
            print(f"stop-file present ({stop_file}): yielding before {meeting_id}", file=sys.stderr)
            summary = build_wave_summary(
                outcomes,
                wave=wave,
                budget_totals=budget.to_dict(),
                stopped_reason=f"stop-file present at {stop_file}, yielded before {meeting_id}",
            )
            write_wave_summary(out_dir, summary)
            return summary
        if resume and already_done(out_dir, meeting_id):
            print(f"resume: skipping {meeting_id} (already ok)", file=sys.stderr)
            continue
        audio_path = require_meeting_audio_path(
            meeting_id, data_dir=data_dir, ami_audio_root_relative=ami_audio_root_relative
        )
        try:
            receipt = run_meeting(
                meeting_id,
                wave=wave,
                audio_path=audio_path,
                tool_config=tool_config,
                nxt_corpus=nxt_corpus,
                rttm_dir=rttm_dir(derived_root),
                tool_slice_dir=tool_slice_dir(derived_root, meeting_id),
                oracle_slice_dir=oracle_slice_dir(derived_root, meeting_id),
                transport=transport,
                budget=budget,
                cache_dir=cache_dir,
                workers=workers,
                encode_max_tokens=encode_max_tokens,
                run_subprocess=run_subprocess,
                query_gpu=query_gpu,
                flight_receipt=flight_receipt,
                **kwargs,
            )
        except PrecompBudgetExceeded as error:
            print(f"BUDGET STOP before {meeting_id}: {error}", file=sys.stderr)
            summary = build_wave_summary(outcomes, wave=wave, budget_totals=budget.to_dict(), stopped_reason=str(error))
            write_wave_summary(out_dir, summary)
            return summary
        write_meeting_receipt(out_dir, receipt)
        outcomes.append(receipt)

    summary = build_wave_summary(outcomes, wave=wave, budget_totals=budget.to_dict(), stopped_reason=None)
    write_wave_summary(out_dir, summary)
    return summary


def build_transport(
    *, base_url: str, model_path: str, model_sha256: str, max_encode_calls: int, slots: int, timeout_seconds: float
) -> tuple[LlamaServerTransport, FlightReceipt]:
    """Transport-layer safety net + audit ledger, exactly like
    ``scripts/launch_pattr_smoke.py::build_transport_and_receipt``: a
    :class:`~meeting_minutes_agent.client.budgets.CallBudget` sized
    generously (every PRECOMP call carries at most one transport slice, so
    ``max_encode_calls * TRANSPORT_SLICE_MAX_S`` upper-bounds total audio
    seconds) as the transport-level backstop underneath
    :class:`~meeting_minutes_agent.precomp.budget.PrecompBudget`'s own,
    PRECOMP-specific ceilings."""

    call_budget = CallBudget(
        BudgetLimits(max_calls=max_encode_calls, max_audio_seconds=max_encode_calls * TRANSPORT_SLICE_MAX_S)
    )
    server_identity = ServerIdentity(
        base_url=base_url, model_files=(ModelFileRef(path=model_path, sha256=model_sha256),), slots=slots
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=base_url, slots=slots, timeout_seconds=timeout_seconds), call_budget
    )
    flight_receipt = FlightReceipt(server_identity, call_budget)
    return transport, flight_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wave", type=int, required=True, choices=WAVES)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument(
        "--meetings", nargs="+", default=None,
        help="override the registered default wave roster (still passed through the fail-closed exposure gate)",
    )
    parser.add_argument("--arm-config", default=None, help='JSON {"B": {...}}, a ToolDiarizationConfig.from_dict input for the pinned Arm B tool')
    parser.add_argument("--server-url", default=None, help="ALREADY-RUNNING llama-server base URL -- this runner never starts one")
    parser.add_argument("--model-path", default=None, help="GGUF path as configured (receipt identity only)")
    parser.add_argument("--model-sha256", default=None, help="GGUF sha256 as configured (receipt identity only)")
    parser.add_argument("--slots", type=int, default=4)
    parser.add_argument("--out-dir", default=None, help="receipts root; defaults to docs/checks/2026-08-19-precomp-wave<wave>/")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="CPU slice-cutting worker pool size")
    parser.add_argument("--encode-max-tokens", type=int, default=DEFAULT_ENCODE_MAX_TOKENS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--stop-file", default=None,
        help=(
            "path checked for existence before every meeting (including the first); its mere presence "
            "ends the wave cleanly (receipts already written stay complete, a wave summary is written, "
            "exit 0) -- the native replacement for the wave-1 per-meeting invocation-loop workaround. "
            "Resume with --resume once the file is cleared or gone."
        ),
    )
    parser.add_argument("--ami-audio-root-relative", default=DEFAULT_AMI_AUDIO_ROOT_RELATIVE)
    parser.add_argument("--ami-annotations-root-relative", default=DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE)
    parser.add_argument(
        "--derived-root-relative", default=DEFAULT_DERIVED_ROOT_RELATIVE,
        help="data-root-relative root for rttm/slice bytes -- never committed",
    )
    parser.add_argument("--featcache-dataset", default=DEFAULT_FEATCACHE_DATASET)
    parser.add_argument("--encoder", default=DEFAULT_ENCODER_ID)
    parser.add_argument("--featcache-root", default=None, help="override the feature-cache root (MMA_FEAT_CACHE_ROOT default otherwise)")
    parser.add_argument("--timeout-seconds", type=float, default=300.0, help="per-request HTTP timeout")
    parser.add_argument(
        "--summary-only", action="store_true",
        help="print the resolved wave roster and ceilings and exit -- no diar/server contact required",
    )
    args = parser.parse_args(argv)

    ceilings = ceilings_for_wave(args.wave)
    meetings = list(args.meetings) if args.meetings is not None else list(default_wave_meetings(args.wave))

    if args.summary_only:
        assert_wave_roster_admissible(meetings)
        print(
            json.dumps(
                {"wave": args.wave, "n_meetings": len(meetings), "meetings": sorted(meetings), "ceilings": ceilings.to_dict()},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    missing = [
        name
        for name, value in (
            ("--arm-config", args.arm_config),
            ("--server-url", args.server_url),
            ("--model-path", args.model_path),
            ("--model-sha256", args.model_sha256),
        )
        if value is None
    ]
    if missing:
        parser.error(f"the following arguments are required for a real wave (omit only with --summary-only): {missing}")

    tool_config = load_arm_b_config(args.arm_config)
    data_dir = Path(args.data_dir)
    derived_root = data_dir / args.derived_root_relative
    out_dir = Path(args.out_dir) if args.out_dir is not None else default_out_dir(args.wave)
    cache_dir = campaign_cache_dir(args.featcache_dataset, args.encoder, root=args.featcache_root)

    transport, flight_receipt = build_transport(
        base_url=args.server_url,
        model_path=args.model_path,
        model_sha256=args.model_sha256,
        max_encode_calls=ceilings.max_encode_calls,
        slots=args.slots,
        timeout_seconds=args.timeout_seconds,
    )

    try:
        summary = run_wave(
            wave=args.wave,
            data_dir=data_dir,
            meetings=meetings,
            tool_config=tool_config,
            transport=transport,
            out_dir=out_dir,
            derived_root=derived_root,
            cache_dir=cache_dir,
            resume=args.resume,
            workers=args.workers,
            encode_max_tokens=args.encode_max_tokens,
            ami_audio_root_relative=args.ami_audio_root_relative,
            ami_annotations_root_relative=args.ami_annotations_root_relative,
            query_gpu=query_gpu_utilization_snapshot,
            flight_receipt=flight_receipt,
            stop_file=args.stop_file,
        )
    finally:
        flight_receipt.write(out_dir / "transport-receipt.json", repo_root=REPO_ROOT)

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
