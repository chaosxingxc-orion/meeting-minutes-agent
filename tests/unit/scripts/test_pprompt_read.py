"""Tests for ``scripts/pprompt_read.py``: response loading, the missing-
reply fail-closed check, the end-to-end read (winner + corrupt verdicts +
written files), and the one-shot output-dir guard. Uses
``run_read``'s own ``resolved_meetings`` injection seam so no real AMI
annotation bytes are needed."""

from __future__ import annotations

import json
from pathlib import Path

import pprompt_read as reader
import pytest

from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Utterance
from meeting_minutes_agent.probes.pattr import PattrManifest
from meeting_minutes_agent.probes.pprompt import ARMS
from meeting_minutes_agent.probes.pprompt_scoring import (
    CellScore,
    PromptSweepOutputExistsError,
    SliceScore,
    aggregate_cell,
    apply_winner_rule,
    evaluate_all_corrupt_arms,
)


def _small_pattr_manifest_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "created_utc": "2026-08-18T00:00:00+00:00",
        "purpose": "test",
        "seed": 1,
        "candidate_pool": ["MTG1"],
        "selected_meetings": ["MTG1"],
        "selection_rule": "test",
        "n_meetings_requested": 1,
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
                "n_turns_total": 1,
                "slice_plan": {
                    "meeting_id": "MTG1", "mode": "turn_aware", "turn_provenance": "oracle-turn",
                    "sample_rate": 16000, "channels": 1,
                    "entries": [
                        {
                            "index": 0, "start": 0.0, "end": 90.0, "filename": "MTG1-slice0000.wav",
                            "sha256": "s0", "vad_snap_applied": False, "encoder_chunk_count": 3,
                            "turns": [
                                {"speaker": "A", "absolute_start": 0.0, "absolute_end": 1.0, "slice_offset_start": 0.0, "slice_offset_end": 1.0},
                            ],
                        }
                    ],
                    "content_hash": "planhash1",
                },
                "turn_clips": [],
                "covered_duration_s": 90.0, "n_slices": 1, "n_turn_clips": 0,
            }
        },
        "totals": {"n_meetings": 1, "n_slices": 1, "n_turn_clips": 0, "slice_audio_seconds": 90.0, "turn_clip_audio_seconds": 0.0},
    }


def _write_pattr_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "pattr-manifest.json"
    path.write_text(json.dumps(_small_pattr_manifest_document()), encoding="utf-8")
    return path


def _resolved_meeting() -> ResolvedMeeting:
    return ResolvedMeeting(
        meeting_id="MTG1",
        transcript=(Utterance(id="u0", speaker="A", start=0.0, end=1.0, text="hello world", word_ids=()),),
        dialogue_acts=(),
        minutes=None,
        evidence_links=(),
        topics=(),
        orphans=(),
    )


def _write_all_arm_responses(responses_dir: Path, *, text: str = "A|hello world") -> None:
    responses_dir.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        record = {"request_id": f"pprompt-{arm}-MTG1-slice0000", "outcome": "ok", "text": text}
        (responses_dir / f"{arm}-responses.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# load_responses / responses_path
# ---------------------------------------------------------------------------


def test_load_responses_keeps_only_ok_records(tmp_path):
    path = tmp_path / "arm-responses.jsonl"
    path.write_text(
        json.dumps({"request_id": "r1", "outcome": "ok", "text": "A|hi"}) + "\n"
        + json.dumps({"request_id": "r2", "outcome": "error", "error": "boom"}) + "\n",
        encoding="utf-8",
    )
    records = reader.load_responses(path)
    assert len(records) == 1
    assert records[0]["request_id"] == "r1"


def test_load_responses_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        reader.load_responses(Path("/no/such/file.jsonl"))


def test_responses_path_shape(tmp_path):
    assert reader.responses_path(tmp_path, "T2-A1") == tmp_path / "T2-A1-responses.jsonl"


# ---------------------------------------------------------------------------
# score_all_arms: missing-reply fail-closed check (no meeteval needed --
# T1-A1 is the FIRST arm in ARMS order, so this fails before any scoring)
# ---------------------------------------------------------------------------


def test_score_all_arms_requires_every_slice_reply_present(tmp_path):
    pattr_manifest = PattrManifest(raw=_small_pattr_manifest_document(), source_path=None)
    responses_dir = tmp_path / "responses"
    _write_all_arm_responses(responses_dir)
    (responses_dir / "T1-A1-responses.jsonl").write_text("", encoding="utf-8")  # no replies for this arm
    with pytest.raises(RuntimeError, match="missing a flown reply"):
        reader.score_all_arms(pattr_manifest, responses_dir, {"MTG1": _resolved_meeting()})


# ---------------------------------------------------------------------------
# build_report_text: pure, no meeteval needed
# ---------------------------------------------------------------------------


def _slice(arm, cp_wer=0.0, confusion=0.0, compliance=1.0):
    return SliceScore(
        arm=arm, meeting_id="MTG1", slice_index=0, cp_wer=cp_wer, confusion_cost=confusion,
        compliance=compliance, n_reference_segments=1, n_hypothesis_segments=1, n_malformed_lines=0,
        hypothesis_empty=False,
    )


def test_build_report_text_contains_the_winner_and_verdict_sections():
    from meeting_minutes_agent.probes.pprompt import ARM_X1, ARM_X2, GRID_CELLS, REFERENCE_CELL

    cells = {arm: aggregate_cell(arm, [_slice(arm)]) for arm in GRID_CELLS}
    cells[ARM_X1] = aggregate_cell(ARM_X1, [_slice(ARM_X1)])
    cells[ARM_X2] = aggregate_cell(ARM_X2, [_slice(ARM_X2)])
    winner = apply_winner_rule(cells)
    corrupt_verdicts = evaluate_all_corrupt_arms(cells)

    text = reader.build_report_text(
        created_utc="2026-08-18T00:00:00+00:00",
        study_commit="deadbeef",
        pins_hash="pinhash",
        meetings=["MTG1"],
        cells=cells,
        winner=winner,
        corrupt_verdicts=corrupt_verdicts,
    )
    assert "GRID WINNER" in text
    assert winner.winner_arm in text
    assert "CORRUPT-CONTEXT VERDICTS" in text
    assert REFERENCE_CELL in text
    assert "CONTEXT-INERT" in text  # both corrupt arms are identical to the reference here


# ---------------------------------------------------------------------------
# run_read: end-to-end (gated on meeteval, since real cpWER is computed)
# ---------------------------------------------------------------------------

pytest.importorskip("meeteval")


def test_run_read_end_to_end_writes_verdict_and_report(tmp_path):
    pattr_path = _write_pattr_manifest(tmp_path)
    responses_dir = tmp_path / "responses"
    _write_all_arm_responses(responses_dir)
    out_dir = tmp_path / "out"

    verdict = reader.run_read(
        data_dir=tmp_path,
        pattr_manifest_path=pattr_path,
        responses_dir=responses_dir,
        out_dir=out_dir,
        force=False,
        resolved_meetings={"MTG1": _resolved_meeting()},
    )

    assert verdict["winner"]["status"] == "WINNER"
    # every grid cell scores identically (perfect reply everywhere), so the
    # tie-break resolves to the simplest template + arrangement: T1-A1.
    assert verdict["winner"]["winner_arm"] == "T1-A1"
    assert verdict["corrupt_verdicts"]["X1"]["verdict"] == "CONTEXT-INERT"
    assert verdict["corrupt_verdicts"]["X2"]["verdict"] == "CONTEXT-INERT"
    assert (out_dir / "verdict.json").is_file()
    assert (out_dir / "report.txt").is_file()
    written = json.loads((out_dir / "verdict.json").read_text(encoding="utf-8"))
    assert written["winner"]["winner_arm"] == "T1-A1"


def test_run_read_one_shot_guard_refuses_a_second_read(tmp_path):
    pattr_path = _write_pattr_manifest(tmp_path)
    responses_dir = tmp_path / "responses"
    _write_all_arm_responses(responses_dir)
    out_dir = tmp_path / "out"
    kwargs = dict(
        data_dir=tmp_path,
        pattr_manifest_path=pattr_path,
        responses_dir=responses_dir,
        out_dir=out_dir,
        resolved_meetings={"MTG1": _resolved_meeting()},
    )
    reader.run_read(force=False, **kwargs)
    with pytest.raises(PromptSweepOutputExistsError):
        reader.run_read(force=False, **kwargs)


def test_run_read_force_allows_overwriting_a_prior_read(tmp_path):
    pattr_path = _write_pattr_manifest(tmp_path)
    responses_dir = tmp_path / "responses"
    _write_all_arm_responses(responses_dir)
    out_dir = tmp_path / "out"
    kwargs = dict(
        data_dir=tmp_path,
        pattr_manifest_path=pattr_path,
        responses_dir=responses_dir,
        out_dir=out_dir,
        resolved_meetings={"MTG1": _resolved_meeting()},
    )
    reader.run_read(force=False, **kwargs)
    reader.run_read(force=True, **kwargs)  # must not raise
