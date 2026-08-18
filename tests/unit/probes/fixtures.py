"""Shared fixtures for the ``probes.pattr`` / ``probes.pattr_scoring``
tests: a small, hand-built manifest document matching the real
``scripts/build_pattr_manifest.py`` schema exactly, but tiny -- two
meetings, three slices, six turn clips total -- so every arm-builder
assertion is hand-checkable."""

from __future__ import annotations

import copy

MTG1_SLICE_0_TURNS = [
    {"speaker": "A", "absolute_start": 0.0, "absolute_end": 40.0, "slice_offset_start": 0.0, "slice_offset_end": 40.0},
    {"speaker": "B", "absolute_start": 40.0, "absolute_end": 90.0, "slice_offset_start": 40.0, "slice_offset_end": 90.0},
]
MTG1_SLICE_1_TURNS = [
    {"speaker": "A", "absolute_start": 90.0, "absolute_end": 150.0, "slice_offset_start": 0.0, "slice_offset_end": 60.0},
    {"speaker": "B", "absolute_start": 150.0, "absolute_end": 180.0, "slice_offset_start": 60.0, "slice_offset_end": 90.0},
]
MTG2_SLICE_0_TURNS = [
    {"speaker": "C", "absolute_start": 0.0, "absolute_end": 30.0, "slice_offset_start": 0.0, "slice_offset_end": 30.0},
    {"speaker": "D", "absolute_start": 30.0, "absolute_end": 60.0, "slice_offset_start": 30.0, "slice_offset_end": 60.0},
]


def sample_manifest_document() -> dict:
    """A fresh, independent copy every call -- callers may freely mutate
    what they get back without cross-test contamination."""

    return copy.deepcopy(
        {
            "schema_version": "1.0.0",
            "created_utc": "2026-08-18T00:00:00+00:00",
            "purpose": "test fixture",
            "seed": 1,
            "candidate_pool": ["MTG1", "MTG2"],
            "selected_meetings": ["MTG1", "MTG2"],
            "selection_rule": "test",
            "n_meetings_requested": 2,
            "slicer": {
                "mode": "turn_aware",
                "turn_provenance": "oracle-turn",
                "allow_oracle_turns": True,
                "nominal_s": 90.0,
                "min_s": 60.0,
                "max_s": 120.0,
                "snap_s": 3.0,
                "max_slices_per_meeting": 2,
            },
            "ami_annotations_root_relative": "datasets/ami/annotations/manual_1.6.2",
            "ami_audio_root_relative": "datasets/ami/amicorpus",
            "ami_role_registry_hash": "deadbeef",
            "slice_output_dir_relative": "derived/meeting-minutes/pattr-smoke/slices",
            "turn_clip_output_dir_relative": "derived/meeting-minutes/pattr-smoke/turn-clips",
            "meetings": {
                "MTG1": {
                    "role": "asr-eval",
                    "audio_relpath": "datasets/ami/amicorpus/MTG1/audio/MTG1.Mix-Headset.wav",
                    "audio_sha256": "aaaa",
                    "meeting_duration_s": 600.0,
                    "n_turns_total": 5,
                    "slice_plan": {
                        "meeting_id": "MTG1",
                        "mode": "turn_aware",
                        "turn_provenance": "oracle-turn",
                        "sample_rate": 16000,
                        "channels": 1,
                        "entries": [
                            {
                                "index": 0,
                                "start": 0.0,
                                "end": 90.0,
                                "filename": "MTG1-slice0000.wav",
                                "sha256": "s0",
                                "vad_snap_applied": False,
                                "encoder_chunk_count": 3,
                                "turns": MTG1_SLICE_0_TURNS,
                            },
                            {
                                "index": 1,
                                "start": 90.0,
                                "end": 180.0,
                                "filename": "MTG1-slice0001.wav",
                                "sha256": "s1",
                                "vad_snap_applied": False,
                                "encoder_chunk_count": 3,
                                "turns": MTG1_SLICE_1_TURNS,
                            },
                        ],
                        "content_hash": "planhash1",
                    },
                    "turn_clips": [
                        {
                            "turn_index": 0, "slice_index": 0, "speaker": "A",
                            "absolute_start": 0.0, "absolute_end": 40.0, "duration_s": 40.0,
                            "filename": "MTG1-turn0000.wav", "sha256": "t0",
                        },
                        {
                            "turn_index": 1, "slice_index": 0, "speaker": "B",
                            "absolute_start": 40.0, "absolute_end": 90.0, "duration_s": 50.0,
                            "filename": "MTG1-turn0001.wav", "sha256": "t1",
                        },
                        {
                            "turn_index": 2, "slice_index": 1, "speaker": "A",
                            "absolute_start": 90.0, "absolute_end": 150.0, "duration_s": 60.0,
                            "filename": "MTG1-turn0002.wav", "sha256": "t2",
                        },
                        {
                            "turn_index": 3, "slice_index": 1, "speaker": "B",
                            "absolute_start": 150.0, "absolute_end": 180.0, "duration_s": 30.0,
                            "filename": "MTG1-turn0003.wav", "sha256": "t3",
                        },
                    ],
                    "covered_duration_s": 180.0,
                    "n_slices": 2,
                    "n_turn_clips": 4,
                },
                "MTG2": {
                    "role": "asr-eval",
                    "audio_relpath": "datasets/ami/amicorpus/MTG2/audio/MTG2.Mix-Headset.wav",
                    "audio_sha256": "bbbb",
                    "meeting_duration_s": 400.0,
                    "n_turns_total": 2,
                    "slice_plan": {
                        "meeting_id": "MTG2",
                        "mode": "turn_aware",
                        "turn_provenance": "oracle-turn",
                        "sample_rate": 16000,
                        "channels": 1,
                        "entries": [
                            {
                                "index": 0,
                                "start": 0.0,
                                "end": 60.0,
                                "filename": "MTG2-slice0000.wav",
                                "sha256": "s2",
                                "vad_snap_applied": False,
                                "encoder_chunk_count": 2,
                                "turns": MTG2_SLICE_0_TURNS,
                            }
                        ],
                        "content_hash": "planhash2",
                    },
                    "turn_clips": [
                        {
                            "turn_index": 0, "slice_index": 0, "speaker": "C",
                            "absolute_start": 0.0, "absolute_end": 30.0, "duration_s": 30.0,
                            "filename": "MTG2-turn0000.wav", "sha256": "t4",
                        },
                        {
                            "turn_index": 1, "slice_index": 0, "speaker": "D",
                            "absolute_start": 30.0, "absolute_end": 60.0, "duration_s": 30.0,
                            "filename": "MTG2-turn0001.wav", "sha256": "t5",
                        },
                    ],
                    "covered_duration_s": 60.0,
                    "n_slices": 1,
                    "n_turn_clips": 2,
                },
            },
            "totals": {
                "n_meetings": 2,
                "n_slices": 3,
                "n_turn_clips": 6,
                "slice_audio_seconds": 240.0,
                "turn_clip_audio_seconds": 240.0,
            },
        }
    )
