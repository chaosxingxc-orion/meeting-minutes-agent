"""Tests for ``scripts/diar_smoke_read.py``: RTTM loading, the
``resolved_meetings`` injection seam (no real AMI annotation bytes needed),
the end-to-end read (per-meeting metrics + pooled DER + verdict + written
files), missing-arm-output handling, and the one-shot output-dir guard."""

from __future__ import annotations

import json
from pathlib import Path

import diar_smoke_read as reader
import pytest

from meeting_minutes_agent.chunking.rttm import write_rttm_text
from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Utterance
from meeting_minutes_agent.probes.diar_smoke_scoring import (
    DiarSmokeReadOutputExistsError,
    STATUS_TOOL_LOCKED_B,
)


def _resolved_meeting(meeting_id: str) -> ResolvedMeeting:
    transcript = (
        Utterance(id="u0", speaker="A", start=0.0, end=10.0, text="hello", word_ids=()),
        Utterance(id="u1", speaker="B", start=10.0, end=20.0, text="world", word_ids=()),
    )
    return ResolvedMeeting(
        meeting_id=meeting_id, transcript=transcript, dialogue_acts=(), minutes=None,
        evidence_links=(), topics=(), orphans=(),
    )


def _write_rttm(flight_dir: Path, arm: str, meeting_id: str, turns) -> None:
    path = reader.rttm_path_for(flight_dir, arm, meeting_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(write_rttm_text(turns, file_id=meeting_id), encoding="utf-8")


_PERFECT_TURNS = (TurnSpan(0.0, 10.0, "A"), TurnSpan(10.0, 20.0, "B"))
# 0.2 s boundary shift vs the perfect oracle -> 0.2 s confusion / 20 s
# reference per meeting = 1.0 percentage point DER per meeting, small enough
# that pooling two meetings still clears both the parity gate (<= 2.0 pct)
# and the TOOL-LOCKED(B) threshold (<= 22.0 pct) -- see
# TestRunRead.test_end_to_end_tool_locked_b below, which asserts the pooled
# DER in PERCENTAGE POINTS (not the 0..1 DerBreakdown.der fraction).
_SHIFTED_TURNS = (TurnSpan(0.0, 9.8, "A"), TurnSpan(9.8, 20.0, "B"))


class TestLoadHypothesisTurns:
    def test_returns_none_when_no_rttm_file(self, tmp_path):
        assert reader.load_hypothesis_turns(tmp_path, "A", "MTG1") is None

    def test_parses_the_written_rttm(self, tmp_path):
        _write_rttm(tmp_path, "A", "MTG1", _PERFECT_TURNS)
        assert reader.load_hypothesis_turns(tmp_path, "A", "MTG1") == _PERFECT_TURNS


class TestRunRead:
    def test_end_to_end_tool_locked_b(self, tmp_path):
        flight_dir = tmp_path / "flight"
        out_dir = tmp_path / "read"
        meetings = ["MTG1", "MTG2"]
        for meeting_id in meetings:
            _write_rttm(flight_dir, "A", meeting_id, _PERFECT_TURNS)
            _write_rttm(flight_dir, "B", meeting_id, _SHIFTED_TURNS)

        document = reader.run_read(
            data_dir=tmp_path,  # unused: resolved_meetings injected below
            flight_dir=flight_dir,
            out_dir=out_dir,
            force=False,
            meetings=meetings,
            arms=("A", "B"),
            resolved_meetings={m: _resolved_meeting(m) for m in meetings},
        )

        assert document["verdict"]["status"] == STATUS_TOOL_LOCKED_B
        # Percentage points (the evaluator's registered unit), not the 0..1
        # DerBreakdown.der fraction: pooled 0.4 s error / 40 s reference =
        # 1.0 percentage point, not 0.01.
        assert document["verdict"]["der_a_no_collar_overlap"] == pytest.approx(0.0)
        assert document["verdict"]["der_b_no_collar_overlap"] == pytest.approx(1.0)
        assert document["verdict"]["a_load_failed"] is False
        assert document["verdict"]["b_load_failed"] is False
        assert (out_dir / "verdict.json").is_file()
        assert (out_dir / "report.txt").is_file()
        on_disk = json.loads((out_dir / "verdict.json").read_text(encoding="utf-8"))
        assert on_disk == document
        report_text = (out_dir / "report.txt").read_text(encoding="utf-8")
        assert STATUS_TOOL_LOCKED_B in report_text

    def test_arm_with_no_rttm_output_anywhere_is_load_failed(self, tmp_path):
        flight_dir = tmp_path / "flight"
        out_dir = tmp_path / "read"
        meetings = ["MTG1"]
        _write_rttm(flight_dir, "A", "MTG1", _PERFECT_TURNS)
        # Arm B never wrote any RTTM for any meeting.

        document = reader.run_read(
            data_dir=tmp_path, flight_dir=flight_dir, out_dir=out_dir, force=False,
            meetings=meetings, arms=("A", "B"),
            resolved_meetings={m: _resolved_meeting(m) for m in meetings},
        )

        assert document["verdict"]["b_load_failed"] is True
        assert document["verdict"]["a_load_failed"] is False
        assert document["pooled_no_collar_with_overlap"]["B"] is None
        assert document["per_meeting"]["MTG1"]["B"] is None

    def test_one_shot_guard_refuses_a_second_read(self, tmp_path):
        flight_dir = tmp_path / "flight"
        out_dir = tmp_path / "read"
        meetings = ["MTG1"]
        _write_rttm(flight_dir, "A", "MTG1", _PERFECT_TURNS)
        _write_rttm(flight_dir, "B", "MTG1", _PERFECT_TURNS)
        resolved = {m: _resolved_meeting(m) for m in meetings}

        reader.run_read(
            data_dir=tmp_path, flight_dir=flight_dir, out_dir=out_dir, force=False,
            meetings=meetings, arms=("A", "B"), resolved_meetings=resolved,
        )
        with pytest.raises(DiarSmokeReadOutputExistsError):
            reader.run_read(
                data_dir=tmp_path, flight_dir=flight_dir, out_dir=out_dir, force=False,
                meetings=meetings, arms=("A", "B"), resolved_meetings=resolved,
            )

    def test_force_allows_overwriting_a_prior_read(self, tmp_path):
        flight_dir = tmp_path / "flight"
        out_dir = tmp_path / "read"
        meetings = ["MTG1"]
        _write_rttm(flight_dir, "A", "MTG1", _PERFECT_TURNS)
        _write_rttm(flight_dir, "B", "MTG1", _PERFECT_TURNS)
        resolved = {m: _resolved_meeting(m) for m in meetings}

        reader.run_read(
            data_dir=tmp_path, flight_dir=flight_dir, out_dir=out_dir, force=False,
            meetings=meetings, arms=("A", "B"), resolved_meetings=resolved,
        )
        # does not raise:
        reader.run_read(
            data_dir=tmp_path, flight_dir=flight_dir, out_dir=out_dir, force=True,
            meetings=meetings, arms=("A", "B"), resolved_meetings=resolved,
        )


class TestMainCli:
    def test_full_cli_round_trip(self, tmp_path, capsys, monkeypatch):
        flight_dir = tmp_path / "flight"
        out_dir = tmp_path / "read"
        meetings = ["MTG1"]
        _write_rttm(flight_dir, "A", "MTG1", _PERFECT_TURNS)
        _write_rttm(flight_dir, "B", "MTG1", _PERFECT_TURNS)

        # NxtCorpus itself is lazy (no filesystem access at construction);
        # only resolve_meeting needs faking to keep this a zero-annotation-
        # bytes test -- patch the name as imported INTO diar_smoke_read.py
        # (module-local binding), not the resolver module's own attribute.
        monkeypatch.setattr(reader, "resolve_meeting", lambda corpus, meeting_id: _resolved_meeting(meeting_id))

        # The real-resolution path also reads each meeting's WAV for the
        # transport packer's audio-derived slicer inputs (duration + energy
        # pause transitions); fake it to keep this a zero-audio-bytes test
        # while asserting the per-meeting wiring actually happens.
        seen_audio: list[str] = []

        def _fake_audio_inputs(data_dir, meeting_id):
            seen_audio.append(meeting_id)
            return None, ()

        monkeypatch.setattr(reader, "audio_derived_slicer_inputs", _fake_audio_inputs)

        rc = reader.main(
            [
                "--data-dir", str(tmp_path),
                "--flight-dir", str(flight_dir),
                "--out-dir", str(out_dir),
                "--meetings", *meetings,
                "--arms", "A", "B",
            ]
        )

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["verdict"]["status"] == STATUS_TOOL_LOCKED_B
        assert seen_audio == meetings
        on_disk = json.loads((out_dir / "verdict.json").read_text(encoding="utf-8"))
        assert on_disk["audio_slicer_inputs"] == {
            "MTG1": {"total_duration_s": None, "n_pause_transitions": 0}
        }
