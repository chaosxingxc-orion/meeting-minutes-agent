"""PRECOMP descriptive metrics -- pure functions, no I/O beyond the one
filesystem walk :func:`snapshot_cache_dir` performs.

Registered scope (``docs/readiness/2026-08-19-precomp-preregistration.md``
SS5): "Per meeting: turn counts, slice counts (tool vs oracle, count
delta), boundary-displacement distribution (descriptive; the positional
packing-change fraction is RETIRED as saturated per the smoke read), cache
entries added/bytes, encode wall, diar wall." This pass renders no
verdicts -- every function here returns a plain descriptive dict, never a
pass/fail judgement.

Boundary-displacement distribution is the RETIRED metric's successor: the
smoke read (``docs/readiness/2026-08-18-diar-smoke-verdict.md`` /
``172d899``) found the old binary "did this boundary position change
Y/N" packing-change fraction SATURATED at 117/117 on every meeting -- a
metric with zero remaining discriminative range. Its replacement measures
magnitude instead of a saturated binary: for every INTERIOR slice boundary
the tool-turn plan emits (a boundary between two consecutive slices --
never the plan's own leading/trailing edge, which is a meeting-span anchor,
not a packing decision), the distance in seconds to the nearest interior
boundary the independently-built oracle-turn plan emits over the SAME
audio. A distribution of these nearest-neighbour distances, not a single
number, so a later G1 read can characterize the whole shape (median vs.
tail) rather than lose it to one aggregate.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..chunking.diarization import DiarizationResult
    from ..chunking.slicer import SlicePlan


def turn_counts(tool_result: "DiarizationResult", oracle_result: "DiarizationResult") -> dict[str, int]:
    """Raw turn-table sizes for one meeting's two independently-built
    sources (module docstring)."""

    return {"tool_turns": len(tool_result.turns), "oracle_turns": len(oracle_result.turns)}


def slice_counts(tool_plan: "SlicePlan", oracle_plan: "SlicePlan") -> dict[str, int]:
    """Slice-plan sizes plus the signed count delta (tool minus oracle) --
    prereg SS5's "slice counts (tool vs oracle, count delta)"."""

    n_tool = len(tool_plan.slices)
    n_oracle = len(oracle_plan.slices)
    return {"tool_slices": n_tool, "oracle_slices": n_oracle, "delta": n_tool - n_oracle}


def interior_boundaries(plan: "SlicePlan") -> tuple[float, ...]:
    """Every boundary BETWEEN two consecutive slices in ``plan`` -- i.e.
    every slice's own ``start`` except the first (module docstring: the
    plan's leading and trailing edges are meeting-span anchors, not a
    packing decision between two turn groups, so they carry no comparable
    "did packing choose this point" signal). ``()`` for a plan with fewer
    than two slices, which has no interior boundary at all."""

    if len(plan.slices) < 2:
        return ()
    return tuple(sl.start for sl in plan.slices[1:])


def boundary_displacement_distribution(tool_plan: "SlicePlan", oracle_plan: "SlicePlan") -> dict[str, Any]:
    """The nearest-neighbour interior-boundary displacement distribution,
    tool plan against oracle plan, in seconds (module docstring). One entry
    per tool-plan interior boundary: the distance to the CLOSEST
    oracle-plan interior boundary, never a positional (index-aligned)
    pairing -- the two plans are built from independent turn sources and
    may carry different slice counts, so index alignment would compare
    unrelated boundaries. Empty (``n=0``) when either plan has no interior
    boundary to compare (e.g. a very short meeting packed into a single
    slice) -- never a crash, and never a fabricated distance."""

    tool_bounds = interior_boundaries(tool_plan)
    oracle_bounds = interior_boundaries(oracle_plan)
    if not tool_bounds or not oracle_bounds:
        return {"n": 0, "displacements_s": [], "min_s": None, "max_s": None, "mean_s": None, "median_s": None}

    displacements = sorted(min(abs(t - o) for o in oracle_bounds) for t in tool_bounds)
    n = len(displacements)
    mid = n // 2
    median = displacements[mid] if n % 2 == 1 else (displacements[mid - 1] + displacements[mid]) / 2.0
    return {
        "n": n,
        "displacements_s": displacements,
        "min_s": displacements[0],
        "max_s": displacements[-1],
        "mean_s": sum(displacements) / n,
        "median_s": median,
    }


def snapshot_cache_dir(path: Path | str) -> dict[str, int]:
    """A shallow, deterministic snapshot of a feature-cache directory
    (``meeting_minutes_agent.client.featcache``): file count and total
    bytes, recursively. ``{"n_entries": 0, "total_bytes": 0}`` for a
    directory that does not exist yet -- the "cache before" snapshot taken
    ahead of a wave's very first contact, before the cache directory has
    even been created."""

    resolved = Path(path)
    if not resolved.is_dir():
        return {"n_entries": 0, "total_bytes": 0}
    n_entries = 0
    total_bytes = 0
    for entry in resolved.rglob("*"):
        if entry.is_file():
            n_entries += 1
            total_bytes += entry.stat().st_size
    return {"n_entries": n_entries, "total_bytes": total_bytes}


def cache_delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, int]:
    """``after`` minus ``before`` on both :func:`snapshot_cache_dir`
    fields -- "cache entries added/bytes" (prereg SS5)."""

    return {
        "entries_added": int(after["n_entries"]) - int(before["n_entries"]),
        "bytes_added": int(after["total_bytes"]) - int(before["total_bytes"]),
    }


def wall_summary(*, diar_wall_s: float, cutting_wall_s: float, encode_wall_s: float) -> dict[str, float]:
    """"encode wall, diar wall" (prereg SS5), plus the CPU-cutting wall
    (this pass's third real-work phase) and a convenience total."""

    return {
        "diar_wall_s": diar_wall_s,
        "cutting_wall_s": cutting_wall_s,
        "encode_wall_s": encode_wall_s,
        "total_wall_s": diar_wall_s + cutting_wall_s + encode_wall_s,
    }


def build_meeting_metrics(
    *,
    tool_result: "DiarizationResult",
    oracle_result: "DiarizationResult",
    tool_plan: "SlicePlan",
    oracle_plan: "SlicePlan",
    cache_before: Mapping[str, int],
    cache_after: Mapping[str, int],
    diar_wall_s: float,
    cutting_wall_s: float,
    encode_wall_s: float,
) -> dict[str, Any]:
    """One meeting's whole descriptive-metrics block (prereg SS5), composed
    from the pure functions above -- the shape
    :mod:`meeting_minutes_agent.precomp.receipts`' ``MeetingReceipt``
    carries as its ``metrics`` field."""

    return {
        "turn_counts": turn_counts(tool_result, oracle_result),
        "slice_counts": slice_counts(tool_plan, oracle_plan),
        "boundary_displacement": boundary_displacement_distribution(tool_plan, oracle_plan),
        "cache": {
            "before": dict(cache_before),
            "after": dict(cache_after),
            "delta": cache_delta(cache_before, cache_after),
        },
        "walls": wall_summary(diar_wall_s=diar_wall_s, cutting_wall_s=cutting_wall_s, encode_wall_s=encode_wall_s),
    }


__all__ = [
    "turn_counts",
    "slice_counts",
    "interior_boundaries",
    "boundary_displacement_distribution",
    "snapshot_cache_dir",
    "cache_delta",
    "wall_summary",
    "build_meeting_metrics",
]
