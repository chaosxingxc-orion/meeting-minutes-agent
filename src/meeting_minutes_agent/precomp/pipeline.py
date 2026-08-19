"""The PRECOMP per-meeting pipeline: pinned Arm B diar -> tool + oracle
slice plans -> CPU slice cutting (worker pool) -> featcache encode-warm
pass, composed entirely from EXISTING machinery
(:mod:`meeting_minutes_agent.chunking.diarization`,
:mod:`meeting_minutes_agent.chunking.slicer`,
:mod:`meeting_minutes_agent.client.transport`,
:mod:`meeting_minutes_agent.probes.diar_smoke`) -- this module reimplements
none of the diar subprocess contact, audio decode/cut/hash, or transport
retry/budget logic those already carry; it only ORCHESTRATES them into one
per-meeting run producing one :mod:`~.receipts` receipt, per
``docs/readiness/2026-08-19-precomp-preregistration.md`` SS3.

Failure isolation (a deliberate, coordinator-reviewable design choice, in
the spirit of ``scripts/build_pattr_manifest.py``'s own "Spec-ambiguity
note... recorded for coordinator review"): PRECOMP is a PRODUCTION pass
over up to ~90 unattended, resumable meetings (wave-2's "night batch"),
not a small hand-watched smoke. Every step of :func:`run_meeting` below
:func:`~.budget.PrecompBudget`'s own checks (diar contact, oracle
resolution, slice planning, CPU cutting, encode-warm) is therefore wrapped
in ONE broad try/except at the meeting level: any failure produces a
recorded, ``ok: False`` receipt with whatever partial stage data was
gathered before the failure (never a bare crash that would need an
operator to notice and manually skip the meeting on the next resumed run).
This differs from ``scripts/launch_diar_smoke.py``'s stricter smoke
design, where a missing audio file propagates uncaught out of the whole
flight -- appropriate for a 6-meeting, hand-watched smoke wanting to fail
fast, not for an unattended overnight batch where "resumable at meeting
granularity" is the actual safety net. :class:`~.budget.PrecompBudgetExceeded`
is the one exception this function does NOT swallow: a ceiling crossing is
a flight-level stop, not a per-meeting failure, and propagates to the wave
runner exactly like ``scripts/launch_diar_smoke.py``'s own
``SmokeBudgetExceeded`` handling.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from ..chunking.constants import (
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from ..chunking.diarization import (
    NxtOracleDiarization,
    PinnedToolDiarization,
    ToolDiarizationConfig,
)
from ..chunking.slicer import (
    SliceManifest,
    SlicePlan,
    build_turn_aware_slice_plan,
    detect_energy_pause_transitions,
    materialize_slice_plan,
    read_audio_duration,
)
from ..client.transport import LlamaServerTransport
from ..corpora.nxt.corpus import NxtCorpus
from ..corpora.nxt.resolver import resolve_meeting
from ..probes.diar_smoke import (
    DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    estimate_gpu_seconds,
    query_gpu_utilization_snapshot,
    require_meeting_audio_path,
)
from .budget import PrecompBudget, PrecompBudgetExceeded
from .encode_warm import DEFAULT_ENCODE_WARM_MAX_TOKENS, encode_warm_manifest
from .metrics import build_meeting_metrics, snapshot_cache_dir
from .receipts import build_meeting_receipt

__all__ = [
    "DEFAULT_WORKERS",
    "DEFAULT_AMI_AUDIO_ROOT_RELATIVE",
    "DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE",
    "require_meeting_audio_path",
    "query_gpu_utilization_snapshot",
    "cut_slice_plans_parallel",
    "run_meeting",
]

#: Owner baseline (CPU preprocessing parallelism convention already used
#: elsewhere in this program: ~20 workers idle, capped at 8 while a GPU
#: campaign is concurrently in flight -- PRECOMP's encode-warm pass IS a
#: concurrent GPU campaign by construction, so 8 is this module's own
#: default, never the idle-host figure).
DEFAULT_WORKERS = 8

#: Matches ``scripts/build_pattr_manifest.py``'s own
#: ``DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE`` -- one convention for where
#: the NXT annotation layers live under the data root.
DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE = "datasets/ami/annotations/manual_1.6.2"

#: A failed meeting's receipt still carries every top-level block, at
#: whichever of these per-stage defaults the pipeline reached before
#: failing (module docstring; :mod:`~.receipts`'s own docstring names this
#: constant by this name).
FAILURE_STAGE_DEFAULTS: dict[str, Any] = {
    "diar": {"contact": None, "n_turns": None, "wall_seconds": None, "gpu_seconds_estimate": None},
    "slice_plans": {"tool": None, "oracle": None},
    "cutting": {"tool": None, "oracle": None, "wall_seconds": None, "workers": None},
    "encode_warm": {"tool": [], "oracle": [], "wall_seconds": None, "n_calls": 0},
    "metrics": {},
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cut_slice_plans_parallel(
    jobs: Mapping[str, tuple[SlicePlan, Path, Path]],
    *,
    workers: int = DEFAULT_WORKERS,
    materialize_fn: Callable[..., SliceManifest] = materialize_slice_plan,
) -> dict[str, SliceManifest]:
    """CPU slice cutting via a worker pool (prereg SS3 step 3, task
    instruction "worker pool, --workers with default 8"): materialize every
    ``(plan, source_audio_path, output_dir)`` job in ``jobs`` concurrently.
    ``materialize_fn`` defaults to
    :func:`~..chunking.slicer.materialize_slice_plan` (the real decode-once
    -cut-hash step); tests inject a fake to exercise the parallel-dispatch
    wiring without real audio I/O. A worker's exception propagates from the
    corresponding ``.result()`` call -- fail-closed, no partial manifest
    silently substituted for a job that raised."""

    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError(f"workers must be a positive integer, got {workers!r}")

    results: dict[str, SliceManifest] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(materialize_fn, plan, audio_path, out_dir): key
            for key, (plan, audio_path, out_dir) in jobs.items()
        }
        for future, key in future_to_key.items():
            results[key] = future.result()
    return results


def run_meeting(
    meeting_id: str,
    *,
    wave: int,
    audio_path: Path,
    tool_config: ToolDiarizationConfig,
    nxt_corpus: NxtCorpus,
    rttm_dir: Path,
    tool_slice_dir: Path,
    oracle_slice_dir: Path,
    transport: LlamaServerTransport,
    budget: PrecompBudget,
    cache_dir: Path,
    workers: int = DEFAULT_WORKERS,
    encode_max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS,
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
    run_subprocess: Callable[..., Any] | None = None,
    query_gpu: Callable[[], Mapping[str, float] | None] | None = None,
    materialize_fn: Callable[..., SliceManifest] = materialize_slice_plan,
    flight_receipt: Any | None = None,
) -> dict[str, Any]:
    """The whole per-meeting pipeline (prereg SS3, module docstring):
    pinned Arm B diar -> tool + oracle turn-aware slice plans -> CPU slice
    cutting (worker pool) -> featcache encode-warm pass -> descriptive
    metrics, folded into one :func:`~.receipts.build_meeting_receipt`.
    Never raises except :class:`~.budget.PrecompBudgetExceeded` (module
    docstring) -- every other failure is caught and recorded as an
    ``ok: False`` receipt."""

    diar_block = dict(FAILURE_STAGE_DEFAULTS["diar"])
    slice_plans_block = dict(FAILURE_STAGE_DEFAULTS["slice_plans"])
    cutting_block = dict(FAILURE_STAGE_DEFAULTS["cutting"])
    encode_block = dict(FAILURE_STAGE_DEFAULTS["encode_warm"])
    metrics_block: dict[str, Any] = dict(FAILURE_STAGE_DEFAULTS["metrics"])

    try:
        # -- 1. diarization: pinned Arm B, per-contact log -------------
        budget.check_before_diar()
        backend = PinnedToolDiarization(tool_config, output_dir=rttm_dir, run_subprocess=run_subprocess)
        tool_result = None
        started = time.monotonic()
        try:
            tool_result = backend.diarize(meeting_id, audio_path)
        finally:
            diar_wall = time.monotonic() - started
            snapshot = query_gpu() if query_gpu is not None else None
            diar_gpu_seconds = estimate_gpu_seconds(diar_wall, snapshot)
            budget.record_diar(diar_gpu_seconds)
            diar_block = {
                "contact": backend.contact_log[-1].to_dict() if backend.contact_log else None,
                "n_turns": len(tool_result.turns) if tool_result is not None else None,
                "wall_seconds": diar_wall,
                "gpu_seconds_estimate": diar_gpu_seconds,
            }

        # -- 2. oracle turns: NXT gold, ceiling-arm admitted -----------
        resolved = resolve_meeting(nxt_corpus, meeting_id)
        oracle_result = NxtOracleDiarization(resolved).diarize(meeting_id)

        # -- 3. slice plans: tool AND oracle (prereg SS2: "BOTH turn
        # sources... G1's ceiling arm needs both slice sets") -----------
        duration = read_audio_duration(audio_path)
        transitions = detect_energy_pause_transitions(audio_path)
        tool_plan = build_turn_aware_slice_plan(
            meeting_id,
            tool_result.turns,
            turn_provenance=tool_result.provenance,
            allow_oracle_turns=False,
            total_duration_s=duration,
            fallback_pause_transitions=transitions,
            nominal_s=nominal_s,
            min_s=min_s,
            max_s=max_s,
            snap_s=snap_s,
        )
        oracle_plan = build_turn_aware_slice_plan(
            meeting_id,
            oracle_result.turns,
            turn_provenance=oracle_result.provenance,
            allow_oracle_turns=True,
            total_duration_s=duration,
            fallback_pause_transitions=transitions,
            nominal_s=nominal_s,
            min_s=min_s,
            max_s=max_s,
            snap_s=snap_s,
        )
        slice_plans_block = {
            "tool": {
                "content_hash": tool_plan.content_hash,
                "n_slices": len(tool_plan.slices),
                "turn_provenance": tool_plan.turn_provenance.value if tool_plan.turn_provenance else None,
            },
            "oracle": {
                "content_hash": oracle_plan.content_hash,
                "n_slices": len(oracle_plan.slices),
                "turn_provenance": oracle_plan.turn_provenance.value if oracle_plan.turn_provenance else None,
            },
        }

        # -- 4. CPU slice cutting: worker pool --------------------------
        budget.check_before_cutting()
        started = time.monotonic()
        manifests = cut_slice_plans_parallel(
            {
                "tool": (tool_plan, audio_path, tool_slice_dir),
                "oracle": (oracle_plan, audio_path, oracle_slice_dir),
            },
            workers=workers,
            materialize_fn=materialize_fn,
        )
        cutting_wall = time.monotonic() - started
        budget.record_cutting(cutting_wall)
        cutting_block = {
            "tool": {
                "content_hash": manifests["tool"].content_hash,
                "n_entries": len(manifests["tool"].entries),
            },
            "oracle": {
                "content_hash": manifests["oracle"].content_hash,
                "n_entries": len(manifests["oracle"].entries),
            },
            "wall_seconds": cutting_wall,
            "workers": workers,
        }

        # -- 5. featcache encode-warm pass: outputs discarded unread ---
        cache_before = snapshot_cache_dir(cache_dir)
        started = time.monotonic()
        tool_outcomes = encode_warm_manifest(
            transport,
            manifests["tool"],
            tool_slice_dir,
            request_id_prefix=f"precomp-w{wave}-tool-{meeting_id}",
            max_tokens=encode_max_tokens,
            budget=budget,
            query_gpu=query_gpu,
            flight_receipt=flight_receipt,
        )
        oracle_outcomes = encode_warm_manifest(
            transport,
            manifests["oracle"],
            oracle_slice_dir,
            request_id_prefix=f"precomp-w{wave}-oracle-{meeting_id}",
            max_tokens=encode_max_tokens,
            budget=budget,
            query_gpu=query_gpu,
            flight_receipt=flight_receipt,
        )
        encode_wall = time.monotonic() - started
        cache_after = snapshot_cache_dir(cache_dir)
        encode_block = {
            "tool": tool_outcomes,
            "oracle": oracle_outcomes,
            "wall_seconds": encode_wall,
            "n_calls": len(tool_outcomes) + len(oracle_outcomes),
        }

        # -- 6. descriptive metrics (verdict-free) ----------------------
        metrics_block = build_meeting_metrics(
            tool_result=tool_result,
            oracle_result=oracle_result,
            tool_plan=tool_plan,
            oracle_plan=oracle_plan,
            cache_before=cache_before,
            cache_after=cache_after,
            diar_wall_s=diar_block["wall_seconds"],
            cutting_wall_s=cutting_block["wall_seconds"],
            encode_wall_s=encode_block["wall_seconds"],
        )

    except PrecompBudgetExceeded:
        raise
    except Exception as error:  # noqa: BLE001 -- isolated per meeting (module docstring), recorded not raised
        return build_meeting_receipt(
            wave=wave,
            meeting_id=meeting_id,
            ok=False,
            error=f"{type(error).__name__}: {error}",
            diar=diar_block,
            slice_plans=slice_plans_block,
            cutting=cutting_block,
            encode_warm=encode_block,
            metrics=metrics_block,
            budget_after=budget.to_dict(),
            recorded_utc=_iso_now(),
        )

    return build_meeting_receipt(
        wave=wave,
        meeting_id=meeting_id,
        ok=True,
        error=None,
        diar=diar_block,
        slice_plans=slice_plans_block,
        cutting=cutting_block,
        encode_warm=encode_block,
        metrics=metrics_block,
        budget_after=budget.to_dict(),
        recorded_utc=_iso_now(),
    )
