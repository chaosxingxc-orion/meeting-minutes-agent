"""Tests for ``scripts/build_pattr_manifest.py``'s pure helpers (selection,
plan truncation, covered-turn extraction -- no I/O) and its one real-I/O
helper (turn-clip materialization), exercised on a tiny SYNTHETIC WAV
fixture generated in-process -- never real AMI bytes, per this repository's
own "unit tests stay on tiny synthetic fixtures" convention
(``tests/integration/test_real_ami_meeting.py`` module docstring)."""

from __future__ import annotations

import hashlib

import build_pattr_manifest as bpm
import numpy as np
import pytest
import soundfile as sf

from meeting_minutes_agent.chunking.leakage import BoundaryProvenance
from meeting_minutes_agent.chunking.slicer import TurnSpan, build_turn_aware_slice_plan

# ---------------------------------------------------------------------------
# select_meetings: pure, deterministic
# ---------------------------------------------------------------------------

_POOL = ("M1", "M2", "M3", "M4", "M5", "M6")


def test_select_meetings_is_deterministic_for_the_same_seed():
    a = bpm.select_meetings(_POOL, seed=20260818, n=3)
    b = bpm.select_meetings(_POOL, seed=20260818, n=3)
    assert a == b


def test_select_meetings_returns_n_distinct_members_of_the_pool():
    selected = bpm.select_meetings(_POOL, seed=1, n=4)
    assert len(selected) == 4
    assert len(set(selected)) == 4
    assert set(selected) <= set(_POOL)


def test_select_meetings_pool_order_does_not_matter():
    shuffled_pool = ("M6", "M1", "M4", "M2", "M5", "M3")
    a = bpm.select_meetings(_POOL, seed=42, n=3)
    b = bpm.select_meetings(shuffled_pool, seed=42, n=3)
    assert a == b


def test_select_meetings_different_seed_can_differ():
    a = bpm.select_meetings(_POOL, seed=1, n=3)
    b = bpm.select_meetings(_POOL, seed=2, n=3)
    assert a != b  # not guaranteed in general, but true for this pool/seed pair


def test_select_meetings_rejects_n_larger_than_pool():
    with pytest.raises(ValueError):
        bpm.select_meetings(_POOL, seed=1, n=len(_POOL) + 1)


def test_select_meetings_rejects_non_positive_n():
    with pytest.raises(ValueError):
        bpm.select_meetings(_POOL, seed=1, n=0)


def test_pattr_manifest_uses_the_real_dev18_minus_ib_candidate_pool():
    # The mission's own instruction: dev-18 minus the six IB meetings.
    assert set(bpm.CANDIDATE_POOL) == {
        "ES2011a", "ES2011b", "ES2011c", "ES2011d",
        "IS1008a", "IS1008b", "IS1008c", "IS1008d",
        "TS3004a", "TS3004b", "TS3004c", "TS3004d",
    }
    assert not any(m.startswith("IB") for m in bpm.CANDIDATE_POOL)


# ---------------------------------------------------------------------------
# truncate_slice_plan: pure
# ---------------------------------------------------------------------------


def _synthetic_full_plan():
    # Six 60s-ish turns, alternating speakers, over a 360s meeting -- packs
    # into several ~90s slices under the default bounds.
    turns = tuple(
        TurnSpan(start=float(i * 60), end=float(i * 60 + 55), speaker=("A" if i % 2 == 0 else "B"))
        for i in range(6)
    )
    return build_turn_aware_slice_plan(
        "SYN1", turns, turn_provenance=BoundaryProvenance.ORACLE_TURN, allow_oracle_turns=True, total_duration_s=360.0
    )


def test_truncate_slice_plan_keeps_only_the_first_n_slices():
    full_plan = _synthetic_full_plan()
    assert len(full_plan.slices) > 2  # fixture must actually produce more than we truncate to
    truncated = bpm.truncate_slice_plan(full_plan, 2)
    assert len(truncated.slices) == 2
    assert [s.index for s in truncated.slices] == [0, 1]


def test_truncate_slice_plan_recomputes_total_duration_and_hash():
    full_plan = _synthetic_full_plan()
    truncated = bpm.truncate_slice_plan(full_plan, 2)
    assert truncated.total_duration_s == truncated.slices[-1].end
    assert truncated.content_hash != full_plan.content_hash
    assert truncated.meeting_id == full_plan.meeting_id
    assert truncated.turn_provenance == full_plan.turn_provenance


def test_truncate_slice_plan_is_deterministic():
    full_plan = _synthetic_full_plan()
    a = bpm.truncate_slice_plan(full_plan, 3)
    b = bpm.truncate_slice_plan(full_plan, 3)
    assert a.content_hash == b.content_hash
    assert a.slices == b.slices


def test_truncate_slice_plan_no_op_when_max_exceeds_slice_count():
    full_plan = _synthetic_full_plan()
    truncated = bpm.truncate_slice_plan(full_plan, len(full_plan.slices) + 10)
    assert truncated.slices == full_plan.slices


def test_truncate_slice_plan_rejects_non_positive_max():
    full_plan = _synthetic_full_plan()
    with pytest.raises(ValueError):
        bpm.truncate_slice_plan(full_plan, 0)


# ---------------------------------------------------------------------------
# extract_covered_turns: pure
# ---------------------------------------------------------------------------


def test_extract_covered_turns_deduplicates_and_orders_chronologically():
    full_plan = _synthetic_full_plan()
    truncated = bpm.truncate_slice_plan(full_plan, 2)
    covered = bpm.extract_covered_turns(truncated.slices)

    # Chronological order.
    starts = [c["absolute_start"] for c in covered]
    assert starts == sorted(starts)

    # No duplicate (absolute_start, absolute_end, speaker) triples.
    keys = [(c["absolute_start"], c["absolute_end"], c["speaker"]) for c in covered]
    assert len(keys) == len(set(keys))

    # Every covered turn actually originates from one of the truncated slices.
    all_turn_keys = {
        (t.absolute_start, t.absolute_end, t.speaker) for sl in truncated.slices for t in sl.turns
    }
    assert set(keys) == all_turn_keys


def test_extract_covered_turns_records_slice_index():
    full_plan = _synthetic_full_plan()
    truncated = bpm.truncate_slice_plan(full_plan, 1)
    covered = bpm.extract_covered_turns(truncated.slices)
    assert covered  # the first slice must cover at least one turn
    assert all(c["slice_index"] == 0 for c in covered)


def test_extract_covered_turns_empty_slices_is_empty():
    assert bpm.extract_covered_turns(()) == ()


# ---------------------------------------------------------------------------
# materialize_turn_clips: the one real-I/O helper, on a synthetic WAV
# ---------------------------------------------------------------------------


def _write_synthetic_wav(path, *, duration_s: float = 3.0, sample_rate: int = 16000) -> None:
    t = np.linspace(0.0, duration_s, int(duration_s * sample_rate), endpoint=False)
    tone = 0.1 * np.sin(2 * np.pi * 220.0 * t)
    sf.write(str(path), tone.astype(np.float32), sample_rate, subtype="PCM_16")


def test_materialize_turn_clips_writes_hashed_files_of_expected_duration(tmp_path):
    source = tmp_path / "source.wav"
    _write_synthetic_wav(source, duration_s=3.0)

    covered_turns = [
        {"speaker": "A", "absolute_start": 0.0, "absolute_end": 1.0, "slice_index": 0},
        {"speaker": "B", "absolute_start": 1.0, "absolute_end": 2.5, "slice_index": 0},
    ]
    out_dir = tmp_path / "turn-clips" / "SYN1"
    entries = bpm.materialize_turn_clips(covered_turns, source, out_dir, meeting_id="SYN1", sample_rate=16000)

    assert len(entries) == 2
    assert entries[0]["turn_index"] == 0
    assert entries[0]["filename"] == "SYN1-turn0000.wav"
    assert entries[0]["duration_s"] == pytest.approx(1.0, abs=1e-3)
    assert entries[1]["duration_s"] == pytest.approx(1.5, abs=1e-3)

    for entry in entries:
        clip_path = out_dir / entry["filename"]
        assert clip_path.is_file()
        digest = hashlib.sha256(clip_path.read_bytes()).hexdigest()
        assert digest == entry["sha256"]


def test_materialize_turn_clips_is_deterministic(tmp_path):
    source = tmp_path / "source.wav"
    _write_synthetic_wav(source, duration_s=2.0)
    covered_turns = [{"speaker": "A", "absolute_start": 0.0, "absolute_end": 1.0, "slice_index": 0}]

    entries_a = bpm.materialize_turn_clips(covered_turns, source, tmp_path / "out1", meeting_id="SYN1")
    entries_b = bpm.materialize_turn_clips(covered_turns, source, tmp_path / "out2", meeting_id="SYN1")
    assert entries_a[0]["sha256"] == entries_b[0]["sha256"]


def test_materialize_turn_clips_clamps_out_of_range_bounds(tmp_path):
    source = tmp_path / "source.wav"
    _write_synthetic_wav(source, duration_s=1.0)
    # absolute_end far beyond the source's own duration must clamp, not crash.
    covered_turns = [{"speaker": "A", "absolute_start": 0.5, "absolute_end": 100.0, "slice_index": 0}]
    entries = bpm.materialize_turn_clips(covered_turns, source, tmp_path / "out", meeting_id="SYN1")
    assert entries[0]["duration_s"] == pytest.approx(0.5, abs=1e-2)


# ---------------------------------------------------------------------------
# BuildConfig / load_build_config
# ---------------------------------------------------------------------------


def test_load_build_config_none_path_returns_defaults():
    cfg = bpm.load_build_config(None)
    assert cfg == bpm.BuildConfig()


def test_load_build_config_reads_the_committed_config_file():
    from pathlib import Path

    config_path = Path(__file__).resolve().parents[3] / "configs" / "probes" / "pattr" / "2026-08-18-build-config.json"
    cfg = bpm.load_build_config(config_path)
    assert cfg.seed == 20260818
    assert cfg.n_meetings == 4
    assert cfg.max_slices_per_meeting == 6
    assert set(cfg.candidate_pool) == set(bpm.CANDIDATE_POOL)


# ---------------------------------------------------------------------------
# find_oversized_slices: pure diagnostic (never a silent drop)
# ---------------------------------------------------------------------------


def _meetings_with_slice_durations(*durations_per_meeting):
    meetings = {}
    for i, durations in enumerate(durations_per_meeting):
        meeting_id = f"M{i}"
        entries = []
        start = 0.0
        for j, dur in enumerate(durations):
            entries.append({"index": j, "start": start, "end": start + dur})
            start += dur
        meetings[meeting_id] = {"slice_plan": {"entries": entries}}
    return meetings


def test_find_oversized_slices_reports_none_when_all_within_bound():
    meetings = _meetings_with_slice_durations([90.0, 100.0], [60.0])
    assert bpm.find_oversized_slices(meetings, 120.0) == ()


def test_find_oversized_slices_reports_every_violation_with_context():
    meetings = _meetings_with_slice_durations([90.0, 127.778], [60.0, 130.0])
    violations = bpm.find_oversized_slices(meetings, 120.0)
    assert len(violations) == 2
    by_meeting = {(v["meeting_id"], v["slice_index"]): v["duration_s"] for v in violations}
    assert by_meeting[("M0", 1)] == pytest.approx(127.778)
    assert by_meeting[("M1", 1)] == pytest.approx(130.0)
    assert all(v["max_audio_seconds"] == 120.0 for v in violations)


def test_load_build_config_partial_json_falls_back_to_defaults(tmp_path):
    import json

    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"seed": 7}), encoding="utf-8")
    cfg = bpm.load_build_config(path)
    assert cfg.seed == 7
    assert cfg.n_meetings == bpm.DEFAULT_N_MEETINGS  # untouched field keeps its default
