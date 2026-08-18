"""Tests for :mod:`meeting_minutes_agent.chunking.slicer`: the real
transport slicer -- VAD/grid determinism and bounds, snap-to-transition
behaviour, the turn-aware packing mode (no mid-turn cuts, the long-turn
internal-split exception, the per-slice speaker table, tier tagging and its
M1 gate), real-audio materialization on synthetic fixtures (slice-manifest
hash stability, sha256 correctness), and the slice-index-keyed resolver
factory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from meeting_minutes_agent.chunking.constants import (
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_TARGET_S,
)
from meeting_minutes_agent.chunking.leakage import BoundaryLeakageTierViolation, BoundaryProvenance
from meeting_minutes_agent.chunking.slicer import (
    SlicerError,
    SlicePlanMode,
    TurnSpan,
    build_slice_manifest,
    build_turn_aware_slice_plan,
    build_vad_slice_plan,
    detect_energy_pause_transitions,
    make_audio_chunk_resolver,
    materialize_slice_plan,
    plan_transport_slices_from_audio,
    read_audio_duration,
)

SR = 16000


def _write_synth_wav(path: Path, duration_s: float, *, sr: int = SR, silence_windows=()) -> Path:
    """A deterministic synthetic mono WAV: a steady 220Hz tone, with
    ``silence_windows`` ((start_s, end_s) pairs) zeroed out to create real,
    detectable pauses for the energy-based VAD to find."""

    n = int(round(duration_s * sr))
    t = np.arange(n) / sr
    y = 0.2 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    for start_s, end_s in silence_windows:
        a, b = int(start_s * sr), int(end_s * sr)
        y[a:b] = 0.0
    sf.write(str(path), y, sr, subtype="PCM_16")
    return path


# ---------------------------------------------------------------------------
# VAD/grid mode -- pure, no audio I/O
# ---------------------------------------------------------------------------


class TestVadSlicePlanPure:
    def test_tiles_with_zero_overlap_and_no_gaps(self):
        plan = build_vad_slice_plan("m1", 400.0)
        assert plan.slices[0].start == 0.0
        assert plan.slices[-1].end == 400.0
        for a, b in zip(plan.slices, plan.slices[1:]):
            assert a.end == b.start  # zero overlap, zero gap

    def test_default_bounds_respected_except_possibly_the_last(self):
        # 400s = 4x90s + a 40s remainder; merging the remainder back would
        # make the predecessor 130s (> max_s=120), so it is refused (SS8.1:
        # "no merging back past 120s") and the final slice stays short.
        plan = build_vad_slice_plan("m1", 400.0)
        for s in plan.slices[:-1]:
            assert TRANSPORT_SLICE_MIN_S <= s.duration <= TRANSPORT_SLICE_MAX_S
        assert plan.slices[-1].duration <= TRANSPORT_SLICE_MAX_S
        assert plan.slices[-1].duration < TRANSPORT_SLICE_MIN_S

    def test_nominal_grid_with_no_transitions_lands_on_90s(self):
        plan = build_vad_slice_plan("m1", 270.0)  # exactly 3 x 90s
        assert [s.duration for s in plan.slices] == [90.0, 90.0, 90.0]
        assert all(not s.vad_snap_applied for s in plan.slices)

    def test_snaps_to_a_transition_within_the_window(self):
        # nominal boundary at 90s; a transition at 92s is within +-3s.
        plan = build_vad_slice_plan("m1", 200.0, pause_transitions=[92.0])
        assert plan.slices[0].end == 92.0
        assert plan.slices[0].vad_snap_applied is True

    def test_transition_outside_the_window_is_ignored(self):
        # 96s is 6s away from the 90s nominal boundary -- outside +-3s.
        plan = build_vad_slice_plan("m1", 200.0, pause_transitions=[96.0])
        assert plan.slices[0].end == 90.0
        assert plan.slices[0].vad_snap_applied is False

    def test_final_slice_may_be_short(self):
        # 310s: [0,90)[90,180)[180,270) + a 40s remainder the merge cannot
        # absorb without exceeding max_s (270+40=310s in a merged slice
        # would be 130s > 120s) -- it survives standalone, short.
        plan = build_vad_slice_plan("m1", 310.0)
        assert plan.slices[-1].duration < TRANSPORT_SLICE_MIN_S

    def test_a_short_tail_merges_when_that_keeps_it_under_the_max(self):
        # 100s: one 90s slice + a 10s tail -- merging gives 100s (<= 120s
        # max), so it DOES merge into a single slice rather than surviving
        # standalone ("no merging back past 120s" permits this merge).
        plan = build_vad_slice_plan("m1", 100.0)
        assert len(plan.slices) == 1
        assert plan.slices[0].duration == 100.0

    def test_undersized_tail_merges_into_predecessor_when_it_fits(self):
        # 190s: grid gives [0,90) [90,180) [180,190) -- the 10s tail merges
        # into the second slice (100s <= 120s max) rather than surviving
        # standalone.
        plan = build_vad_slice_plan("m1", 190.0)
        assert len(plan.slices) == 2
        assert plan.slices[-1].end == 190.0
        assert plan.slices[-1].duration <= TRANSPORT_SLICE_MAX_S

    def test_determinism_same_inputs_same_hash(self):
        a = build_vad_slice_plan("m1", 400.0, pause_transitions=[91.0, 271.0])
        b = build_vad_slice_plan("m1", 400.0, pause_transitions=[91.0, 271.0])
        assert a == b
        assert a.content_hash == b.content_hash
        assert len(a.content_hash) == 64

    def test_content_hash_changes_with_transitions(self):
        a = build_vad_slice_plan("m1", 400.0, pause_transitions=[91.0])
        b = build_vad_slice_plan("m1", 400.0, pause_transitions=[89.0])
        assert a.content_hash != b.content_hash

    def test_encoder_chunk_count_is_ceiling_of_30s_grid(self):
        plan = build_vad_slice_plan("m1", 270.0)
        assert all(s.encoder_chunk_count == 3 for s in plan.slices)  # 90s / 30s exactly

    def test_zero_duration_gives_no_slices(self):
        plan = build_vad_slice_plan("m1", 0.0)
        assert plan.slices == ()
        assert plan.mode is SlicePlanMode.VAD
        assert plan.turn_provenance is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"nominal_s": 0.0},
            {"min_s": 0.0},
            {"max_s": 0.0},
            {"min_s": 130.0, "nominal_s": 90.0, "max_s": 120.0},  # min > nominal
            {"nominal_s": 200.0, "min_s": 60.0, "max_s": 120.0},  # nominal > max
            {"snap_s": -1.0},
        ],
    )
    def test_rejects_bad_bounds(self, kwargs):
        with pytest.raises(SlicerError):
            build_vad_slice_plan("m1", 400.0, **kwargs)

    def test_rejects_negative_duration(self):
        with pytest.raises(SlicerError):
            build_vad_slice_plan("m1", -1.0)


# ---------------------------------------------------------------------------
# turn-aware mode -- pure, no audio I/O
# ---------------------------------------------------------------------------


def _turn_train(n: int, turn_len: float, gap: float, start: float = 0.0, speakers=("A", "B")) -> tuple[TurnSpan, ...]:
    turns = []
    t = start
    for i in range(n):
        turns.append(TurnSpan(t, t + turn_len, speakers[i % len(speakers)]))
        t += turn_len + gap
    return tuple(turns)


class TestTurnAwareSlicePlan:
    def test_refuses_an_oracle_turn_table_without_explicit_admission(self):
        turns = _turn_train(10, 8.0, 1.5)
        with pytest.raises(BoundaryLeakageTierViolation):
            build_turn_aware_slice_plan("m2", turns, turn_provenance=BoundaryProvenance.ORACLE_TURN)

    def test_admits_an_oracle_turn_table_with_the_ceiling_arm_flag(self):
        turns = _turn_train(10, 8.0, 1.5)
        plan = build_turn_aware_slice_plan(
            "m2", turns, turn_provenance=BoundaryProvenance.ORACLE_TURN, allow_oracle_turns=True
        )
        assert plan.turn_provenance is BoundaryProvenance.ORACLE_TURN
        assert plan.mode is SlicePlanMode.TURN_AWARE

    @pytest.mark.parametrize("provenance", [BoundaryProvenance.SIGNAL, BoundaryProvenance.TOOL_DIAR])
    def test_m0_turn_provenance_never_needs_the_flag(self, provenance):
        turns = _turn_train(10, 8.0, 1.5)
        plan = build_turn_aware_slice_plan("m2", turns, turn_provenance=provenance)
        assert plan.turn_provenance is provenance

    def test_never_cuts_mid_turn(self):
        turns = _turn_train(40, 7.0, 2.3)
        plan = build_turn_aware_slice_plan("m2", turns, turn_provenance=BoundaryProvenance.TOOL_DIAR)
        interior_boundaries = [s.end for s in plan.slices[:-1]]
        for boundary in interior_boundaries:
            for turn in turns:
                # A boundary must never fall STRICTLY inside a turn's span.
                assert not (turn.start < boundary < turn.end)

    def test_packs_consecutive_turns_toward_the_nominal_target(self):
        turns = _turn_train(40, 7.0, 2.3)  # period 9.3s -> ~10 turns per 90s-ish slice
        plan = build_turn_aware_slice_plan("m2", turns, turn_provenance=BoundaryProvenance.TOOL_DIAR)
        for s in plan.slices[:-1]:
            assert TRANSPORT_SLICE_MIN_S <= s.duration <= TRANSPORT_SLICE_MAX_S

    def test_a_turn_longer_than_max_s_is_split_internally_at_pauses(self):
        long_turn = (TurnSpan(0.0, 300.0, "A"),)
        transitions = [90.0, 91.0, 210.0, 211.0]  # exactly on/near grid points inside the turn
        plan = build_turn_aware_slice_plan(
            "m3",
            long_turn,
            turn_provenance=BoundaryProvenance.TOOL_DIAR,
            fallback_pause_transitions=transitions,
        )
        assert len(plan.slices) >= 3  # 300s / ~90s
        assert plan.slices[0].start == 0.0
        assert plan.slices[-1].end == 300.0
        for a, b in zip(plan.slices, plan.slices[1:]):
            assert a.end == b.start  # still zero overlap, no gap, even mid-turn
        for s in plan.slices:
            assert s.duration <= TRANSPORT_SLICE_MAX_S

    def test_per_slice_speaker_table_offsets_are_slice_relative(self):
        turns = (TurnSpan(0.0, 5.0, "A"), TurnSpan(5.0, 92.0, "B"))
        plan = build_turn_aware_slice_plan(
            "m4", turns, turn_provenance=BoundaryProvenance.TOOL_DIAR, total_duration_s=92.0
        )
        assert len(plan.slices) == 1
        s = plan.slices[0]
        speakers = {e.speaker: e for e in s.turns}
        assert speakers["A"].slice_offset_start == 0.0
        assert speakers["A"].slice_offset_end == 5.0
        assert speakers["A"].absolute_start == 0.0
        assert speakers["B"].slice_offset_start == 5.0
        assert speakers["B"].slice_offset_end == pytest.approx(92.0)

    def test_empty_turn_table_gives_an_empty_plan(self):
        plan = build_turn_aware_slice_plan("m5", (), turn_provenance=BoundaryProvenance.SIGNAL)
        assert plan.slices == ()

    def test_turn_span_rejects_end_not_after_start(self):
        with pytest.raises(SlicerError):
            TurnSpan(5.0, 5.0, "A").validate()


# ---------------------------------------------------------------------------
# real-audio I/O: VAD detection, materialization, manifest, resolver
# ---------------------------------------------------------------------------


class TestRealAudioVad:
    def test_read_audio_duration_matches_written_length(self, tmp_path):
        path = _write_synth_wav(tmp_path / "clip.wav", 12.5)
        assert read_audio_duration(path) == pytest.approx(12.5, abs=0.01)

    def test_detect_energy_pause_transitions_finds_a_real_silence_gap(self, tmp_path):
        path = _write_synth_wav(tmp_path / "clip.wav", 20.0, silence_windows=[(8.0, 11.0)])
        transitions = detect_energy_pause_transitions(path, min_pause_s=1.0)
        assert any(abs(t - 8.0) < 0.2 for t in transitions)
        assert any(abs(t - 11.0) < 0.2 for t in transitions)

    def test_short_pauses_below_the_threshold_are_not_reported(self, tmp_path):
        path = _write_synth_wav(tmp_path / "clip.wav", 20.0, silence_windows=[(8.0, 8.3)])  # 0.3s < 1.0s min
        transitions = detect_energy_pause_transitions(path, min_pause_s=1.0)
        assert not any(7.5 < t < 8.8 for t in transitions)

    def test_plan_transport_slices_from_audio_uses_the_real_duration_and_pauses(self, tmp_path):
        path = _write_synth_wav(tmp_path / "clip.wav", 200.0, silence_windows=[(89.0, 91.5)])
        plan = plan_transport_slices_from_audio(path, meeting_id="m6")
        assert plan.total_duration_s == pytest.approx(200.0, abs=0.01)
        assert plan.slices[-1].end == pytest.approx(200.0, abs=0.01)


class TestMaterializeSlicePlan:
    def test_writes_one_16khz_mono_wav_per_slice(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 200.0)
        plan = build_vad_slice_plan("m7", 200.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")

        assert len(manifest.entries) == len(plan.slices)
        assert manifest.sample_rate == 16000
        assert manifest.channels == 1
        for entry in manifest.entries:
            out_path = (tmp_path / "out" / entry.filename)
            assert out_path.is_file()
            info = sf.info(str(out_path))
            assert info.samplerate == 16000
            assert info.channels == 1
            assert info.frames / info.samplerate == pytest.approx(entry.end - entry.start, abs=0.01)

    def test_sha256_is_the_real_written_file_hash(self, tmp_path):
        import hashlib

        source = _write_synth_wav(tmp_path / "source.wav", 200.0)
        plan = build_vad_slice_plan("m8", 200.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")
        for entry in manifest.entries:
            real_bytes = (tmp_path / "out" / entry.filename).read_bytes()
            assert entry.sha256 == hashlib.sha256(real_bytes).hexdigest()

    def test_manifest_hash_and_slice_hashes_are_stable_across_re_materialization(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 200.0)
        plan = build_vad_slice_plan("m9", 200.0)
        manifest_a = materialize_slice_plan(plan, source, tmp_path / "out_a")
        manifest_b = materialize_slice_plan(plan, source, tmp_path / "out_b")

        assert manifest_a.content_hash == manifest_b.content_hash
        assert [e.sha256 for e in manifest_a.entries] == [e.sha256 for e in manifest_b.entries]

    def test_downmix_and_resample_44khz_stereo_source(self, tmp_path):
        # 17-item change list item 8: a non-16kHz-mono source (MeetingBank's
        # own 44.1kHz stereo carrier) must go through the SAME decode path.
        sr = 44100
        n = int(round(6.0 * sr))
        t = np.arange(n) / sr
        left = 0.2 * np.sin(2 * np.pi * 220.0 * t)
        right = 0.2 * np.sin(2 * np.pi * 330.0 * t)
        stereo = np.stack([left, right], axis=1).astype(np.float32)
        source = tmp_path / "stereo.wav"
        sf.write(str(source), stereo, sr, subtype="PCM_16")

        plan = build_vad_slice_plan("m10", 6.0, nominal_s=6.0, min_s=6.0, max_s=6.0, snap_s=0.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")

        assert manifest.sample_rate == 16000
        assert manifest.channels == 1
        out_path = tmp_path / "out" / manifest.entries[0].filename
        info = sf.info(str(out_path))
        assert info.samplerate == 16000
        assert info.channels == 1

    def test_manifest_records_turn_provenance_from_turn_aware_plans(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 20.0)
        plan = build_turn_aware_slice_plan(
            "m11", (TurnSpan(0.0, 20.0, "A"),), turn_provenance=BoundaryProvenance.TOOL_DIAR, total_duration_s=20.0
        )
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")
        assert manifest.mode == "turn_aware"
        assert manifest.turn_provenance == "tool-diar"
        assert manifest.entries[0].turns[0]["speaker"] == "A"


class TestBuildSliceManifestOrchestrator:
    def test_vad_mode_end_to_end(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 250.0, silence_windows=[(89.0, 91.0)])
        manifest = build_slice_manifest("m12", source, tmp_path / "out", mode="vad")
        assert manifest.mode == "vad"
        assert manifest.turn_provenance is None
        assert sum(e.end - e.start for e in manifest.entries) == pytest.approx(250.0, abs=0.01)

    def test_turn_aware_mode_end_to_end(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 60.0)
        turns = (TurnSpan(0.0, 30.0, "A"), TurnSpan(30.0, 60.0, "B"))
        manifest = build_slice_manifest(
            "m13", source, tmp_path / "out", mode="turn_aware", turns=turns, turn_provenance=BoundaryProvenance.SIGNAL
        )
        assert manifest.mode == "turn_aware"
        assert manifest.turn_provenance == "signal"

    def test_turn_aware_mode_requires_a_provenance(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 10.0)
        with pytest.raises(SlicerError):
            build_slice_manifest("m14", source, tmp_path / "out", mode="turn_aware")

    def test_unknown_mode_rejected(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 10.0)
        with pytest.raises(SlicerError):
            build_slice_manifest("m15", source, tmp_path / "out", mode="bogus")


class TestMakeAudioChunkResolver:
    def test_resolves_index_to_path_and_seconds(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 200.0)
        plan = build_vad_slice_plan("m16", 200.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")
        resolve = make_audio_chunk_resolver(manifest, tmp_path / "out")

        for entry in manifest.entries:
            path, seconds = resolve(entry.index)
            assert path == tmp_path / "out" / entry.filename
            assert path.is_file()
            assert seconds == pytest.approx(entry.end - entry.start)

    def test_unknown_index_raises_key_error(self, tmp_path):
        source = _write_synth_wav(tmp_path / "source.wav", 90.0)
        plan = build_vad_slice_plan("m17", 90.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")
        resolve = make_audio_chunk_resolver(manifest, tmp_path / "out")
        with pytest.raises(KeyError):
            resolve(999)

    def test_a_slice_never_exceeds_the_transport_slice_max(self, tmp_path):
        # Direct check of the G1-blocking property: every resolved slice's
        # audio_seconds is within the transport-slice bound, so a caller
        # feeding it straight to LlamaServerTransport.request can never
        # accidentally carry more than one slice.
        source = _write_synth_wav(tmp_path / "source.wav", 500.0)
        plan = build_vad_slice_plan("m18", 500.0)
        manifest = materialize_slice_plan(plan, source, tmp_path / "out")
        resolve = make_audio_chunk_resolver(manifest, tmp_path / "out")
        for entry in manifest.entries:
            _, seconds = resolve(entry.index)
            assert seconds <= TRANSPORT_SLICE_MAX_S
