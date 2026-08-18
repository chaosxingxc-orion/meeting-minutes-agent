"""Two-level chunk/slice granularity constants.

Owner G1 lock item (c), ``docs/readiness/2026-08-18-chunk-slice-granularity-
analysis.md`` SS8. Retires the single ``DEFAULT_WINDOW_CAP_S = 2400.0``
(40-minute) cap -- refuted by the analysis (SS3: 2,400 s of audio alone is
2.54x the whole `-np 4` slot) and, per the analysis's 17-item change list,
duplicated in two places (``planner.py:22`` and ``adapters.py:40``) -- with
the two independently-bounded levels the binding proposal requires:

- a **task chunk**: the unit of state consolidation and dispatch
  (:mod:`.planner`), NEVER a transport unit;
- a **transport slice**: the unit of one core request (:mod:`.slicer`).

Every one of these values is either the analysis's own binding proposal
(SS8.1/SS8.2) or a directly-cited mechanical fact (the encoder's 30 s grid,
``tools/mtmd/mtmd-audio.cpp`` ``frames_per_chunk = 3000``).
"""

from __future__ import annotations

# -- transport slice: the unit of a core request (analysis SS8.1) ----------
TRANSPORT_SLICE_TARGET_S = 90.0
TRANSPORT_SLICE_MIN_S = 60.0
TRANSPORT_SLICE_MAX_S = 120.0
TRANSPORT_SLICE_SNAP_S = 3.0
# Zero, always: overlap exists only to serve a dedup stitch, and the dedup
# stitch is where 86% of SAEA's deletions were made (analysis SS8.1/SS8.3).
TRANSPORT_SLICE_OVERLAP_S = 0.0
ENCODER_CHUNK_S = 30.0  # tools/mtmd/mtmd-audio.cpp frames_per_chunk = 3000 = 30.0s @ 16kHz/hop160

# -- task chunk: the unit of state consolidation and dispatch (SS8.2) ------
TASK_CHUNK_TARGET_S = 360.0
TASK_CHUNK_MIN_S = 180.0
TASK_CHUNK_MAX_S = 900.0

__all__ = [
    "TRANSPORT_SLICE_TARGET_S",
    "TRANSPORT_SLICE_MIN_S",
    "TRANSPORT_SLICE_MAX_S",
    "TRANSPORT_SLICE_SNAP_S",
    "TRANSPORT_SLICE_OVERLAP_S",
    "ENCODER_CHUNK_S",
    "TASK_CHUNK_TARGET_S",
    "TASK_CHUNK_MIN_S",
    "TASK_CHUNK_MAX_S",
]
