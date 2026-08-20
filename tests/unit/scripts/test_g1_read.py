"""Tests for ``scripts/g1_read.py``: the registered one-shot descriptive
read over already-flown replies. Real I/O, zero model contact -- every
meeting/plan is injected (mirrors ``scripts/pprompt_read.py``'s own
``resolved_meetings`` seam), so this exercises the read's own scoring/
aggregation/gap wiring without real AMI annotation bytes or a real PRECOMP
cache."""

from __future__ import annotations

import json

import pytest
import g1_read as reader

from meeting_minutes_agent.chunking.leakage import BoundaryProvenance
from meeting_minutes_agent.chunking.slicer import Slice, SlicePlan, SlicePlanMode
from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Utterance
from meeting_minutes_agent.probes import g1

pytest.importorskip("meeteval")


def _resolved(meeting_id: str) -> ResolvedMeeting:
    return ResolvedMeeting(
        meeting_id=meeting_id,
        transcript=(
            Utterance(id="u0", speaker="A", start=0.0, end=1.0, text="hello world", word_ids=()),
        ),
        dialogue_acts=(),
        minutes=None,
        evidence_links=(),
        topics=(),
        orphans=(),
    )


def _plan(meeting_id: str, mode: SlicePlanMode, provenance) -> SlicePlan:
    sl = Slice(index=0, start=0.0, end=90.0, vad_snap_applied=False, turns=())
    return SlicePlan(meeting_id=meeting_id, mode=mode, turn_provenance=provenance, total_duration_s=90.0, slices=(sl,), content_hash="h")


def _all_plans_for(meeting_id: str) -> dict:
    return {
        (meeting_id, g1.ARM_Z_TURN): (_plan(meeting_id, SlicePlanMode.TURN_AWARE, BoundaryProvenance.TOOL_DIAR), "tool"),
        (meeting_id, g1.ARM_Z_ORACLE): (_plan(meeting_id, SlicePlanMode.TURN_AWARE, BoundaryProvenance.ORACLE_TURN), "oracle"),
        (meeting_id, g1.ARM_Z_FREE): (_plan(meeting_id, SlicePlanMode.TURN_AWARE, BoundaryProvenance.TOOL_DIAR), "tool"),
        (meeting_id, g1.ARM_Z_NODIAR): (_plan(meeting_id, SlicePlanMode.VAD, None), "vad"),
    }


def _write_response(responses_dir, chunk_index: int, request_id: str, text: str) -> None:
    path = responses_dir / f"chunk{chunk_index:04d}-responses.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"request_id": request_id, "outcome": "ok", "text": text, "usage": {"completion_tokens": 3}}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


class TestRunRead:
    def test_writes_verdict_and_report(self, tmp_path):
        meeting_id = "MTG1"
        responses_dir = tmp_path / "responses"
        for arm in g1.ARMS:
            request_id = f"g1-{arm}-{meeting_id}-transcribe-slice0000"
            text = "A|hello world" if arm in g1.ARMS_WITH_ATTRIBUTION else "hello world"
            _write_response(responses_dir, 0, request_id, text)

        out_dir = tmp_path / "out"
        verdict = reader.run_read(
            data_dir=tmp_path / "data", responses_dir=responses_dir, meetings=[meeting_id], out_dir=out_dir,
            force=False, resolved_meetings={meeting_id: _resolved(meeting_id)},
            slice_plans_by_meeting_arm=_all_plans_for(meeting_id),
        )
        assert (out_dir / "verdict.json").is_file()
        assert (out_dir / "report.txt").is_file()
        assert set(verdict["pooled_by_arm"]) == set(g1.ARMS)
        assert "deployment_gap" in verdict

    def test_no_branch_verdict_field_anywhere_in_the_output(self, tmp_path):
        meeting_id = "MTG1"
        responses_dir = tmp_path / "responses"
        for arm in g1.ARMS:
            request_id = f"g1-{arm}-{meeting_id}-transcribe-slice0000"
            text = "A|hello world" if arm in g1.ARMS_WITH_ATTRIBUTION else "hello world"
            _write_response(responses_dir, 0, request_id, text)

        out_dir = tmp_path / "out"
        verdict = reader.run_read(
            data_dir=tmp_path / "data", responses_dir=responses_dir, meetings=[meeting_id], out_dir=out_dir,
            force=False, resolved_meetings={meeting_id: _resolved(meeting_id)},
            slice_plans_by_meeting_arm=_all_plans_for(meeting_id),
        )
        assert "winner" not in verdict
        assert "tie_set" not in verdict
        for pooled in verdict["pooled_by_arm"].values():
            assert "verdict" not in pooled and "winner" not in pooled

    def test_refuses_a_second_read_without_force(self, tmp_path):
        meeting_id = "MTG1"
        responses_dir = tmp_path / "responses"
        for arm in g1.ARMS:
            request_id = f"g1-{arm}-{meeting_id}-transcribe-slice0000"
            text = "A|hello world" if arm in g1.ARMS_WITH_ATTRIBUTION else "hello world"
            _write_response(responses_dir, 0, request_id, text)

        out_dir = tmp_path / "out"
        reader.run_read(
            data_dir=tmp_path / "data", responses_dir=responses_dir, meetings=[meeting_id], out_dir=out_dir,
            force=False, resolved_meetings={meeting_id: _resolved(meeting_id)},
            slice_plans_by_meeting_arm=_all_plans_for(meeting_id),
        )
        from meeting_minutes_agent.probes.g1_scoring import OneShotOutputExistsError

        with pytest.raises(OneShotOutputExistsError):
            reader.run_read(
                data_dir=tmp_path / "data", responses_dir=responses_dir, meetings=[meeting_id], out_dir=out_dir,
                force=False, resolved_meetings={meeting_id: _resolved(meeting_id)},
                slice_plans_by_meeting_arm=_all_plans_for(meeting_id),
            )

    def test_missing_reply_raises(self, tmp_path):
        meeting_id = "MTG1"
        responses_dir = tmp_path / "responses"
        # Only Z-turn's reply is present; every other arm is missing.
        _write_response(responses_dir, 0, f"g1-{g1.ARM_Z_TURN}-{meeting_id}-transcribe-slice0000", "A|hello world")

        with pytest.raises(RuntimeError):
            reader.run_read(
                data_dir=tmp_path / "data", responses_dir=responses_dir, meetings=[meeting_id], out_dir=tmp_path / "out",
                force=False, resolved_meetings={meeting_id: _resolved(meeting_id)},
                slice_plans_by_meeting_arm=_all_plans_for(meeting_id),
            )


class TestVadManifestDirWiring:
    """Z-nodiar's slice plan lives ONLY in the PRECOMP VAD supplement's
    manifest, so the read must be able to name that directory; a read that
    cannot is structurally incapable of scoring the fourth registered arm."""

    def test_cli_accepts_vad_manifest_dir_and_threads_it_through(self, tmp_path, monkeypatch):
        captured: dict[str, object] = {}

        def _fake_run_read(**kwargs):
            captured.update(kwargs)
            return {"pooled_by_arm": {}, "deployment_gap": {}}

        monkeypatch.setattr(reader, "run_read", _fake_run_read)
        rc = reader.main(
            [
                "--data-dir", str(tmp_path / "data"),
                "--responses-dir", str(tmp_path / "responses"),
                "--vad-manifest-dir", str(tmp_path / "vad-manifest"),
                "--meetings", "MTG1",
                "--out-dir", str(tmp_path / "out"),
            ]
        )
        assert rc == 0
        assert captured["vad_manifest_dir"] == tmp_path / "vad-manifest"

    def test_cli_defaults_vad_manifest_dir_to_none(self, tmp_path, monkeypatch):
        captured: dict[str, object] = {}

        def _fake_run_read(**kwargs):
            captured.update(kwargs)
            return {"pooled_by_arm": {}, "deployment_gap": {}}

        monkeypatch.setattr(reader, "run_read", _fake_run_read)
        reader.main(
            [
                "--data-dir", str(tmp_path / "data"),
                "--responses-dir", str(tmp_path / "responses"),
                "--meetings", "MTG1",
                "--out-dir", str(tmp_path / "out"),
            ]
        )
        assert captured["vad_manifest_dir"] is None


class TestLoadAllResponses:
    def test_merges_multiple_chunk_files(self, tmp_path):
        responses_dir = tmp_path / "responses"
        _write_response(responses_dir, 0, "req-a", "text-a")
        _write_response(responses_dir, 1, "req-b", "text-b")
        merged = reader.load_all_responses(responses_dir)
        assert set(merged) == {"req-a", "req-b"}

    def test_skips_non_ok_records(self, tmp_path):
        path = tmp_path / "responses" / "chunk0000-responses.jsonl"
        path.parent.mkdir(parents=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps({"request_id": "r1", "outcome": "error"}) + "\n")
        merged = reader.load_all_responses(tmp_path / "responses")
        assert merged == {}
