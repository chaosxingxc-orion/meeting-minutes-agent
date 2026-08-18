"""Tests for ``scripts/build_pprompt_binding.py``: pure helpers on a tiny
synthetic P-ATTR-shaped manifest and a fake donor JSONL -- never real AMI
bytes or a real P-ATTR run directory, mirroring
``tests/unit/scripts/test_build_pattr_manifest.py``'s own convention."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import build_pprompt_binding as bpb
import pytest

from meeting_minutes_agent.probes.pattr import PattrManifest
from meeting_minutes_agent.probes.pprompt import GRID_CELLS


def _small_manifest_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "created_utc": "2026-08-18T00:00:00+00:00",
        "purpose": "test",
        "seed": 1,
        "candidate_pool": ["MTG1", "MTG2"],
        "selected_meetings": ["MTG1", "MTG2"],
        "selection_rule": "test",
        "n_meetings_requested": 2,
        "slicer": {
            "mode": "turn_aware", "turn_provenance": "oracle-turn", "allow_oracle_turns": True,
            "nominal_s": 90.0, "min_s": 60.0, "max_s": 120.0, "snap_s": 3.0, "max_slices_per_meeting": 1,
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
                "meeting_duration_s": 100.0,
                "n_turns_total": 2,
                "slice_plan": {
                    "meeting_id": "MTG1", "mode": "turn_aware", "turn_provenance": "oracle-turn",
                    "sample_rate": 16000, "channels": 1,
                    "entries": [
                        {
                            "index": 0, "start": 0.0, "end": 90.0, "filename": "MTG1-slice0000.wav",
                            "sha256": "s0", "vad_snap_applied": False, "encoder_chunk_count": 3,
                            "turns": [
                                {"speaker": "A", "absolute_start": 0.0, "absolute_end": 40.0, "slice_offset_start": 0.0, "slice_offset_end": 40.0},
                                {"speaker": "B", "absolute_start": 40.0, "absolute_end": 90.0, "slice_offset_start": 40.0, "slice_offset_end": 90.0},
                            ],
                        },
                    ],
                    "content_hash": "planhash1",
                },
                "turn_clips": [],
                "covered_duration_s": 90.0, "n_slices": 1, "n_turn_clips": 0,
            },
            "MTG2": {
                "role": "asr-eval",
                "audio_relpath": "datasets/ami/amicorpus/MTG2/audio/MTG2.Mix-Headset.wav",
                "audio_sha256": "bbbb",
                "meeting_duration_s": 60.0,
                "n_turns_total": 2,
                "slice_plan": {
                    "meeting_id": "MTG2", "mode": "turn_aware", "turn_provenance": "oracle-turn",
                    "sample_rate": 16000, "channels": 1,
                    "entries": [
                        {
                            "index": 0, "start": 0.0, "end": 60.0, "filename": "MTG2-slice0000.wav",
                            "sha256": "s2", "vad_snap_applied": False, "encoder_chunk_count": 2,
                            "turns": [
                                {"speaker": "C", "absolute_start": 0.0, "absolute_end": 30.0, "slice_offset_start": 0.0, "slice_offset_end": 30.0},
                                {"speaker": "D", "absolute_start": 30.0, "absolute_end": 60.0, "slice_offset_start": 30.0, "slice_offset_end": 60.0},
                            ],
                        },
                    ],
                    "content_hash": "planhash2",
                },
                "turn_clips": [],
                "covered_duration_s": 60.0, "n_slices": 1, "n_turn_clips": 0,
            },
        },
        "totals": {"n_meetings": 2, "n_slices": 2, "n_turn_clips": 0, "slice_audio_seconds": 150.0, "turn_clip_audio_seconds": 0.0},
    }


def _manifest() -> PattrManifest:
    return PattrManifest(raw=_small_manifest_document(), source_path=None)


def _write_donor_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _fake_a_turn_records(meeting_id: str, n: int, *, speakers=("A", "B")) -> list[dict]:
    return [
        {
            "request_id": f"pattr-turn-{meeting_id}-turn{i:04d}",
            "arm": "A-turn",
            "meeting_id": meeting_id,
            "turn_index": i,
            "slice_index": 0,
            "known_speaker": speakers[i % len(speakers)],
            "outcome": "ok",
            "text": f"model said {meeting_id} turn {i}",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# per_slice_roster_table
# ---------------------------------------------------------------------------


def test_per_slice_roster_table():
    table = bpb.per_slice_roster_table(_manifest())
    assert table == {"MTG1": {0: ("A", "B")}, "MTG2": {0: ("C", "D")}}


# ---------------------------------------------------------------------------
# build_x1_block
# ---------------------------------------------------------------------------


def test_build_x1_block_derangement_is_fixed_point_free_and_covers_the_alphabet():
    block = bpb.build_x1_block(_manifest(), seed=20260818)
    derangement = block["label_derangement"]
    assert set(derangement) == {"A", "B", "C", "D"}
    assert set(derangement.values()) == {"A", "B", "C", "D"}
    assert all(k != v for k, v in derangement.items())


def test_build_x1_block_records_the_resolution_and_true_roster():
    block = bpb.build_x1_block(_manifest(), seed=20260818)
    assert block["resolution"] == "label-derangement-within-slice"
    assert block["per_slice_roster"]["MTG1"]["0"]["true_roster"] == ["A", "B"]
    assert block["per_slice_roster"]["MTG2"]["0"]["true_roster"] == ["C", "D"]


def test_build_x1_block_corrupted_roster_differs_from_true_roster():
    block = bpb.build_x1_block(_manifest(), seed=20260818)
    entry = block["per_slice_roster"]["MTG1"]["0"]
    assert entry["corrupted_roster"] != entry["true_roster"]


# ---------------------------------------------------------------------------
# select_donor_tail_entries
# ---------------------------------------------------------------------------


def test_select_donor_tail_entries_takes_the_last_n_by_turn_index():
    records = _fake_a_turn_records("MTG2", 15)
    entries = bpb.select_donor_tail_entries("MTG2", records, tail_size=10)
    assert len(entries) == 10
    assert [e["donor_turn_index"] for e in entries] == list(range(5, 15))
    assert all(e["donor_meeting_id"] == "MTG2" for e in entries)


def test_select_donor_tail_entries_skips_non_ok_records():
    records = _fake_a_turn_records("MTG2", 12)
    records[11]["outcome"] = "error"
    entries = bpb.select_donor_tail_entries("MTG2", records, tail_size=10)
    assert len(entries) == 10
    assert 11 not in [e["donor_turn_index"] for e in entries]


def test_select_donor_tail_entries_filters_by_donor_meeting_id():
    records = _fake_a_turn_records("MTG1", 5) + _fake_a_turn_records("MTG2", 12)
    entries = bpb.select_donor_tail_entries("MTG2", records, tail_size=10)
    assert all(e["donor_meeting_id"] == "MTG2" for e in entries)
    assert len(entries) == 10


def test_select_donor_tail_entries_pins_the_correct_text_hash():
    records = _fake_a_turn_records("MTG2", 10)
    entries = bpb.select_donor_tail_entries("MTG2", records, tail_size=10)
    by_id = {r["request_id"]: r for r in records}
    for e in entries:
        expected = hashlib.sha256(by_id[e["donor_request_id"]]["text"].encode("utf-8")).hexdigest()
        assert e["text_sha256"] == expected


# ---------------------------------------------------------------------------
# build_x2_block
# ---------------------------------------------------------------------------


def test_build_x2_block_raises_when_donor_source_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        bpb.build_x2_block(_manifest(), tmp_path, seed=1, tail_size=10, donor_source_relative="does/not/exist.jsonl")


def test_build_x2_block_raises_when_donor_has_too_few_flown_turns(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 3) + _fake_a_turn_records("MTG2", 3)
    _write_donor_jsonl(tmp_path / relpath, records)
    with pytest.raises(RuntimeError, match="fewer than"):
        bpb.build_x2_block(_manifest(), tmp_path, seed=1, tail_size=10, donor_source_relative=relpath)


def test_build_x2_block_assigns_a_different_meeting_as_donor(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 15) + _fake_a_turn_records("MTG2", 15)
    _write_donor_jsonl(tmp_path / relpath, records)
    block, tail_segments = bpb.build_x2_block(
        _manifest(), tmp_path, seed=20260818, tail_size=10, donor_source_relative=relpath
    )
    assignment = block["donor_meeting_assignment"]
    assert set(assignment) == {"MTG1", "MTG2"}
    assert all(target != donor for target, donor in assignment.items())
    assert set(tail_segments) == {"MTG1", "MTG2"}
    assert len(tail_segments["MTG1"]) == 10
    assert len(tail_segments["MTG2"]) == 10


def test_build_x2_block_pins_hashes_matching_the_donor_text(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 15) + _fake_a_turn_records("MTG2", 15)
    _write_donor_jsonl(tmp_path / relpath, records)
    block, _ = bpb.build_x2_block(_manifest(), tmp_path, seed=20260818, tail_size=10, donor_source_relative=relpath)
    by_id = {r["request_id"]: r for r in records}
    for entries in block["tail_entries"].values():
        for e in entries:
            expected = hashlib.sha256(by_id[e["donor_request_id"]]["text"].encode("utf-8")).hexdigest()
            assert e["text_sha256"] == expected


def test_build_x2_block_never_embeds_raw_donor_text():
    # The committed binding manifest must carry only hashes, never the raw
    # model-generated donor text (module docstring: keep raw traces out of
    # git). This is checked structurally on the block's own dict shape.
    block = {"tail_entries": {"MTG1": [{"donor_request_id": "x", "text_sha256": "a" * 64}]}}
    for entries in block["tail_entries"].values():
        for e in entries:
            assert "text" not in e


# ---------------------------------------------------------------------------
# build_binding_manifest end-to-end (still on the tiny synthetic fixture)
# ---------------------------------------------------------------------------


def _write_pattr_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "pattr-manifest.json"
    path.write_text(json.dumps(_small_manifest_document()), encoding="utf-8")
    return path


def test_build_binding_manifest_end_to_end(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 15) + _fake_a_turn_records("MTG2", 15)
    _write_donor_jsonl(tmp_path / relpath, records)
    pattr_manifest_path = _write_pattr_manifest(tmp_path)

    binding = bpb.build_binding_manifest(
        _manifest(), pattr_manifest_path, tmp_path, seed=20260818, tail_size=10, donor_source_relative=relpath
    )

    assert binding["schema_version"] == "1.0.0"
    assert binding["seed"] == 20260818
    assert binding["pattr_manifest_reference"]["path"] == pattr_manifest_path.as_posix()
    assert len(binding["pattr_manifest_reference"]["sha256"]) == 64
    assert set(binding["templates"]) == {"T1", "T2", "T3", "T4"}
    assert {"A1", "A2", "A3"} <= set(binding["arrangements"])
    assert binding["totals"]["n_grid_requests"] == 12 * 2  # 2 slices total (1 per meeting)
    assert binding["totals"]["n_x1_requests"] == 2
    assert binding["totals"]["n_x2_requests"] == 2
    assert binding["totals"]["n_total_requests"] == 12 * 2 + 2 + 2
    for cell in GRID_CELLS:
        renderings = binding["renderings"][cell]
        assert len(renderings) == 2
        for r in renderings:
            assert len(r["content_sha256"]) == 64
    # T1's three arrangements collapse to one distinct hash per slice
    # (module docstring / build_arrangements_block's own recorded note).
    t1_hashes = {
        (r["meeting_id"], r["slice_index"]): r["content_sha256"]
        for cell in ("T1-A1", "T1-A2", "T1-A3")
        for r in binding["renderings"][cell]
    }
    per_slice_distinct = {}
    for cell in ("T1-A1", "T1-A2", "T1-A3"):
        for r in binding["renderings"][cell]:
            key = (r["meeting_id"], r["slice_index"])
            per_slice_distinct.setdefault(key, set()).add(r["content_sha256"])
    assert all(len(v) == 1 for v in per_slice_distinct.values())


def test_main_writes_the_binding_manifest_file(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 15) + _fake_a_turn_records("MTG2", 15)
    _write_donor_jsonl(tmp_path / relpath, records)
    pattr_manifest_path = _write_pattr_manifest(tmp_path)
    out_path = tmp_path / "out" / "binding.json"

    rc = bpb.main(
        [
            "--data-dir", str(tmp_path),
            "--pattr-manifest", str(pattr_manifest_path),
            "--out", str(out_path),
            "--donor-source-relative", relpath,
        ]
    )
    assert rc == 0
    assert out_path.is_file()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0.0"


def test_main_dry_run_writes_nothing(tmp_path):
    relpath = "runs/a-turn-responses.jsonl"
    records = _fake_a_turn_records("MTG1", 15) + _fake_a_turn_records("MTG2", 15)
    _write_donor_jsonl(tmp_path / relpath, records)
    pattr_manifest_path = _write_pattr_manifest(tmp_path)
    out_path = tmp_path / "out" / "binding.json"

    rc = bpb.main(
        [
            "--data-dir", str(tmp_path),
            "--pattr-manifest", str(pattr_manifest_path),
            "--out", str(out_path),
            "--donor-source-relative", relpath,
            "--dry-run",
        ]
    )
    assert rc == 0
    assert not out_path.exists()
