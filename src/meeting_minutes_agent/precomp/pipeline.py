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

Turn sources (the G1 VAD-supplement extension,
``docs/readiness/2026-08-19-g1-floors-preregistration.md`` SS3): wave-1/2's
registered pass always builds BOTH the pinned-tool AND oracle-NXT turn
sources together (:data:`DEFAULT_TURN_SOURCES`, unchanged). A caller may
instead pass ``turn_sources=("vad",)`` (:data:`VAD_SOURCE`) to build ONLY
the pure-VAD/no-diarization source that feeds G1's Z-nodiar ablation
(:func:`~..chunking.slicer.build_vad_slice_plan`, the module's own
"explicit fallback/ablation mode... the no-diarization arm"): this skips
the pinned diar tool contact and the NXT oracle resolution ENTIRELY --
neither :func:`~..budget.PrecompBudget.check_before_diar` nor a diar
subprocess call happens when ``"tool"`` is not requested, and
:func:`~..corpora.nxt.resolver.resolve_meeting` is never called when
``"oracle"`` is not requested -- so a ``turn_sources=("vad",)`` supplement
invocation never re-pays (or re-risks) work wave-1 already receipted,
structurally, without needing to inspect any existing receipt. Any subset
of :data:`TURN_SOURCES` may be requested together in one call; each
requested source gets its own slice-plan/cutting/encode-warm sub-stage,
and the receipt's ``slice_plans``/``cutting``/``encode_warm`` blocks always
carry all three keys (``"tool"``/``"oracle"``/``"vad"``), ``None``/empty
for whichever source was not requested this call -- see
:mod:`.receipts`'s schema-versioning note.

Whenever :data:`VAD_SOURCE` is requested, this pipeline also PERSISTS the
built :class:`~..chunking.slicer.SlicePlan` as JSON under
``vad_manifest_dir`` (:func:`write_vad_slice_plan_manifest`, the
``SlicePlan.to_dict()`` shape, one ``<meeting_id>.json`` file per meeting)
-- the one artifact G1's Z-nodiar arm actually consumes
(:func:`meeting_minutes_agent.probes.g1.load_vad_slice_plan`, fail-closed
via ``G1VadSupplementMissingError``, read through ``scripts/run_g1.py``'s
``--vad-manifest-dir``). Before this, the VAD source cut real slice WAVs
and warmed the feature cache but never materialized this manifest, so a
real Z-nodiar flight had no supplement to read. ``vad_manifest_dir`` is
therefore required exactly like ``vad_slice_dir`` whenever ``"vad"`` is
requested (fail-closed, :class:`InvalidTurnSourcesError`).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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
    build_vad_slice_plan,
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
from .receipts import build_meeting_receipt, fsync_write_json

__all__ = [
    "DEFAULT_WORKERS",
    "DEFAULT_AMI_AUDIO_ROOT_RELATIVE",
    "DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE",
    "TOOL_SOURCE",
    "ORACLE_SOURCE",
    "VAD_SOURCE",
    "TURN_SOURCES",
    "DEFAULT_TURN_SOURCES",
    "InvalidTurnSourcesError",
    "require_meeting_audio_path",
    "query_gpu_utilization_snapshot",
    "cut_slice_plans_parallel",
    "vad_slice_plan_manifest_path",
    "write_vad_slice_plan_manifest",
    "run_meeting",
]

#: The three PRECOMP turn sources (module docstring). ``"tool"`` (pinned
#: Arm B diar) and ``"oracle"`` (NXT gold turns) are wave-1/2's registered
#: pair; ``"vad"`` (pure-VAD/no-diarization, :func:`~..chunking.slicer.
#: build_vad_slice_plan`) is the G1 floors campaign's Z-nodiar-ablation
#: supplement source.
TOOL_SOURCE = "tool"
ORACLE_SOURCE = "oracle"
VAD_SOURCE = "vad"
TURN_SOURCES: tuple[str, ...] = (TOOL_SOURCE, ORACLE_SOURCE, VAD_SOURCE)

#: Backward-compatible default: unchanged wave-1/2 behaviour, both
#: registered sources together, every existing caller that never passes
#: ``turn_sources`` at all.
DEFAULT_TURN_SOURCES: tuple[str, ...] = (TOOL_SOURCE, ORACLE_SOURCE)


class InvalidTurnSourcesError(ValueError):
    """``turn_sources`` was empty, carried an unknown source name, or
    requested a source whose required companion argument
    (``tool_config`` for :data:`TOOL_SOURCE`, ``vad_slice_dir`` for
    :data:`VAD_SOURCE`) was not given."""


def _normalize_turn_sources(turn_sources: Sequence[str]) -> tuple[str, ...]:
    """Validate and de-duplicate (order-preserving) a caller's
    ``turn_sources``. Fail-closed: an empty sequence or an unknown source
    name raises :class:`InvalidTurnSourcesError` rather than silently
    running nothing or an unrecognized stage."""

    if not turn_sources:
        raise InvalidTurnSourcesError("turn_sources must be non-empty")
    ordered: list[str] = []
    for source in turn_sources:
        if source not in TURN_SOURCES:
            raise InvalidTurnSourcesError(f"unknown turn source {source!r}; expected one of {TURN_SOURCES}")
        if source not in ordered:
            ordered.append(source)
    return tuple(ordered)


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
    "slice_plans": {"tool": None, "oracle": None, "vad": None},
    "cutting": {"tool": None, "oracle": None, "vad": None, "wall_seconds": None, "workers": None},
    "encode_warm": {"tool": [], "oracle": [], "vad": [], "wall_seconds": None, "n_calls": 0},
    "metrics": {},
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# VAD slice-plan manifest persistence (closes the G1 Z-nodiar gap: this
# supplement previously cut real slice WAVs and warmed the feature cache but
# never materialized the one artifact Z-nodiar's own fail-closed loader
# requires -- ``probes/g1.py``'s ``load_vad_slice_plan``/
# ``G1VadSupplementMissingError``, consumed via ``scripts/run_g1.py``'s
# ``--vad-manifest-dir``)
# ---------------------------------------------------------------------------


def vad_slice_plan_manifest_path(vad_manifest_dir: Path | str, meeting_id: str) -> Path:
    """Where the VAD supplement persists ``meeting_id``'s materialized
    :class:`~..chunking.slicer.SlicePlan` as JSON: ``<vad_manifest_dir>/
    <meeting_id>.json`` -- the EXACT naming/dir convention
    :func:`meeting_minutes_agent.probes.g1.load_vad_slice_plan` reads
    (``scripts/run_g1.py``'s own ``resolve_slice_plan``:
    ``Path(vad_manifest_dir) / f"{meeting_id}.json"``), so a real flight
    only needs to point ``--vad-manifest-dir`` at the SAME directory this
    module's own ``vad_manifest_dir`` argument names -- no translation, no
    second convention to keep in sync."""

    return Path(vad_manifest_dir) / f"{meeting_id}.json"


def write_vad_slice_plan_manifest(vad_manifest_dir: Path | str, plan: SlicePlan) -> Path:
    """Persist ``plan`` (already ``_assert_transport_bound``-checked inside
    :func:`~..chunking.slicer.build_vad_slice_plan` itself) as the
    ``SlicePlan.to_dict()``-shaped JSON G1's Z-nodiar arm loads, fsynced --
    the same durability discipline :func:`~.receipts.fsync_write_json`
    already applies to every other PRECOMP receipt this pipeline writes."""

    path = vad_slice_plan_manifest_path(vad_manifest_dir, plan.meeting_id)
    fsync_write_json(path, plan.to_dict())
    return path


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
    tool_config: ToolDiarizationConfig | None = None,
    nxt_corpus: NxtCorpus,
    rttm_dir: Path,
    tool_slice_dir: Path,
    oracle_slice_dir: Path,
    vad_slice_dir: Path | None = None,
    vad_manifest_dir: Path | None = None,
    transport: LlamaServerTransport,
    budget: PrecompBudget,
    cache_dir: Path,
    workers: int = DEFAULT_WORKERS,
    encode_max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS,
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
    turn_sources: Sequence[str] = DEFAULT_TURN_SOURCES,
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
    ``ok: False`` receipt.

    ``turn_sources`` (module docstring) defaults to
    :data:`DEFAULT_TURN_SOURCES` -- both registered sources, byte-for-byte
    the original behaviour. Passing ``turn_sources=("vad",)`` runs ONLY the
    pure-VAD stage: the diar contact, the oracle resolution, and both
    turn-aware slice plans are skipped entirely (never even attempted), and
    ``tool_config``/``nxt_corpus`` go unused for that call -- ``tool_config``
    may be left ``None`` whenever :data:`TOOL_SOURCE` is not requested.
    Whenever :data:`VAD_SOURCE` IS requested, the built VAD
    :class:`~..chunking.slicer.SlicePlan` is also persisted, fsynced, to
    ``vad_manifest_dir`` (:func:`write_vad_slice_plan_manifest`) -- required
    exactly like ``vad_slice_dir`` (same fail-closed rule, one level up:
    Z-nodiar's own loader, ``probes/g1.py``'s ``load_vad_slice_plan``, fails
    closed on a missing manifest; this pipeline now fails closed BEFORE that
    point, on a missing ``vad_manifest_dir``, rather than silently cutting
    WAVs a later G1 flight could never resolve a slice plan for)."""

    turn_sources = _normalize_turn_sources(turn_sources)
    need_tool = TOOL_SOURCE in turn_sources
    need_oracle = ORACLE_SOURCE in turn_sources
    need_vad = VAD_SOURCE in turn_sources
    if need_vad and vad_slice_dir is None:
        raise InvalidTurnSourcesError("turn_sources includes 'vad' but vad_slice_dir was not given")
    if need_vad and vad_manifest_dir is None:
        raise InvalidTurnSourcesError("turn_sources includes 'vad' but vad_manifest_dir was not given")
    if need_tool and tool_config is None:
        raise InvalidTurnSourcesError("turn_sources includes 'tool' but tool_config was not given")

    diar_block = dict(FAILURE_STAGE_DEFAULTS["diar"])
    slice_plans_block = dict(FAILURE_STAGE_DEFAULTS["slice_plans"])
    cutting_block = dict(FAILURE_STAGE_DEFAULTS["cutting"])
    encode_block = dict(FAILURE_STAGE_DEFAULTS["encode_warm"])
    metrics_block: dict[str, Any] = dict(FAILURE_STAGE_DEFAULTS["metrics"])

    try:
        tool_result = None
        oracle_result = None
        tool_plan: SlicePlan | None = None
        oracle_plan: SlicePlan | None = None
        vad_plan: SlicePlan | None = None

        # -- 1. diarization: pinned Arm B, per-contact log (TOOL_SOURCE
        # only -- skipped entirely, no subprocess/GPU contact, budget check
        # never even called, when "tool" is not requested) --------------
        if need_tool:
            budget.check_before_diar()
            backend = PinnedToolDiarization(tool_config, output_dir=rttm_dir, run_subprocess=run_subprocess)
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

        # -- 2. oracle turns: NXT gold, ceiling-arm admitted (ORACLE_SOURCE
        # only -- skipped entirely, no NXT resolution, when "oracle" is
        # not requested) --------------------------------------------------
        if need_oracle:
            resolved = resolve_meeting(nxt_corpus, meeting_id)
            oracle_result = NxtOracleDiarization(resolved).diarize(meeting_id)

        # -- 3. slice plans: whichever of tool/oracle/vad was requested
        # (prereg SS2: "BOTH turn sources... G1's ceiling arm needs both
        # slice sets"; the G1 VAD supplement adds a third, independent
        # source, module docstring) -----------------------------------
        duration: float | None = None
        transitions: tuple[float, ...] = ()
        if need_tool or need_oracle or need_vad:
            duration = read_audio_duration(audio_path)
            transitions = detect_energy_pause_transitions(audio_path)

        if need_tool:
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
            slice_plans_block["tool"] = {
                "content_hash": tool_plan.content_hash,
                "n_slices": len(tool_plan.slices),
                "turn_provenance": tool_plan.turn_provenance.value if tool_plan.turn_provenance else None,
            }
        if need_oracle:
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
            slice_plans_block["oracle"] = {
                "content_hash": oracle_plan.content_hash,
                "n_slices": len(oracle_plan.slices),
                "turn_provenance": oracle_plan.turn_provenance.value if oracle_plan.turn_provenance else None,
            }
        if need_vad:
            vad_plan = build_vad_slice_plan(
                meeting_id,
                duration,
                pause_transitions=transitions,
                nominal_s=nominal_s,
                min_s=min_s,
                max_s=max_s,
                snap_s=snap_s,
            )
            manifest_path = write_vad_slice_plan_manifest(vad_manifest_dir, vad_plan)
            slice_plans_block["vad"] = {
                "content_hash": vad_plan.content_hash,
                "n_slices": len(vad_plan.slices),
                "turn_provenance": None,
                "manifest_path": str(manifest_path),
            }

        # -- 4. CPU slice cutting: worker pool, one job per requested
        # source only ----------------------------------------------------
        jobs: dict[str, tuple[SlicePlan, Path, Path]] = {}
        if need_tool:
            jobs["tool"] = (tool_plan, audio_path, tool_slice_dir)
        if need_oracle:
            jobs["oracle"] = (oracle_plan, audio_path, oracle_slice_dir)
        if need_vad:
            jobs["vad"] = (vad_plan, audio_path, vad_slice_dir)

        budget.check_before_cutting()
        started = time.monotonic()
        manifests = cut_slice_plans_parallel(jobs, workers=workers, materialize_fn=materialize_fn)
        cutting_wall = time.monotonic() - started
        budget.record_cutting(cutting_wall)
        for source, manifest in manifests.items():
            cutting_block[source] = {"content_hash": manifest.content_hash, "n_entries": len(manifest.entries)}
        cutting_block["wall_seconds"] = cutting_wall
        cutting_block["workers"] = workers

        # -- 5. featcache encode-warm pass: outputs discarded unread,
        # one pass per requested source only ------------------------------
        slice_dir_by_source: dict[str, Path] = {"tool": tool_slice_dir, "oracle": oracle_slice_dir}
        if vad_slice_dir is not None:
            slice_dir_by_source["vad"] = vad_slice_dir
        cache_before = snapshot_cache_dir(cache_dir)
        started = time.monotonic()
        total_calls = 0
        for source, manifest in manifests.items():
            outcomes = encode_warm_manifest(
                transport,
                manifest,
                slice_dir_by_source[source],
                request_id_prefix=f"precomp-w{wave}-{source}-{meeting_id}",
                max_tokens=encode_max_tokens,
                budget=budget,
                query_gpu=query_gpu,
                flight_receipt=flight_receipt,
            )
            encode_block[source] = outcomes
            total_calls += len(outcomes)
        encode_wall = time.monotonic() - started
        cache_after = snapshot_cache_dir(cache_dir)
        encode_block["wall_seconds"] = encode_wall
        encode_block["n_calls"] = total_calls

        # -- 6. descriptive metrics (verdict-free), whichever blocks the
        # requested source(s) actually support ---------------------------
        metrics_block = build_meeting_metrics(
            tool_result=tool_result,
            oracle_result=oracle_result,
            tool_plan=tool_plan,
            oracle_plan=oracle_plan,
            vad_plan=vad_plan,
            cache_before=cache_before,
            cache_after=cache_after,
            diar_wall_s=diar_block["wall_seconds"] or 0.0,
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
