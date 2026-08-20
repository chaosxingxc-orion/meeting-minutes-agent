"""The real transport slicer (owner G1 lock item (c), 17-item change list
items 1/9/16 -- the single largest missing piece named "a precondition for
any G1 flight"): builds the frozen, content-hashed per-meeting slice
manifest that :mod:`.planner`'s task chunks are dispatched against, one
core request per slice, never a whole chunk or a whole meeting file
(``docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md`` SS8.1).

Two packing modes, per the 2026-08-18 diarization-aware slicer amendment
(pipeline order DIARIZE -> pack -> dispatch):

- **turn-aware** (:func:`build_turn_aware_slice_plan`): packs CONSECUTIVE
  speaker turns greedily into ``~90 s`` slices; a slice boundary always
  falls on a turn boundary, NEVER mid-turn; a single turn longer than
  ``max_s`` is the one exception, split internally at VAD pauses. Needs a
  turn table (``[{start, end, speaker}, ...]``, source-agnostic) and a
  declared :class:`~.leakage.BoundaryProvenance` for it -- a gold
  (AMI/ICSI annotation) turn table is Tier-M1 and is refused unless
  ``allow_oracle_turns=True`` (:mod:`.leakage`), exactly mirroring the
  topic-layer M1 gate; a tool-diarizer's own table is Tier-M0 and always
  admissible. **This module does NOT default to the oracle tier**: turn-
  aware packing over a gold table is available, real, and tested, but it
  is a declared ceiling-arm choice a caller opts into, never a silent
  default -- the safety property the M1 gate exists to guarantee applies
  here exactly as it does to topic marks.
- **VAD/grid** (:func:`build_vad_slice_plan`): the explicit fallback/
  ablation mode (the no-diarization arm) when no admissible turn table is
  available. Fixed ``nominal_s`` grid, boundaries snapped (``±snap_s``) to
  a signal-derived (energy-based) speech/non-speech transition when one is
  nearby, else cut at the unsnapped grid point.

Both modes share: **zero overlap** (overlap exists only to serve a dedup
stitch, and the dedup stitch is where 86% of SAEA's deletions were made),
hard bounds ``[min_s, max_s]`` after snapping/packing, and a boundary
source that is signal- or turn-derived only -- **never** a model-declared
boundary (analysis SS8.1). Both modes also trim, never absorb, leading/
trailing non-speech: turn-aware mode's first/last slice starts/ends at the
first/last turn's own edge (pulled out by at most ``snap_s``), and VAD
mode trims a leading/trailing energy-floor pause run before tiling --
neither mode ever stretches an edge slice all the way to absolute 0 or the
full meeting duration just because that is where the audio file happens to
end. Both modes finish behind the same hard post-condition
(:func:`_finalize_slice_plan`): every emitted slice's duration is
re-checked against :data:`TRANSPORT_SLICE_MAX_S` (plus
:data:`TRANSPORT_SLICE_MAX_EPSILON_S`, a float-accumulation tolerance only
-- never a bound relaxation) and a violation raises
:class:`TransportBoundViolation` rather than shipping a manifest
``client/transport.py`` would refuse mid-flight.

:func:`materialize_slice_plan` / :func:`build_slice_manifest` do the one
real I/O this module performs: decode the source audio ONCE, normalize to
16 kHz mono (the declared decode path every corpus's audio goes through --
17-item change list item 8 -- so a 44.1 kHz stereo MeetingBank clip and a
16 kHz mono AMI/ICSI clip are cut identically), cut per the frozen plan,
write each slice as its own 16 kHz mono PCM16 WAV, and hash it. ffmpeg is
absent by design (CLAUDE.md); ``librosa``/``soundfile`` do the whole job.
The resulting :class:`SliceManifest` is what a caller freezes BEFORE any
arm runs, so the feature cache (keyed on exact audio bytes) pays for the
encode exactly once across the whole campaign.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

from ..runreceipt import config_hash
from .constants import (
    ENCODER_CHUNK_S,
    TRANSPORT_SLICE_MAX_EPSILON_S,
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from .leakage import BoundaryProvenance, assert_runtime_admissible

DEFAULT_MIN_PAUSE_S = 1.0
DEFAULT_ENERGY_FLOOR_PERCENTILE = 15.0
DEFAULT_ENERGY_FRAME_S = 0.02


class SlicerError(ValueError):
    """A slice-plan input was invalid (bad bounds, an inadmissible turn-
    table provenance, ...)."""


class TransportBoundViolation(SlicerError):
    """A finalized slice plan carries a slice whose duration exceeds
    :data:`TRANSPORT_SLICE_MAX_S`, the transport layer's own hard
    per-request cap (``client/transport.py``'s
    ``max_audio_seconds_per_request``). Raised by the hard post-condition
    every :class:`SlicePlan` passes through before it is handed back to a
    caller (:func:`_finalize_slice_plan`) -- belt-and-braces beyond any
    packing-logic correctness a mode's own tiling is supposed to guarantee:
    a manifest must never freeze a slice the transport layer will refuse
    mid-flight."""


def _validate_bounds(nominal_s: float, min_s: float, max_s: float, snap_s: float) -> None:
    if nominal_s <= 0 or min_s <= 0 or max_s <= 0:
        raise SlicerError(f"nominal_s/min_s/max_s must all be positive, got {nominal_s}, {min_s}, {max_s}")
    if not (min_s <= nominal_s <= max_s):
        raise SlicerError(
            f"slice bounds must satisfy min_s <= nominal_s <= max_s, got min={min_s}, nominal={nominal_s}, max={max_s}"
        )
    if snap_s < 0:
        raise SlicerError(f"snap_s must be non-negative, got {snap_s}")


# ---------------------------------------------------------------------------
# data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnSpan:
    """One speaker turn: ``[start, end)`` plus a speaker id. Plain, source-
    agnostic data (2026-08-18 amendment: "make it a plain parameter,
    source-agnostic") -- its provenance tier is declared separately by the
    caller of :func:`build_turn_aware_slice_plan`, never inferred from this
    shape."""

    start: float
    end: float
    speaker: str

    def validate(self) -> "TurnSpan":
        if not math.isfinite(self.start) or not math.isfinite(self.end) or self.end <= self.start:
            raise SlicerError(f"TurnSpan requires end > start, got start={self.start}, end={self.end}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "speaker": self.speaker}


@dataclass(frozen=True)
class SliceTurnEntry:
    """One turn's presence within one slice: absolute (meeting-wide) times
    plus slice-relative offsets -- what a LISTEN prompt's span-level
    speaker tags need (2026-08-18 amendment item 2)."""

    speaker: str
    absolute_start: float
    absolute_end: float
    slice_offset_start: float
    slice_offset_end: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "absolute_start": self.absolute_start,
            "absolute_end": self.absolute_end,
            "slice_offset_start": self.slice_offset_start,
            "slice_offset_end": self.slice_offset_end,
        }


@dataclass(frozen=True)
class Slice:
    index: int
    start: float
    end: float
    vad_snap_applied: bool
    turns: tuple[SliceTurnEntry, ...] = field(default_factory=tuple)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def encoder_chunk_count(self) -> int:
        """The encoder works on a 30 s grid (``ENCODER_CHUNK_S``, ``tools/
        mtmd/mtmd-audio.cpp`` ``frames_per_chunk = 3000``); a slice length
        that is not a multiple of 30 s ends on a partial final chunk, still
        counted here (ceiling, not floor)."""

        if self.duration <= 0:
            return 0
        return math.ceil(self.duration / ENCODER_CHUNK_S)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "vad_snap_applied": self.vad_snap_applied,
            "encoder_chunk_count": self.encoder_chunk_count,
            "turns": [t.to_dict() for t in self.turns],
        }


class SlicePlanMode(str, Enum):
    VAD = "vad"
    TURN_AWARE = "turn_aware"


@dataclass(frozen=True)
class SlicePlan:
    """A meeting's frozen, deterministic transport-slice plan -- pure data,
    no audio bytes touched yet (see :func:`materialize_slice_plan` for the
    one real-I/O step). ``turn_provenance`` records which tier fed the
    packing (2026-08-18 amendment item 4): ``None`` for VAD mode, a
    :class:`~.leakage.BoundaryProvenance` for turn-aware mode."""

    meeting_id: str
    mode: SlicePlanMode
    turn_provenance: BoundaryProvenance | None
    total_duration_s: float
    slices: tuple[Slice, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "mode": self.mode.value,
            "turn_provenance": self.turn_provenance.value if self.turn_provenance is not None else None,
            "total_duration_s": self.total_duration_s,
            "slices": [s.to_dict() for s in self.slices],
            "content_hash": self.content_hash,
        }


def _plan_payload(
    meeting_id: str, mode: SlicePlanMode, turn_provenance: BoundaryProvenance | None, total_duration_s: float,
    slices: Sequence[Slice],
) -> dict:
    return {
        "meeting_id": meeting_id,
        "mode": mode.value,
        "turn_provenance": turn_provenance.value if turn_provenance is not None else None,
        "total_duration_s": total_duration_s,
        "slices": [s.to_dict() for s in slices],
    }


def _assert_transport_bound(slices: Sequence[Slice]) -> None:
    """Hard post-condition (module docstring, both modes): every emitted
    slice's duration must fit the transport layer's own hard per-request
    cap regardless of what ``max_s`` a caller packed against -- checked
    against the fixed :data:`TRANSPORT_SLICE_MAX_S` constant, widened by
    :data:`TRANSPORT_SLICE_MAX_EPSILON_S` to absorb float-accumulation
    residue only. Never the caller's own (possibly wider) ``max_s``
    parameter, because that constant is what ``client/transport.py``'s
    ``max_audio_seconds_per_request`` actually enforces as a hard refusal.
    Fail-closed: a violation raises rather than shipping a manifest a real
    flight's transport layer would refuse mid-run. A slice that clears this
    check is shipped at its own computed ``(start, end)`` bounds, unrounded
    and unclamped -- this guard only ever decides accept/refuse, it never
    rewrites slice geometry."""

    for sl in slices:
        if sl.duration > TRANSPORT_SLICE_MAX_S + TRANSPORT_SLICE_MAX_EPSILON_S:
            raise TransportBoundViolation(
                f"slice {sl.index} (start={sl.start}, end={sl.end}) has duration {sl.duration}s, which "
                f"exceeds the transport layer's hard cap TRANSPORT_SLICE_MAX_S={TRANSPORT_SLICE_MAX_S}s "
                f"(+ float-accumulation epsilon {TRANSPORT_SLICE_MAX_EPSILON_S}s) -- "
                "a slice plan must never carry a slice client/transport.py would refuse to send"
            )


def _finalize_slice_plan(
    meeting_id: str, mode: SlicePlanMode, turn_provenance: BoundaryProvenance | None, total_duration_s: float,
    slices: Sequence[Slice],
) -> SlicePlan:
    _assert_transport_bound(slices)
    payload = _plan_payload(meeting_id, mode, turn_provenance, total_duration_s, slices)
    return SlicePlan(
        meeting_id=meeting_id,
        mode=mode,
        turn_provenance=turn_provenance,
        total_duration_s=total_duration_s,
        slices=tuple(slices),
        content_hash=config_hash(payload),
    )


# ---------------------------------------------------------------------------
# VAD/grid mode (the explicit fallback/ablation mode -- signal only)
# ---------------------------------------------------------------------------


def _snap_boundary(nominal_t: float, transitions: Sequence[float], *, window_s: float) -> tuple[float, bool]:
    candidates = [tr for tr in transitions if abs(tr - nominal_t) <= window_s]
    if not candidates:
        return nominal_t, False
    best = min(candidates, key=lambda tr: (abs(tr - nominal_t), tr))
    return best, True


def _leading_trailing_trim(total_duration_s: float, transitions: Sequence[float]) -> tuple[float, float]:
    """How much non-speech to trim off the very front and very back of the
    file before tiling (VAD mode's counterpart of turn-aware mode's "first
    slice starts at the first turn" rule -- module docstring, "trim
    leading/trailing non-speech below an energy floor before packing").

    ``transitions`` is the flat, sorted, deduplicated set of pause-run
    boundary points :func:`detect_energy_pause_transitions` emits -- each
    qualifying non-speech run contributes BOTH its start and its end, so a
    leading run shows up as ``transitions[0] == 0.0`` paired with
    ``transitions[1]`` (its end), and a trailing run as
    ``transitions[-1] == total_duration_s`` paired with ``transitions[-2]``
    (its start). A lone, unpaired transition that happens to equal ``0.0``
    or ``total_duration_s`` (e.g. a hand-built test fixture passing a
    single snap point rather than a real detector's pair) is NOT treated
    as a leading/trailing run: trimming only fires when a full pair is
    present, so this stays a no-op for every existing caller that hands in
    an arbitrary transition list rather than real pause-run pairs."""

    if len(transitions) < 2:
        return 0.0, 0.0
    ordered = sorted(transitions)
    leading = ordered[1] if math.isclose(ordered[0], 0.0, abs_tol=1e-6) else 0.0
    trailing = (
        total_duration_s - ordered[-2]
        if math.isclose(ordered[-1], total_duration_s, abs_tol=1e-6)
        else 0.0
    )
    if leading < 0.0:
        leading = 0.0
    if trailing < 0.0:
        trailing = 0.0
    # Guard against adjacent/overlapping runs collapsing the packable
    # window to nothing (or negative) -- fall back to no trim rather than
    # produce an empty plan for real audio.
    if leading + trailing >= total_duration_s:
        return 0.0, 0.0
    return leading, trailing


def _grid_walk_with_snap(
    total_duration_s: float,
    transitions: Sequence[float],
    *,
    nominal_s: float,
    min_s: float,
    max_s: float,
    snap_s: float,
) -> list[tuple[float, float, bool]]:
    """Tile ``[0, total_duration_s)`` into non-overlapping bounds: each
    interior boundary snaps (±``snap_s``) to the nearest transition in
    ``transitions`` when one keeps the resulting slice within
    ``[min_s, max_s]``; otherwise the boundary falls back to the unsnapped
    grid point (``start + nominal_s``). The final slice may be short; a
    too-short final slice is merged back into its predecessor only if the
    merge does not exceed ``max_s`` ("no merging back past 120s")."""

    if total_duration_s <= 0:
        return []

    bounds: list[tuple[float, float, bool]] = []
    start = 0.0
    while start < total_duration_s - 1e-9:
        nominal_end = start + nominal_s
        if nominal_end >= total_duration_s - 1e-9:
            end, snapped = total_duration_s, False
        else:
            snapped_end, did_snap = _snap_boundary(nominal_end, transitions, window_s=snap_s)
            candidate_len = snapped_end - start
            if did_snap and min_s <= candidate_len <= max_s:
                end, snapped = snapped_end, True
            else:
                end, snapped = nominal_end, False
        bounds.append((start, end, snapped))
        start = end

    if len(bounds) >= 2:
        last_start, last_end, last_snapped = bounds[-1]
        if (last_end - last_start) < min_s:
            prev_start, prev_end, prev_snapped = bounds[-2]
            if (last_end - prev_start) <= max_s:
                bounds = bounds[:-2] + [(prev_start, last_end, False)]

    return bounds


def build_vad_slice_plan(
    meeting_id: str,
    total_duration_s: float,
    *,
    pause_transitions: Sequence[float] = (),
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
) -> SlicePlan:
    """Pure, deterministic VAD/grid transport-slice plan: no audio I/O --
    ``total_duration_s`` and ``pause_transitions`` (signal-derived
    speech/non-speech transition times, see
    :func:`detect_energy_pause_transitions` for the real-audio source of
    these) are plain inputs, so this is fully testable on synthetic
    fixtures."""

    _validate_bounds(nominal_s, min_s, max_s, snap_s)
    if not math.isfinite(total_duration_s) or total_duration_s < 0:
        raise SlicerError(f"total_duration_s must be a finite, non-negative number, got {total_duration_s!r}")

    # Trim leading/trailing non-speech BEFORE tiling (module docstring) --
    # never fold it into an edge slice the way the pre-fix turn-aware
    # gap-tiling step used to. Reuse the same [0, packable) walk by
    # shifting the transitions into the trimmed frame, then shift the
    # resulting bounds back.
    leading_trim, trailing_trim = _leading_trailing_trim(total_duration_s, pause_transitions)
    packable_duration_s = total_duration_s - leading_trim - trailing_trim
    shifted_transitions = [t - leading_trim for t in pause_transitions]
    raw = _grid_walk_with_snap(
        packable_duration_s, shifted_transitions, nominal_s=nominal_s, min_s=min_s, max_s=max_s, snap_s=snap_s
    )
    slices = tuple(
        Slice(index=i, start=s + leading_trim, end=e + leading_trim, vad_snap_applied=snapped)
        for i, (s, e, snapped) in enumerate(raw)
    )
    return _finalize_slice_plan(meeting_id, SlicePlanMode.VAD, None, total_duration_s, slices)


# ---------------------------------------------------------------------------
# turn-aware mode (primary packing mode when an admissible turn table is
# available -- 2026-08-18 diarization-aware slicer amendment)
# ---------------------------------------------------------------------------


def _pack_turn_groups(turns: Sequence[TurnSpan], *, nominal_s: float, max_s: float) -> list[list[int]]:
    """Greedily group CONSECUTIVE turn indices so that a group never spans
    more than ``max_s`` and closes as soon as it reaches ``nominal_s`` --
    "pack consecutive turns greedily into ~90s slices" (amendment). A turn
    whose OWN duration exceeds ``max_s`` becomes its own singleton group
    (the internal-VAD-split exception, handled by the caller)."""

    groups: list[list[int]] = []
    current: list[int] = []
    for i, turn in enumerate(turns):
        turn_len = turn.end - turn.start
        if turn_len > max_s:
            if current:
                groups.append(current)
                current = []
            groups.append([i])
            continue
        if not current:
            current = [i]
            continue
        group_start = turns[current[0]].start
        candidate_len = turn.end - group_start
        if candidate_len <= max_s:
            current.append(i)
            if candidate_len >= nominal_s:
                groups.append(current)
                current = []
        else:
            groups.append(current)
            current = [i]
    if current:
        groups.append(current)
    return groups


def build_turn_aware_slice_plan(
    meeting_id: str,
    turns: Sequence[TurnSpan],
    *,
    turn_provenance: BoundaryProvenance,
    allow_oracle_turns: bool = False,
    total_duration_s: float | None = None,
    fallback_pause_transitions: Sequence[float] = (),
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
) -> SlicePlan:
    """Turn-aware transport-slice plan: packs consecutive turns greedily
    into ``~nominal_s`` slices, cutting ONLY at turn boundaries -- never
    mid-turn. A single turn longer than ``max_s`` is the one exception,
    split internally via the VAD/grid walk on that turn's own span (using
    ``fallback_pause_transitions`` restricted to it).

    ``turn_provenance`` is gated exactly like AMI's gold topic marks
    (:mod:`.leakage`): a Tier-M1 provenance (``ORACLE_TURN``, i.e. an
    AMI/ICSI gold diarization layer) raises
    :class:`~.leakage.BoundaryLeakageTierViolation` unless
    ``allow_oracle_turns=True`` is passed explicitly from a declared
    ceiling arm. Tier-M0 provenances (``SIGNAL``, ``TOOL_DIAR``,
    ``SHIPPED_MATERIALS``) are always admissible.
    """

    _validate_bounds(nominal_s, min_s, max_s, snap_s)
    assert_runtime_admissible(turn_provenance, allow_oracle=allow_oracle_turns, label="turn table provenance")

    ordered = sorted((t.validate() for t in turns), key=lambda t: (t.start, t.end))
    if not ordered:
        return _finalize_slice_plan(meeting_id, SlicePlanMode.TURN_AWARE, turn_provenance, total_duration_s or 0.0, ())

    groups = _pack_turn_groups(ordered, nominal_s=nominal_s, max_s=max_s)

    bounds: list[tuple[float, float, bool]] = []
    for group in groups:
        if len(group) == 1:
            turn = ordered[group[0]]
            turn_len = turn.end - turn.start
            if turn_len > max_s:
                # Exception: split this one over-long turn internally at
                # VAD pauses, on its own local timeline.
                local_transitions = [p - turn.start for p in fallback_pause_transitions if turn.start <= p <= turn.end]
                sub_plan = build_vad_slice_plan(
                    f"{meeting_id}-turn-internal",
                    turn_len,
                    pause_transitions=local_transitions,
                    nominal_s=nominal_s,
                    min_s=min_s,
                    max_s=max_s,
                    snap_s=snap_s,
                )
                for sub in sub_plan.slices:
                    bounds.append((turn.start + sub.start, turn.start + sub.end, sub.vad_snap_applied))
                continue
        group_start = ordered[group[0]].start
        group_end = ordered[group[-1]].end
        bounds.append((group_start, group_end, False))

    # Merge an undersized trailing bound into its predecessor, same
    # "no merging back past max_s" rule as VAD mode.
    if len(bounds) >= 2:
        last_start, last_end, _ = bounds[-1]
        if (last_end - last_start) < min_s:
            prev_start, prev_end, _ = bounds[-2]
            if (last_end - prev_start) <= max_s:
                bounds = bounds[:-2] + [(prev_start, last_end, False)]

    # Tile inter-turn silence gaps at their midpoint (never inside a turn,
    # by construction) rather than dropping that audio -- room-capped: each
    # neighbor absorbs at most the room it has left under ``max_s``, with
    # any leftover spilling to the other side's remaining room, and silence
    # the pair cannot absorb staying uncovered rather than oversizing a
    # slice. (A flat midpoint split used to push a near-cap group past
    # ``max_s`` whenever a wide silence gap adjoined it -- first hit on
    # TS3004d's real AMI oracle turn table during the 2026-08-19 DIAR-SMOKE
    # read: a 101.1s group + half of a 48.3s gap = 125.3s > 120s,
    # TransportBoundViolation at finalize. When both rooms cover their
    # halves the split IS the plain midpoint, so every previously-valid
    # plan is unchanged.) The OUTER edges
    # (before the first turn, after the last turn) are different: that
    # silence is not between two turns needing a midpoint split, it is
    # leading/trailing non-speech the meeting may carry arbitrarily much
    # of. The first slice therefore starts at the first turn's own start,
    # the last slice ends at the last turn's own end, each pulled back/out
    # by AT MOST ``snap_s`` (the same margin VAD-mode snapping already
    # uses) and clamped to the known meeting span -- never all the way to
    # absolute 0 / total_duration_s, which is what used to tile arbitrary
    # leading/trailing silence straight into an edge slice and push it past
    # TRANSPORT_SLICE_MAX_S (docs/readiness/2026-08-18-chunk-slice-
    # granularity-analysis.md SS8.1; observed on real AMI turn tables via
    # scripts/build_pattr_manifest.py's find_oversized_slices). The margin
    # actually applied is further capped to whatever room is left under
    # ``max_s`` for that edge slice: gap-midpoint tiling above may already
    # have pulled an edge slice's own boundary close to ``max_s``, and a
    # flat ``snap_s`` push on top of that (observed on a real synthetic
    # fixture: a 117.5s edge slice + a flat 3s push = 120.5s) is exactly
    # the kind of small overshoot :func:`_assert_transport_bound` exists to
    # catch -- so the margin here is room-aware instead of flat, and never
    # produces a violation in the first place.
    tiled: list[list[float]] = [[s, e] for s, e, _ in bounds]
    for k in range(len(tiled) - 1):
        gap_end = tiled[k][1]
        gap_start = tiled[k + 1][0]
        if gap_start > gap_end:
            gap = gap_start - gap_end
            left_room = max(0.0, max_s - (tiled[k][1] - tiled[k][0]))
            right_room = max(0.0, max_s - (tiled[k + 1][1] - tiled[k + 1][0]))
            take_left = min(gap / 2.0, left_room)
            take_right = min(gap - take_left, right_room)
            take_left = min(gap - take_right, left_room)  # spill right's shortfall back left
            tiled[k][1] = gap_end + take_left
            tiled[k + 1][0] = gap_start - take_right
    if total_duration_s is not None and tiled:
        first_start, first_end = tiled[0]
        pullback = min(snap_s, max(0.0, max_s - (first_end - first_start)))
        tiled[0][0] = max(0.0, first_start - pullback)

        # Re-read tiled[-1] (not the pre-loop ``bounds`` values): when
        # there is exactly one slice, tiled[-1] IS tiled[0], and the
        # pullback just applied above must count against this edge's own
        # remaining room too.
        last_start, last_end = tiled[-1]
        push = min(snap_s, max(0.0, max_s - (last_end - last_start)))
        extended_end = last_end + push
        tiled[-1][1] = max(last_end, min(extended_end, total_duration_s))

    final_bounds = [(s, e, snapped) for (s, e), (_, _, snapped) in zip(tiled, bounds)]
    slices_no_turns = [
        Slice(index=i, start=s, end=e, vad_snap_applied=snapped) for i, (s, e, snapped) in enumerate(final_bounds)
    ]
    turn_tables = _attach_turns([(s.start, s.end) for s in slices_no_turns], ordered)
    slices = tuple(
        Slice(index=s.index, start=s.start, end=s.end, vad_snap_applied=s.vad_snap_applied, turns=turns_for_slice)
        for s, turns_for_slice in zip(slices_no_turns, turn_tables)
    )

    duration = total_duration_s if total_duration_s is not None else slices[-1].end
    return _finalize_slice_plan(meeting_id, SlicePlanMode.TURN_AWARE, turn_provenance, duration, slices)


def _attach_turns(
    bounds: Sequence[tuple[float, float]], turns: Sequence[TurnSpan]
) -> tuple[tuple[SliceTurnEntry, ...], ...]:
    """Per-slice turn/speaker table: every turn overlapping a slice's
    ``[start, end)``, with both absolute and slice-relative offsets
    (2026-08-18 amendment item 2)."""

    result: list[tuple[SliceTurnEntry, ...]] = []
    for start, end in bounds:
        entries = []
        for t in turns:
            overlap_start = max(t.start, start)
            overlap_end = min(t.end, end)
            if overlap_end > overlap_start:
                entries.append(
                    SliceTurnEntry(
                        speaker=t.speaker,
                        absolute_start=t.start,
                        absolute_end=t.end,
                        slice_offset_start=overlap_start - start,
                        slice_offset_end=overlap_end - start,
                    )
                )
        result.append(tuple(entries))
    return tuple(result)


# ---------------------------------------------------------------------------
# real-audio I/O: signal-derived VAD, decode/normalize, cut, hash
# ---------------------------------------------------------------------------


def read_audio_duration(audio_path: Path) -> float:
    """The source audio's duration in seconds, from its header only (no
    full decode)."""

    import soundfile as sf  # lazy: heavy import stays out of this module's top level

    info = sf.info(str(audio_path))
    if info.samplerate <= 0:
        raise SlicerError(f"audio file {audio_path} reports a non-positive sample rate: {info.samplerate}")
    return float(info.frames) / float(info.samplerate)


def detect_energy_pause_transitions(
    audio_path: Path,
    *,
    frame_s: float = DEFAULT_ENERGY_FRAME_S,
    min_pause_s: float = DEFAULT_MIN_PAUSE_S,
    energy_floor_percentile: float = DEFAULT_ENERGY_FLOOR_PERCENTILE,
) -> tuple[float, ...]:
    """Signal-derived (never model-declared, never gold) pause-transition
    detector: short-time RMS energy on a ``frame_s`` grid; frames at or
    below the file's own ``energy_floor_percentile`` are non-speech. The
    START and END of every contiguous non-speech run at least
    ``min_pause_s`` long become candidate VAD transition points a slice
    boundary may snap to (analysis SS8.1: boundary source is "signal
    only... never a model-declared boundary, never a gold annotation")."""

    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    if len(y) == 0:
        return ()
    frame_len = max(1, int(round(frame_s * sr)))
    n_frames = len(y) // frame_len
    if n_frames == 0:
        return ()
    trimmed = y[: n_frames * frame_len].astype(np.float64)
    frames = trimmed.reshape(n_frames, frame_len)
    energy = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    floor = float(np.percentile(energy, energy_floor_percentile))
    is_pause = (energy <= floor).tolist()

    transitions: list[float] = []
    run_start: float | None = None
    for idx, flag in enumerate([*is_pause, False]):  # sentinel flushes a trailing run
        t = idx * frame_s
        if flag and run_start is None:
            run_start = t
        elif not flag and run_start is not None:
            if (t - run_start) >= min_pause_s:
                transitions.append(round(run_start, 6))
                transitions.append(round(t, 6))
            run_start = None
    return tuple(sorted(set(transitions)))


def plan_transport_slices_from_audio(
    audio_path: Path,
    *,
    meeting_id: str,
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
    min_pause_s: float = DEFAULT_MIN_PAUSE_S,
) -> SlicePlan:
    """VAD/grid convenience wrapper: read the real source audio's duration
    and pause structure, then delegate to the pure :func:`build_vad_slice_plan`."""

    duration = read_audio_duration(audio_path)
    transitions = detect_energy_pause_transitions(audio_path, min_pause_s=min_pause_s)
    return build_vad_slice_plan(
        meeting_id, duration, pause_transitions=transitions, nominal_s=nominal_s, min_s=min_s, max_s=max_s, snap_s=snap_s
    )


def _load_mono(source_audio_path: Path, target_sample_rate: int):
    """The declared decode -> 16 kHz mono normalization path (17-item
    change list item 8): every corpus's audio -- AMI/ICSI's native 16 kHz
    mono, MeetingBank's 44.1 kHz stereo MP3, or anything else -- goes
    through this SAME call, so slice hashes mean the same thing regardless
    of source format. ffmpeg is absent by design; librosa resamples and
    downmixes without it."""

    import librosa

    y, sr = librosa.load(str(source_audio_path), sr=target_sample_rate, mono=True)
    return y, sr


@dataclass(frozen=True)
class SliceManifestEntry:
    index: int
    start: float
    end: float
    filename: str
    sha256: str
    vad_snap_applied: bool
    encoder_chunk_count: int
    turns: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "filename": self.filename,
            "sha256": self.sha256,
            "vad_snap_applied": self.vad_snap_applied,
            "encoder_chunk_count": self.encoder_chunk_count,
            "turns": [dict(t) for t in self.turns],
        }


@dataclass(frozen=True)
class SliceManifest:
    """The frozen, per-meeting artifact (17-item change list item 16): slice
    index, offsets, sha256, VAD-snap flag, encoder-chunk count, and (turn-
    aware mode) the per-slice speaker table -- committed to the run receipt
    so a re-run provably re-sends identical bytes and the feature-cache
    reuse claim is auditable rather than assumed."""

    meeting_id: str
    mode: str
    turn_provenance: str | None
    sample_rate: int
    channels: int
    entries: tuple[SliceManifestEntry, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "mode": self.mode,
            "turn_provenance": self.turn_provenance,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "entries": [e.to_dict() for e in self.entries],
            "content_hash": self.content_hash,
        }

    def path_for(self, index: int, base_dir: Path) -> Path:
        for entry in self.entries:
            if entry.index == index:
                return Path(base_dir) / entry.filename
        raise KeyError(f"slice index {index} not in manifest for meeting {self.meeting_id!r}")


def materialize_slice_plan(
    plan: SlicePlan,
    source_audio_path: Path,
    output_dir: Path,
    *,
    sample_rate: int = 16000,
) -> SliceManifest:
    """The one real-I/O step: decode ``source_audio_path`` ONCE, normalize
    to ``sample_rate`` Hz mono, cut per ``plan``'s frozen bounds, write each
    slice as its own PCM16 WAV, and hash it. Deterministic: the same source
    bytes and the same plan always produce byte-identical slice files (and
    therefore identical sha256 digests and an identical manifest
    ``content_hash``) -- callers freeze this BEFORE any arm runs so the
    feature cache pays for the encode exactly once (analysis SS8.1)."""

    import hashlib

    import soundfile as sf

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    samples, sr = _load_mono(source_audio_path, sample_rate)

    entries: list[SliceManifestEntry] = []
    for sl in plan.slices:
        start_sample = max(0, min(int(round(sl.start * sr)), len(samples)))
        end_sample = max(start_sample, min(int(round(sl.end * sr)), len(samples)))
        clip = samples[start_sample:end_sample]
        filename = f"{plan.meeting_id}-slice{sl.index:04d}.wav"
        out_path = output_dir / filename
        sf.write(str(out_path), clip, sr, subtype="PCM_16")
        digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
        entries.append(
            SliceManifestEntry(
                index=sl.index,
                start=sl.start,
                end=sl.end,
                filename=filename,
                sha256=digest,
                vad_snap_applied=sl.vad_snap_applied,
                encoder_chunk_count=sl.encoder_chunk_count,
                turns=tuple(t.to_dict() for t in sl.turns),
            )
        )

    turn_provenance_value = plan.turn_provenance.value if plan.turn_provenance is not None else None
    payload = {
        "meeting_id": plan.meeting_id,
        "mode": plan.mode.value,
        "turn_provenance": turn_provenance_value,
        "sample_rate": sr,
        "channels": 1,
        "entries": [e.to_dict() for e in entries],
    }
    return SliceManifest(
        meeting_id=plan.meeting_id,
        mode=plan.mode.value,
        turn_provenance=turn_provenance_value,
        sample_rate=sr,
        channels=1,
        entries=tuple(entries),
        content_hash=config_hash(payload),
    )


def build_slice_manifest(
    meeting_id: str,
    source_audio_path: Path,
    output_dir: Path,
    *,
    mode: str = "vad",
    turns: Sequence[TurnSpan] = (),
    turn_provenance: BoundaryProvenance | None = None,
    allow_oracle_turns: bool = False,
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
    min_pause_s: float = DEFAULT_MIN_PAUSE_S,
    sample_rate: int = 16000,
) -> SliceManifest:
    """The top-level orchestrator: real audio in, frozen
    :class:`SliceManifest` out. ``mode="vad"`` (default, the safe fallback/
    ablation arm) needs nothing but the audio file. ``mode="turn_aware"``
    needs ``turns`` + ``turn_provenance`` (and, for a gold table,
    ``allow_oracle_turns=True`` -- module docstring)."""

    duration = read_audio_duration(source_audio_path)
    transitions = detect_energy_pause_transitions(source_audio_path, min_pause_s=min_pause_s)

    if mode == "vad":
        plan = build_vad_slice_plan(
            meeting_id, duration, pause_transitions=transitions, nominal_s=nominal_s, min_s=min_s, max_s=max_s, snap_s=snap_s
        )
    elif mode == "turn_aware":
        if turn_provenance is None:
            raise SlicerError("mode='turn_aware' requires an explicit turn_provenance")
        plan = build_turn_aware_slice_plan(
            meeting_id,
            turns,
            turn_provenance=turn_provenance,
            allow_oracle_turns=allow_oracle_turns,
            total_duration_s=duration,
            fallback_pause_transitions=transitions,
            nominal_s=nominal_s,
            min_s=min_s,
            max_s=max_s,
            snap_s=snap_s,
        )
    else:
        raise SlicerError(f"unknown slicer mode: {mode!r} (expected 'vad' or 'turn_aware')")

    return materialize_slice_plan(plan, source_audio_path, output_dir, sample_rate=sample_rate)


def make_audio_chunk_resolver(manifest: SliceManifest, base_dir: Path) -> Callable[[int], tuple[Path, float]]:
    """Build a slice-index-keyed resolver ``Callable[[int], (Path,
    audio_seconds)]`` from a frozen :class:`SliceManifest` -- the real
    counterpart of the ``audio_chunk_resolver`` that
    :mod:`meeting_minutes_agent.controller.loop` currently only receives as
    test fakes (17-item change list item 9). Keyed by SLICE index, not task-
    chunk index: a task chunk spans multiple slices (SS8.2), so only a
    slice-level resolver can honor "never more than one slice per request"
    (SS8.1/item 10). Wiring this into the per-task-chunk dispatch loop (so
    a ``transcribe_span`` task fans out one core call per slice) is
    tracked as follow-up integration work, not implemented in this module."""

    base_dir = Path(base_dir)
    by_index = {e.index: e for e in manifest.entries}

    def resolve(slice_index: int) -> tuple[Path, float]:
        entry = by_index.get(slice_index)
        if entry is None:
            raise KeyError(f"slice index {slice_index} not in manifest for meeting {manifest.meeting_id!r}")
        return base_dir / entry.filename, entry.end - entry.start

    return resolve


__all__ = [
    "DEFAULT_MIN_PAUSE_S",
    "DEFAULT_ENERGY_FLOOR_PERCENTILE",
    "DEFAULT_ENERGY_FRAME_S",
    "SlicerError",
    "TransportBoundViolation",
    "TRANSPORT_SLICE_MAX_EPSILON_S",
    "TurnSpan",
    "SliceTurnEntry",
    "Slice",
    "SlicePlanMode",
    "SlicePlan",
    "build_vad_slice_plan",
    "build_turn_aware_slice_plan",
    "read_audio_duration",
    "detect_energy_pause_transitions",
    "plan_transport_slices_from_audio",
    "SliceManifestEntry",
    "SliceManifest",
    "materialize_slice_plan",
    "build_slice_manifest",
    "make_audio_chunk_resolver",
]
