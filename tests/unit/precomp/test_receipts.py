"""Tests for :mod:`meeting_minutes_agent.precomp.receipts`: the per-meeting
receipt schema, the per-wave summary, and the fsynced-write + resume-check
helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_minutes_agent.precomp.receipts import (
    SCHEMA_VERSION,
    already_done,
    build_meeting_receipt,
    build_wave_summary,
    fsync_write_json,
    meeting_receipt_path,
    wave_summary_path,
    write_meeting_receipt,
    write_wave_summary,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WAVE_1_RECEIPTS_DIR = _REPO_ROOT / "docs" / "checks" / "2026-08-19-precomp-wave1"


def _receipt(meeting_id: str = "MTG1", *, ok: bool = True) -> dict:
    return build_meeting_receipt(
        wave=1,
        meeting_id=meeting_id,
        ok=ok,
        error=None if ok else "boom",
        diar={"contact": None, "n_turns": 3, "wall_seconds": 1.0, "gpu_seconds_estimate": 0.5},
        slice_plans={"tool": {"n_slices": 2}, "oracle": {"n_slices": 2}},
        cutting={"tool": {"n_entries": 2}, "oracle": {"n_entries": 2}, "wall_seconds": 0.1, "workers": 8},
        encode_warm={"tool": [], "oracle": [], "wall_seconds": 0.2, "n_calls": 4},
        metrics={},
        budget_after={"encode_calls_used": 4},
        recorded_utc="2026-08-19T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def test_meeting_receipt_path_shape(tmp_path):
    path = meeting_receipt_path(tmp_path, "MTG1")
    assert path == tmp_path / "receipts" / "MTG1-receipt.json"


def test_wave_summary_path_shape(tmp_path):
    assert wave_summary_path(tmp_path) == tmp_path / "wave-summary.json"


# ---------------------------------------------------------------------------
# fsync_write_json
# ---------------------------------------------------------------------------


def test_fsync_write_json_round_trips(tmp_path):
    path = tmp_path / "a" / "b" / "out.json"
    fsync_write_json(path, {"x": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"x": 1}


# ---------------------------------------------------------------------------
# build_meeting_receipt: schema
# ---------------------------------------------------------------------------


def test_build_meeting_receipt_carries_every_top_level_field():
    receipt = _receipt()
    assert receipt["schema_version"] == SCHEMA_VERSION
    assert receipt["wave"] == 1
    assert receipt["meeting_id"] == "MTG1"
    assert receipt["ok"] is True
    assert receipt["error"] is None
    for key in ("diar", "slice_plans", "cutting", "encode_warm", "metrics", "budget_after", "recorded_utc"):
        assert key in receipt


def test_build_meeting_receipt_json_serializable():
    json.dumps(_receipt())  # must not raise


# ---------------------------------------------------------------------------
# write_meeting_receipt / already_done
# ---------------------------------------------------------------------------


def test_write_meeting_receipt_writes_under_the_conventional_path(tmp_path):
    write_meeting_receipt(tmp_path, _receipt("MTG7"))
    assert meeting_receipt_path(tmp_path, "MTG7").is_file()


class TestAlreadyDone:
    def test_false_when_no_receipt(self, tmp_path):
        assert already_done(tmp_path, "MTG1") is False

    def test_true_when_receipt_ok_and_schema_matches(self, tmp_path):
        write_meeting_receipt(tmp_path, _receipt("MTG1", ok=True))
        assert already_done(tmp_path, "MTG1") is True

    def test_false_when_receipt_not_ok(self, tmp_path):
        write_meeting_receipt(tmp_path, _receipt("MTG1", ok=False))
        assert already_done(tmp_path, "MTG1") is False

    def test_false_when_schema_version_does_not_match(self, tmp_path):
        receipt = _receipt("MTG1", ok=True)
        receipt["schema_version"] = "0.0.1-stale"
        write_meeting_receipt(tmp_path, receipt)
        assert already_done(tmp_path, "MTG1") is False

    def test_false_when_unparsable(self, tmp_path):
        path = meeting_receipt_path(tmp_path, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text("not json", encoding="utf-8")
        assert already_done(tmp_path, "MTG1") is False

    def test_false_when_json_is_not_an_object(self, tmp_path):
        path = meeting_receipt_path(tmp_path, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert already_done(tmp_path, "MTG1") is False


# ---------------------------------------------------------------------------
# schema-version backward compatibility (the G1 VAD-supplement extension):
# SCHEMA_VERSION bumped to "1.1.0" must still recognize the 18 already-
# committed wave-1 receipts (schema_version "1.0.0", no "vad" key at all)
# as already-done -- module docstring / already_done's own docstring.
# ---------------------------------------------------------------------------


class TestSchemaVersionBackwardCompatibility:
    def test_current_schema_version_is_a_minor_bump_over_1_0_0(self):
        # Documents the exact compatibility contract this class tests: a
        # MINOR bump (same major "1"), never a major bump, is what keeps
        # old "1.0.0" receipts readable as already-done below.
        assert SCHEMA_VERSION.split(".")[0] == "1"

    def test_an_old_1_0_0_ok_receipt_with_no_vad_key_is_still_already_done(self, tmp_path):
        receipt = build_meeting_receipt(
            wave=1,
            meeting_id="MTG1",
            ok=True,
            error=None,
            diar={"contact": None, "n_turns": 3, "wall_seconds": 1.0, "gpu_seconds_estimate": 0.5},
            slice_plans={"tool": {"n_slices": 2}, "oracle": {"n_slices": 2}},  # no "vad" key, like the real ones
            cutting={"tool": {"n_entries": 2}, "oracle": {"n_entries": 2}, "wall_seconds": 0.1, "workers": 8},
            encode_warm={"tool": [], "oracle": [], "wall_seconds": 0.2, "n_calls": 4},
            metrics={},
            budget_after={},
            recorded_utc="2026-08-19T00:00:00+00:00",
        )
        receipt["schema_version"] = "1.0.0"  # simulate a receipt written before this bump
        write_meeting_receipt(tmp_path, receipt)
        assert already_done(tmp_path, "MTG1") is True

    def test_a_future_major_bump_would_not_be_recognized(self, tmp_path):
        receipt = build_meeting_receipt(
            wave=1, meeting_id="MTG1", ok=True, error=None,
            diar={}, slice_plans={}, cutting={}, encode_warm={}, metrics={}, budget_after={},
            recorded_utc="2026-08-19T00:00:00+00:00",
        )
        receipt["schema_version"] = "2.0.0"
        write_meeting_receipt(tmp_path, receipt)
        assert already_done(tmp_path, "MTG1") is False

    @pytest.mark.skipif(
        not _WAVE_1_RECEIPTS_DIR.is_dir(), reason="wave-1 committed receipts not present in this checkout"
    )
    def test_a_real_committed_wave_1_receipt_is_recognized_as_already_done(self):
        # Concrete regression against the ACTUAL 18 committed wave-1
        # receipts (task instruction: "backward-compatible with the 18
        # committed wave-1 receipts") -- not a hand-built fixture.
        assert already_done(_WAVE_1_RECEIPTS_DIR, "ES2011a") is True

    @pytest.mark.skipif(
        not _WAVE_1_RECEIPTS_DIR.is_dir(), reason="wave-1 committed receipts not present in this checkout"
    )
    def test_every_real_committed_wave_1_receipt_declares_schema_1_0_0_with_no_vad_key(self):
        # Pins the exact on-disk shape this compatibility layer must keep
        # reading: "1.0.0", no "vad" key under slice_plans/cutting/encode_warm.
        receipts_dir = _WAVE_1_RECEIPTS_DIR / "receipts"
        paths = sorted(receipts_dir.glob("*-receipt.json"))
        assert len(paths) == 18
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["schema_version"] == "1.0.0"
            assert "vad" not in data["slice_plans"]
            assert "vad" not in data["cutting"]
            assert "vad" not in data["encode_warm"]


# ---------------------------------------------------------------------------
# build_wave_summary / write_wave_summary
# ---------------------------------------------------------------------------


def test_build_wave_summary_counts_ok_and_error():
    outcomes = [_receipt("MTG1", ok=True), _receipt("MTG2", ok=False), _receipt("MTG3", ok=True)]
    summary = build_wave_summary(outcomes, wave=1, budget_totals={"encode_calls_used": 4}, stopped_reason=None)
    assert summary["n_meetings"] == 3
    assert summary["n_ok"] == 2
    assert summary["n_error"] == 1
    assert summary["stopped_reason"] is None
    assert summary["wave"] == 1


def test_write_wave_summary_writes_and_round_trips(tmp_path):
    summary = build_wave_summary([_receipt("MTG1")], wave=2, budget_totals={}, stopped_reason="budget stop")
    write_wave_summary(tmp_path, summary)
    on_disk = json.loads(wave_summary_path(tmp_path).read_text(encoding="utf-8"))
    assert on_disk == summary
