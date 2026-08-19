"""PRECOMP -- the pinned-diar + featcache production pass.

Registered design: ``docs/readiness/2026-08-19-precomp-preregistration.md``;
tool binding: ``docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md``.
Freezes reusable derived assets (speaker turns, transport-slice manifests,
a warmed feature cache) over two waves -- wave-1 the dev-18 meetings,
wave-2 the remaining usable-discovery meetings -- so every later experiment
against this audio is decode-only. This package is the MACHINERY: the
per-meeting pipeline (:mod:`.pipeline`), the wave rosters and their
fail-closed exposure gate (:mod:`.roster`), per-wave budget ceilings
(:mod:`.budget`), the encode-warm contact whose reply text is never read
(:mod:`.encode_warm`), receipt schemas (:mod:`.receipts`), and descriptive,
verdict-free metrics (:mod:`.metrics`). The wave RUNNER --
``scripts/run_precomp.py`` -- composes these; a real flight (real diar
contact, real frozen-core contact) is a separate, later, coordinator-
reviewed mission, exactly like every other flight-vs-machinery split in
this repository.
"""

from __future__ import annotations

from .budget import (
    WAVE_1_CEILINGS,
    WAVE_2_CEILINGS,
    CEILINGS_PROFILES,
    G1_SUPPLEMENT_CEILINGS,
    PrecompBudget,
    PrecompBudgetExceeded,
    WaveCeilings,
    ceilings_for_profile,
    ceilings_for_wave,
    wave_usage_from_receipts,
)
from .encode_warm import (
    DEFAULT_ENCODE_WARM_MAX_TOKENS,
    build_encode_warm_decoding_params,
    encode_warm_manifest,
    encode_warm_slice,
)
from .metrics import (
    boundary_displacement_distribution,
    build_meeting_metrics,
    cache_delta,
    interior_boundaries,
    slice_counts,
    snapshot_cache_dir,
    turn_counts,
    vad_slice_count,
    wall_summary,
)
from .pipeline import (
    DEFAULT_TURN_SOURCES,
    DEFAULT_WORKERS,
    ORACLE_SOURCE,
    TOOL_SOURCE,
    TURN_SOURCES,
    VAD_SOURCE,
    InvalidTurnSourcesError,
    cut_slice_plans_parallel,
    run_meeting,
)
from .receipts import (
    SCHEMA_VERSION,
    already_done,
    build_meeting_receipt,
    build_wave_summary,
    meeting_receipt_path,
    wave_summary_path,
    write_meeting_receipt,
    write_wave_summary,
)
from .roster import (
    WAVE_1,
    WAVE_2,
    WAVES,
    PrecompRosterError,
    assert_wave_roster_admissible,
    default_wave_meetings,
    dev18_roster,
    usable_discovery_exposable_roster,
    wave2_roster,
)

__all__ = [
    "WAVE_1",
    "WAVE_2",
    "WAVES",
    "PrecompRosterError",
    "dev18_roster",
    "usable_discovery_exposable_roster",
    "wave2_roster",
    "default_wave_meetings",
    "assert_wave_roster_admissible",
    "PrecompBudgetExceeded",
    "WaveCeilings",
    "WAVE_1_CEILINGS",
    "WAVE_2_CEILINGS",
    "G1_SUPPLEMENT_CEILINGS",
    "CEILINGS_PROFILES",
    "ceilings_for_wave",
    "ceilings_for_profile",
    "PrecompBudget",
    "wave_usage_from_receipts",
    "turn_counts",
    "slice_counts",
    "vad_slice_count",
    "interior_boundaries",
    "boundary_displacement_distribution",
    "snapshot_cache_dir",
    "cache_delta",
    "wall_summary",
    "build_meeting_metrics",
    "DEFAULT_ENCODE_WARM_MAX_TOKENS",
    "build_encode_warm_decoding_params",
    "encode_warm_slice",
    "encode_warm_manifest",
    "SCHEMA_VERSION",
    "meeting_receipt_path",
    "wave_summary_path",
    "build_meeting_receipt",
    "write_meeting_receipt",
    "already_done",
    "build_wave_summary",
    "write_wave_summary",
    "DEFAULT_WORKERS",
    "TOOL_SOURCE",
    "ORACLE_SOURCE",
    "VAD_SOURCE",
    "TURN_SOURCES",
    "DEFAULT_TURN_SOURCES",
    "InvalidTurnSourcesError",
    "cut_slice_plans_parallel",
    "run_meeting",
]
