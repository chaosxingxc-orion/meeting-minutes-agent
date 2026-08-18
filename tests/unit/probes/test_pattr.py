"""Tests for :mod:`meeting_minutes_agent.probes.pattr`: manifest loading and
the three arms' request builders. Runs entirely on the hand-built
:func:`sample_manifest_document` fixture -- no real AMI bytes, no network."""

from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.heads.transcribe_attribute import (
    DECLARED_GRID_SECTION_HEADER,
    TEMPLATE_ID as ATTRIBUTE_TEMPLATE_ID,
    TRANSCRIBE_ONLY_TEMPLATE_ID,
)
from meeting_minutes_agent.probes.pattr import (
    ARM_A_FREE,
    ARM_A_GRID,
    ARM_A_TURN,
    ARMS,
    PattrManifest,
    PattrManifestError,
    build_arm_requests,
    build_free_requests,
    build_grid_requests,
    build_turn_requests,
    load_pattr_manifest,
    summarize_all_arms,
    summarize_arm,
)

from .fixtures import sample_manifest_document


def _manifest() -> PattrManifest:
    return PattrManifest(raw=sample_manifest_document(), source_path=None)


# ---------------------------------------------------------------------------
# manifest loading (fail-closed)
# ---------------------------------------------------------------------------


def test_load_pattr_manifest_happy_path(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(sample_manifest_document()), encoding="utf-8")
    manifest = load_pattr_manifest(path)
    assert manifest.selected_meetings == ("MTG1", "MTG2")
    assert manifest.seed == 1


def test_load_pattr_manifest_rejects_unknown_schema_version(tmp_path):
    doc = sample_manifest_document()
    doc["schema_version"] = "9.9.9"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PattrManifestError, match="schema_version"):
        load_pattr_manifest(path)


def test_load_pattr_manifest_rejects_missing_top_level_field(tmp_path):
    doc = sample_manifest_document()
    del doc["meetings"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PattrManifestError, match="missing top-level fields"):
        load_pattr_manifest(path)


def test_load_pattr_manifest_rejects_empty_selected_meetings(tmp_path):
    doc = sample_manifest_document()
    doc["selected_meetings"] = []
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PattrManifestError, match="empty or non-list"):
        load_pattr_manifest(path)


def test_load_pattr_manifest_rejects_selected_meeting_absent_from_meetings(tmp_path):
    doc = sample_manifest_document()
    doc["selected_meetings"].append("GHOST")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PattrManifestError, match="GHOST"):
        load_pattr_manifest(path)


def test_manifest_unknown_meeting_raises():
    manifest = _manifest()
    with pytest.raises(PattrManifestError):
        manifest.meeting("GHOST")


def test_manifest_transport_bound_violations_defaults_empty():
    manifest = _manifest()
    assert manifest.transport_bound_violations == ()


def test_manifest_transport_bound_violations_reads_the_field_when_present():
    doc = sample_manifest_document()
    doc["transport_bound_violations"] = [{"meeting_id": "MTG1", "slice_index": 0, "duration_s": 127.8, "max_audio_seconds": 120.0}]
    manifest = PattrManifest(raw=doc, source_path=None)
    assert len(manifest.transport_bound_violations) == 1
    assert manifest.transport_bound_violations[0]["meeting_id"] == "MTG1"


def test_manifest_audio_relpath_helpers():
    manifest = _manifest()
    assert (
        manifest.slice_audio_relpath("MTG1", "MTG1-slice0000.wav")
        == "derived/meeting-minutes/pattr-smoke/slices/MTG1/MTG1-slice0000.wav"
    )
    assert (
        manifest.turn_clip_audio_relpath("MTG1", "MTG1-turn0000.wav")
        == "derived/meeting-minutes/pattr-smoke/turn-clips/MTG1/MTG1-turn0000.wav"
    )


# ---------------------------------------------------------------------------
# A-grid: grid present
# ---------------------------------------------------------------------------


def test_build_grid_requests_count_equals_n_slices():
    manifest = _manifest()
    requests = build_grid_requests(manifest)
    assert len(requests) == 3  # 2 (MTG1) + 1 (MTG2)
    assert all(r.arm == ARM_A_GRID for r in requests)


def test_build_grid_requests_every_request_carries_the_declared_grid():
    manifest = _manifest()
    requests = build_grid_requests(manifest)
    for r in requests:
        assert r.head_request.template_id == ATTRIBUTE_TEMPLATE_ID
        assert any(part.startswith(DECLARED_GRID_SECTION_HEADER) for part in r.head_request.supplied_text)


def test_build_grid_requests_grid_content_matches_the_slice_turn_table():
    manifest = _manifest()
    requests = {r.request_id: r for r in build_grid_requests(manifest)}
    r0 = requests["pattr-grid-MTG1-slice0000"]
    grid_part = next(p for p in r0.head_request.supplied_text if p.startswith(DECLARED_GRID_SECTION_HEADER))
    assert "[0] 0.00-40.00 A" in grid_part
    assert "[1] 40.00-90.00 B" in grid_part


def test_build_grid_requests_ids_deterministic_and_unique():
    manifest = _manifest()
    ids_a = [r.request_id for r in build_grid_requests(manifest)]
    ids_b = [r.request_id for r in build_grid_requests(manifest)]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))
    assert "pattr-grid-MTG1-slice0000" in ids_a
    assert "pattr-grid-MTG2-slice0000" in ids_a


def test_build_grid_requests_audio_relpath_and_seconds():
    manifest = _manifest()
    requests = {r.request_id: r for r in build_grid_requests(manifest)}
    r1 = requests["pattr-grid-MTG1-slice0001"]
    assert r1.audio_relpath == "derived/meeting-minutes/pattr-smoke/slices/MTG1/MTG1-slice0001.wav"
    assert r1.audio_seconds == pytest.approx(90.0)  # 180.0 - 90.0
    assert r1.slice_index == 1
    assert r1.turn_index is None
    assert r1.known_speaker is None


# ---------------------------------------------------------------------------
# A-free: same shape, grid absent
# ---------------------------------------------------------------------------


def test_build_free_requests_count_equals_grid_requests():
    manifest = _manifest()
    assert len(build_free_requests(manifest)) == len(build_grid_requests(manifest))


def test_build_free_requests_never_carries_a_grid_block():
    manifest = _manifest()
    for r in build_free_requests(manifest):
        assert r.head_request.template_id == ATTRIBUTE_TEMPLATE_ID
        assert not any(part.startswith(DECLARED_GRID_SECTION_HEADER) for part in r.head_request.supplied_text)


def test_build_free_requests_ids_use_the_free_slug():
    manifest = _manifest()
    ids = [r.request_id for r in build_free_requests(manifest)]
    assert "pattr-free-MTG1-slice0000" in ids
    assert all(r.arm == ARM_A_FREE for r in build_free_requests(manifest))


# ---------------------------------------------------------------------------
# A-turn: one request per turn clip, per-turn cutting
# ---------------------------------------------------------------------------


def test_build_turn_requests_count_equals_n_turn_clips():
    manifest = _manifest()
    requests = build_turn_requests(manifest)
    assert len(requests) == 6  # 4 (MTG1) + 2 (MTG2)
    assert all(r.arm == ARM_A_TURN for r in requests)


def test_build_turn_requests_use_the_transcribe_only_template_no_grid_no_context():
    manifest = _manifest()
    for r in build_turn_requests(manifest):
        assert r.head_request.template_id == TRANSCRIBE_ONLY_TEMPLATE_ID
        assert r.head_request.supplied_text == ()


def test_build_turn_requests_cut_to_the_turn_clip_not_the_slice():
    manifest = _manifest()
    requests = {r.request_id: r for r in build_turn_requests(manifest)}
    r0 = requests["pattr-turn-MTG1-turn0000"]
    assert r0.audio_relpath == "derived/meeting-minutes/pattr-smoke/turn-clips/MTG1/MTG1-turn0000.wav"
    assert r0.audio_seconds == pytest.approx(40.0)
    assert r0.known_speaker == "A"
    assert r0.turn_index == 0
    assert r0.slice_index == 0


def test_build_turn_requests_known_speaker_by_construction_for_every_clip():
    manifest = _manifest()
    by_id = {r.request_id: r.known_speaker for r in build_turn_requests(manifest)}
    assert by_id["pattr-turn-MTG1-turn0001"] == "B"
    assert by_id["pattr-turn-MTG1-turn0002"] == "A"
    assert by_id["pattr-turn-MTG2-turn0000"] == "C"
    assert by_id["pattr-turn-MTG2-turn0001"] == "D"


# ---------------------------------------------------------------------------
# dispatch + summaries
# ---------------------------------------------------------------------------


def test_build_arm_requests_dispatches_by_name():
    manifest = _manifest()
    for arm, builder in ((ARM_A_GRID, build_grid_requests), (ARM_A_FREE, build_free_requests), (ARM_A_TURN, build_turn_requests)):
        assert [r.request_id for r in build_arm_requests(manifest, arm)] == [r.request_id for r in builder(manifest)]


def test_build_arm_requests_rejects_unknown_arm():
    manifest = _manifest()
    with pytest.raises(ValueError, match="unknown P-ATTR arm"):
        build_arm_requests(manifest, "A-bogus")


def test_summarize_arm_counts_and_audio_seconds():
    manifest = _manifest()
    summary = summarize_arm(ARM_A_GRID, build_grid_requests(manifest))
    assert summary.arm == ARM_A_GRID
    assert summary.n_requests == 3
    assert summary.n_meetings == 2
    assert summary.total_audio_seconds == pytest.approx(240.0)  # 90 + 90 + 60


def test_summarize_all_arms_matches_manifest_totals():
    manifest = _manifest()
    summaries = summarize_all_arms(manifest)
    assert set(summaries) == set(ARMS)
    assert summaries[ARM_A_GRID].n_requests == 3
    assert summaries[ARM_A_FREE].n_requests == 3
    assert summaries[ARM_A_TURN].n_requests == 6
    assert summaries[ARM_A_GRID].total_audio_seconds == pytest.approx(240.0)
    assert summaries[ARM_A_TURN].total_audio_seconds == pytest.approx(240.0)


def test_pattr_request_spec_to_transport_kwargs(tmp_path):
    manifest = _manifest()
    spec = build_grid_requests(manifest)[0]
    kwargs = spec.to_transport_kwargs(data_dir=tmp_path)
    assert kwargs["request_id"] == spec.request_id
    assert kwargs["audio_path"] == tmp_path / spec.audio_relpath
    assert kwargs["audio_seconds"] == spec.audio_seconds
