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

# Float-accumulation tolerance for hard TRANSPORT_SLICE_MAX_S post-condition
# checks, NOT a bound relaxation: a value compared against
# TRANSPORT_SLICE_MAX_S here is always some slice's `end - start`, computed
# after packing/snap/gap-tiling arithmetic (repeated float addition/
# subtraction across turn and pause boundaries) -- IEEE 754 double
# arithmetic can leave a few ULPs of residue on that path even when every
# input was well inside the cap. Observed in production
# (docs/checks/2026-08-19-precomp-wave2/README.md "The one refused
# meeting", and its follow-up transport-layer repeat one call-site deeper):
# ES2005d's turn-derived plan produced a slice measuring
# 120.00000000000011s against a 120.0s cap -- an overrun of 1.1e-13s, six
# orders of magnitude below this epsilon, from packing arithmetic alone.
# Consumed by BOTH the hard post-condition every :class:`~.slicer.SlicePlan`
# passes through (:func:`~.slicer._assert_transport_bound`) and the
# transport layer's own per-request guard
# (:meth:`~meeting_minutes_agent.client.transport.LlamaServerTransport.
# request`) -- the same slice duration value reaches both checks, so both
# need the same tolerance. Absorbs exactly that class of float noise and
# nothing else: a slice genuinely longer than the cap by any
# humanly-meaningful margin (a microsecond, let alone a second) still
# refuses at both call sites.
TRANSPORT_SLICE_MAX_EPSILON_S = 1e-9

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
    "TRANSPORT_SLICE_MAX_EPSILON_S",
    "TASK_CHUNK_TARGET_S",
    "TASK_CHUNK_MIN_S",
    "TASK_CHUNK_MAX_S",
]
