"""Tests for :mod:`meeting_minutes_agent.precomp.metrics`: pure descriptive
metrics (turn counts, slice counts + delta, boundary-displacement
distribution, cache before/after, walls) -- never a verdict."""

from __future__ import annotations

from pathlib import Path

from meeting_minutes_agent.chunking.diarization import DiarizationResult
from meeting_minutes_agent.chunking.leakage import BoundaryProvenance
from meeting_minutes_agent.chunking.slicer import TurnSpan, build_vad_slice_plan
from meeting_minutes_agent.precomp.metrics import (
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


def _result(n_turns: int, provenance: BoundaryProvenance = BoundaryProvenance.TOOL_DIAR) -> DiarizationResult:
    turns = tuple(TurnSpan(start=float(i), end=float(i) + 0.5, speaker="A") for i in range(n_turns))
    return DiarizationResult(turns=turns, provenance=provenance)


# ---------------------------------------------------------------------------
# turn_counts / slice_counts
# ---------------------------------------------------------------------------


def test_turn_counts_reports_both_sides_independently():
    assert turn_counts(_result(5), _result(3)) == {"tool_turns": 5, "oracle_turns": 3}


def test_slice_counts_reports_delta_tool_minus_oracle():
    tool_plan = build_vad_slice_plan("m1", 400.0)  # 5 slices
    oracle_plan = build_vad_slice_plan("m1", 200.0)  # 3 slices
    counts = slice_counts(tool_plan, oracle_plan)
    assert counts["tool_slices"] == len(tool_plan.slices)
    assert counts["oracle_slices"] == len(oracle_plan.slices)
    assert counts["delta"] == len(tool_plan.slices) - len(oracle_plan.slices)


# ---------------------------------------------------------------------------
# interior_boundaries
# ---------------------------------------------------------------------------


def test_interior_boundaries_empty_for_zero_or_one_slice():
    empty_plan = build_vad_slice_plan("m1", 0.0)
    assert interior_boundaries(empty_plan) == ()

    one_slice_plan = build_vad_slice_plan("m1", 50.0)  # under min_s -> stays a single slice
    assert len(one_slice_plan.slices) == 1
    assert interior_boundaries(one_slice_plan) == ()


def test_interior_boundaries_excludes_leading_and_trailing_edges():
    plan = build_vad_slice_plan("m1", 400.0)
    bounds = interior_boundaries(plan)
    assert len(bounds) == len(plan.slices) - 1
    assert 0.0 not in bounds
    assert plan.slices[-1].end not in bounds
    assert bounds == tuple(sl.start for sl in plan.slices[1:])


# ---------------------------------------------------------------------------
# boundary_displacement_distribution
# ---------------------------------------------------------------------------


def test_boundary_displacement_distribution_zero_when_plans_are_identical():
    plan = build_vad_slice_plan("m1", 400.0)
    dist = boundary_displacement_distribution(plan, plan)
    assert dist["n"] == len(interior_boundaries(plan))
    assert dist["max_s"] == 0.0
    assert dist["min_s"] == 0.0
    assert dist["mean_s"] == 0.0
    assert dist["median_s"] == 0.0
    assert dist["displacements_s"] == sorted(dist["displacements_s"])  # always sorted


def test_boundary_displacement_distribution_empty_when_either_plan_has_no_interior_boundary():
    single = build_vad_slice_plan("m1", 50.0)
    multi = build_vad_slice_plan("m1", 400.0)
    dist = boundary_displacement_distribution(single, multi)
    assert dist == {"n": 0, "displacements_s": [], "min_s": None, "max_s": None, "mean_s": None, "median_s": None}


def test_boundary_displacement_distribution_nearest_neighbour_not_positional():
    # Tool plan has one interior boundary at 90.0 (nominal grid, 400s -> 5
    # slices); oracle plan is built with a snap-able transition placed 4s
    # away, so the nearest-neighbour distance is a small, known number, not
    # a positional (index) comparison across differently-shaped plans.
    tool_plan = build_vad_slice_plan("m1", 400.0)
    oracle_plan = build_vad_slice_plan("m1", 400.0, pause_transitions=(86.0, 94.0))
    dist = boundary_displacement_distribution(tool_plan, oracle_plan)
    assert dist["n"] == len(interior_boundaries(tool_plan))
    assert dist["min_s"] >= 0.0
    assert dist["max_s"] >= dist["min_s"]


# ---------------------------------------------------------------------------
# snapshot_cache_dir / cache_delta
# ---------------------------------------------------------------------------


def test_snapshot_cache_dir_missing_directory_is_zero(tmp_path):
    assert snapshot_cache_dir(tmp_path / "does-not-exist") == {"n_entries": 0, "total_bytes": 0}


def test_snapshot_cache_dir_counts_files_recursively(tmp_path: Path):
    cache = tmp_path / "cache"
    (cache / "sub").mkdir(parents=True)
    (cache / "a.bin").write_bytes(b"1234")
    (cache / "sub" / "b.bin").write_bytes(b"123456")
    snap = snapshot_cache_dir(cache)
    assert snap == {"n_entries": 2, "total_bytes": 10}


def test_cache_delta_computes_added_entries_and_bytes():
    before = {"n_entries": 2, "total_bytes": 100}
    after = {"n_entries": 5, "total_bytes": 340}
    assert cache_delta(before, after) == {"entries_added": 3, "bytes_added": 240}


# ---------------------------------------------------------------------------
# wall_summary
# ---------------------------------------------------------------------------


def test_wall_summary_sums_the_three_phases():
    walls = wall_summary(diar_wall_s=1.0, cutting_wall_s=2.0, encode_wall_s=3.0)
    assert walls == {"diar_wall_s": 1.0, "cutting_wall_s": 2.0, "encode_wall_s": 3.0, "total_wall_s": 6.0}


# ---------------------------------------------------------------------------
# build_meeting_metrics: composition
# ---------------------------------------------------------------------------


def test_build_meeting_metrics_composes_every_block():
    tool_plan = build_vad_slice_plan("m1", 400.0)
    oracle_plan = build_vad_slice_plan("m1", 200.0)
    metrics = build_meeting_metrics(
        tool_result=_result(4),
        oracle_result=_result(2),
        tool_plan=tool_plan,
        oracle_plan=oracle_plan,
        cache_before={"n_entries": 0, "total_bytes": 0},
        cache_after={"n_entries": 1, "total_bytes": 50},
        diar_wall_s=1.0,
        cutting_wall_s=2.0,
        encode_wall_s=3.0,
    )
    assert metrics["turn_counts"] == {"tool_turns": 4, "oracle_turns": 2}
    assert metrics["slice_counts"]["tool_slices"] == len(tool_plan.slices)
    assert metrics["boundary_displacement"]["n"] >= 0
    assert metrics["cache"]["delta"] == {"entries_added": 1, "bytes_added": 50}
    assert metrics["walls"]["total_wall_s"] == 6.0
    assert "vad_slice_count" not in metrics  # no vad_plan given


# ---------------------------------------------------------------------------
# vad_slice_count / build_meeting_metrics: the VAD turn source (the G1
# Z-nodiar-ablation PRECOMP supplement)
# ---------------------------------------------------------------------------


def test_vad_slice_count_reports_the_plan_size():
    plan = build_vad_slice_plan("m1", 400.0)  # 5 slices
    assert vad_slice_count(plan) == {"vad_slices": len(plan.slices)}


def test_build_meeting_metrics_vad_only_never_claims_a_tool_oracle_comparison():
    vad_plan = build_vad_slice_plan("m1", 400.0)
    metrics = build_meeting_metrics(
        vad_plan=vad_plan,
        cache_before={"n_entries": 0, "total_bytes": 0},
        cache_after={"n_entries": 2, "total_bytes": 80},
        cutting_wall_s=1.0,
        encode_wall_s=2.0,
    )
    assert metrics["vad_slice_count"] == {"vad_slices": len(vad_plan.slices)}
    assert "turn_counts" not in metrics
    assert "slice_counts" not in metrics
    assert "boundary_displacement" not in metrics
    assert metrics["cache"]["delta"] == {"entries_added": 2, "bytes_added": 80}
    assert metrics["walls"] == {"diar_wall_s": 0.0, "cutting_wall_s": 1.0, "encode_wall_s": 2.0, "total_wall_s": 3.0}


def test_build_meeting_metrics_all_three_sources_together():
    tool_plan = build_vad_slice_plan("m1", 400.0)
    oracle_plan = build_vad_slice_plan("m1", 200.0)
    vad_plan = build_vad_slice_plan("m1", 300.0)
    metrics = build_meeting_metrics(
        tool_result=_result(4),
        oracle_result=_result(2),
        tool_plan=tool_plan,
        oracle_plan=oracle_plan,
        vad_plan=vad_plan,
        cache_before={"n_entries": 0, "total_bytes": 0},
        cache_after={"n_entries": 1, "total_bytes": 50},
        diar_wall_s=1.0,
        cutting_wall_s=2.0,
        encode_wall_s=3.0,
    )
    for key in ("turn_counts", "slice_counts", "boundary_displacement", "vad_slice_count", "cache", "walls"):
        assert key in metrics
    assert metrics["vad_slice_count"] == {"vad_slices": len(vad_plan.slices)}
