"""Tests for ``scripts/launch_pprompt_sweep.py``.

This engineering mission ONLY import-verifies and wiring-tests this script
(mirrors ``tests/unit/scripts/test_launch_pattr_smoke.py``'s own scope
statement): every request in these tests goes through a FAKE ``post``
callable, never a real ``llama-server`` process or network call."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import launch_pprompt_sweep as launcher
import pytest

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.probes.pattr import PattrManifest
from meeting_minutes_agent.probes.pprompt import ARM_X1, ARM_X2


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
                "meeting_duration_s": 200.0,
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


_DONOR_TEXT = "donor text zero"
_DONOR_SOURCE_RELATIVE = "runs/a-turn-responses.jsonl"


def _small_binding_document(*, donor_text: str = _DONOR_TEXT) -> dict:
    return {
        "schema_version": "1.0.0",
        "seed": 20260818,
        "corrupt_arms": {
            "X1": {"label_derangement": {"A": "B", "B": "A"}},
            "X2": {
                "donor_source_relpath": _DONOR_SOURCE_RELATIVE,
                "tail_entries": {
                    "MTG1": [
                        {
                            "donor_meeting_id": "MTG2",
                            "donor_request_id": "pattr-turn-MTG2-turn0000",
                            "donor_turn_index": 0,
                            "donor_slice_index": 0,
                            "speaker": "C",
                            "text_sha256": hashlib.sha256(donor_text.encode("utf-8")).hexdigest(),
                            "text_length_chars": len(donor_text),
                        }
                    ]
                },
            },
        },
    }


def _write_binding(tmp_path: Path, *, donor_text: str = _DONOR_TEXT) -> Path:
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(_small_binding_document(donor_text=donor_text)), encoding="utf-8")
    return path


def _write_donor_jsonl(data_dir: Path, *, request_id="pattr-turn-MTG2-turn0000", text=_DONOR_TEXT) -> None:
    path = data_dir / _DONOR_SOURCE_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"request_id": request_id, "meeting_id": "MTG2", "turn_index": 0, "outcome": "ok", "text": text}
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def _write_fake_audio(data_dir: Path, relpath: str) -> None:
    path = Path(data_dir) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF....WAVEfmt ")


def _canned_response(text="A|hello there") -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}], "usage": {}}).encode("utf-8")


# ---------------------------------------------------------------------------
# import verification
# ---------------------------------------------------------------------------


def test_module_imports_cleanly_without_side_effects():
    assert hasattr(launcher, "main")
    assert hasattr(launcher, "run_arm")
    assert hasattr(launcher, "build_transport_and_receipt")
    assert hasattr(launcher, "load_x2_tail_segments")


def test_help_does_not_execute_a_flight():
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--help"])
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# load_pprompt_binding: fail-closed
# ---------------------------------------------------------------------------


def test_load_pprompt_binding_happy_path(tmp_path):
    path = _write_binding(tmp_path)
    binding = launcher.load_pprompt_binding(path)
    assert binding["seed"] == 20260818


def test_load_pprompt_binding_rejects_missing_field(tmp_path):
    doc = _small_binding_document()
    del doc["corrupt_arms"]
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(launcher.PpromptBindingError, match="corrupt_arms"):
        launcher.load_pprompt_binding(path)


def test_load_pprompt_binding_rejects_missing_x1_or_x2(tmp_path):
    doc = _small_binding_document()
    del doc["corrupt_arms"]["X1"]
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(launcher.PpromptBindingError, match="X1"):
        launcher.load_pprompt_binding(path)


# ---------------------------------------------------------------------------
# load_x2_tail_segments: real-I/O, fail-closed hash verification
# ---------------------------------------------------------------------------


def test_load_x2_tail_segments_resolves_and_verifies(tmp_path):
    _write_donor_jsonl(tmp_path)
    binding = _small_binding_document()
    tails = launcher.load_x2_tail_segments(binding, tmp_path)
    assert set(tails) == {"MTG1"}
    assert len(tails["MTG1"]) == 1
    assert tails["MTG1"][0].speaker == "C"
    assert tails["MTG1"][0].text == _DONOR_TEXT


def test_load_x2_tail_segments_missing_source_file_refuses(tmp_path):
    binding = _small_binding_document()
    with pytest.raises(launcher.PpromptBindingError, match="not found"):
        launcher.load_x2_tail_segments(binding, tmp_path)


def test_load_x2_tail_segments_missing_donor_request_id_refuses(tmp_path):
    _write_donor_jsonl(tmp_path, request_id="some-other-request-id")
    binding = _small_binding_document()
    with pytest.raises(launcher.PpromptBindingError, match="not found in"):
        launcher.load_x2_tail_segments(binding, tmp_path)


def test_load_x2_tail_segments_hash_mismatch_refuses(tmp_path):
    # donor JSONL text does not match the hash pinned in the binding manifest
    _write_donor_jsonl(tmp_path, text="a substituted different text")
    binding = _small_binding_document(donor_text=_DONOR_TEXT)  # pinned hash is for the ORIGINAL text
    with pytest.raises(launcher.PpromptBindingError, match="hash mismatch"):
        launcher.load_x2_tail_segments(binding, tmp_path)


# ---------------------------------------------------------------------------
# --summary-only
# ---------------------------------------------------------------------------


def test_summary_only_grid_cell_prints_expected_counts(tmp_path, capsys):
    pattr_path = _write_pattr_manifest(tmp_path)
    binding_path = _write_binding(tmp_path)
    rc = launcher.main(
        [
            "--data-dir", str(tmp_path),
            "--pattr-manifest", str(pattr_path),
            "--binding", str(binding_path),
            "--arm", "T2-A1",
            "--summary-only",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["T2-A1"]["n_requests"] == 1


def test_summary_only_x2_resolves_the_tail_from_disk(tmp_path, capsys):
    pattr_path = _write_pattr_manifest(tmp_path)
    binding_path = _write_binding(tmp_path)
    _write_donor_jsonl(tmp_path)
    rc = launcher.main(
        [
            "--data-dir", str(tmp_path),
            "--pattr-manifest", str(pattr_path),
            "--binding", str(binding_path),
            "--arm", ARM_X2,
            "--summary-only",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed[ARM_X2]["n_requests"] == 1


def test_missing_flight_args_without_summary_only_errors_cleanly(tmp_path):
    pattr_path = _write_pattr_manifest(tmp_path)
    binding_path = _write_binding(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(
            [
                "--data-dir", str(tmp_path),
                "--pattr-manifest", str(pattr_path),
                "--binding", str(binding_path),
                "--arm", "T1-A1",
            ]
        )
    assert excinfo.value.code != 0


# ---------------------------------------------------------------------------
# run_arm: real wiring, fake transport
# ---------------------------------------------------------------------------


def _fixtures(tmp_path):
    pattr_manifest = PattrManifest(raw=_small_pattr_manifest_document(), source_path=None)
    binding = _small_binding_document()
    _write_fake_audio(tmp_path, "derived/meeting-minutes/pattr-smoke/slices/MTG1/MTG1-slice0000.wav")
    budget = CallBudget(BudgetLimits(max_calls=10, max_audio_seconds=1000.0))
    server_identity = ServerIdentity(base_url="http://x", model_files=(ModelFileRef(path="m.gguf", sha256="a" * 64),))
    receipt = FlightReceipt(server_identity, budget)
    return pattr_manifest, binding, budget, receipt


def test_run_arm_grid_cell_dispatches_one_request_per_slice(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    calls = []

    def fake_post(url, body):
        calls.append(body)
        return _canned_response()

    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=fake_post)
    result = launcher.run_arm(
        "T2-A1", pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt
    )
    assert result is receipt
    assert len(calls) == 1
    assert budget.totals["calls_used"] == 1


def test_run_arm_x1_uses_the_bindings_label_derangement(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    bodies = []

    def fake_post(url, body):
        bodies.append(json.loads(body.decode("utf-8")))
        return _canned_response()

    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=fake_post)
    launcher.run_arm(ARM_X1, pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt)
    assert len(bodies) == 1
    system_text = bodies[0]["messages"][0]["content"]
    # true roster is {A, B}; the binding's derangement swaps A<->B, so the
    # deranged roster is still {A, B} as a SET under this particular
    # 2-cycle -- what matters here is that the request actually flew and
    # carried a MEETING CONTEXT block at all (the label-content assertion
    # itself is covered directly in tests/unit/probes/test_pprompt.py).
    assert "MEETING CONTEXT" in system_text


def test_run_arm_x2_resolves_and_verifies_the_donor_tail_from_data_dir(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    _write_donor_jsonl(tmp_path)
    bodies = []

    def fake_post(url, body):
        bodies.append(json.loads(body.decode("utf-8")))
        return _canned_response()

    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=fake_post)
    launcher.run_arm(ARM_X2, pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt)
    assert len(bodies) == 1
    user_text_parts = [p.get("text", "") for p in bodies[0]["messages"][1]["content"] if p.get("type") == "text"]
    assert any(_DONOR_TEXT in part for part in user_text_parts)


def test_run_arm_x2_without_the_donor_file_on_disk_refuses(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=lambda u, b: _canned_response())
    with pytest.raises(launcher.PpromptBindingError):
        launcher.run_arm(ARM_X2, pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt)


def test_response_sink_persists_one_scoreable_record(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=lambda u, b: _canned_response())
    out = tmp_path / "responses.jsonl"
    with launcher.ResponseSink(out) as sink:
        launcher.run_arm("T1-A1", pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt, sink=sink)
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["outcome"] == "ok"
    assert records[0]["text"] == "A|hello there"
    assert records[0]["arm"] == "T1-A1"


def test_resume_skips_recorded_ids_without_spending_budget(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)
    calls = []

    def fake_post(url, body):
        calls.append(body)
        return _canned_response()

    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=fake_post)
    out = tmp_path / "responses.jsonl"
    out.write_text(json.dumps({"request_id": "pprompt-T1-A1-MTG1-slice0000", "outcome": "ok"}) + "\n", encoding="utf-8")

    already = launcher.load_recorded_request_ids(out)
    assert already == {"pprompt-T1-A1-MTG1-slice0000"}

    launcher.run_arm(
        "T1-A1", pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt, skip_request_ids=already
    )
    assert len(calls) == 0
    assert budget.totals["calls_used"] == 0


def test_failed_request_is_persisted_then_propagates(tmp_path):
    pattr_manifest, binding, budget, receipt = _fixtures(tmp_path)

    def failing_post(url, body):
        raise ValueError("boom")

    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=failing_post)
    out = tmp_path / "responses.jsonl"
    with pytest.raises(ValueError):
        with launcher.ResponseSink(out) as sink:
            launcher.run_arm("T1-A1", pattr_manifest, binding, data_dir=tmp_path, transport=transport, receipt=receipt, sink=sink)
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["outcome"] == "error"
    assert launcher.load_recorded_request_ids(out) == set()


def test_build_transport_and_receipt_wires_server_identity():
    transport, receipt = launcher.build_transport_and_receipt(
        base_url="http://127.0.0.1:8080", model_path="m.gguf", model_sha256="a" * 64,
        max_calls=5, max_audio_seconds=100.0, slots=4,
    )
    assert isinstance(transport, LlamaServerTransport)
    assert isinstance(receipt, FlightReceipt)
    assert receipt.server_identity.base_url == "http://127.0.0.1:8080"
