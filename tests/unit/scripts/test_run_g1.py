"""Tests for ``scripts/run_g1.py``.

This engineering mission ONLY import/wiring-verifies this script (task
scope: "MACHINERY ONLY -- no model contact, no flights") -- every frozen-
core contact goes through a FAKE transport ``post`` and every server
lifecycle goes through a FAKE ``popen``/``health_check`` (the same
injection-seam discipline ``tests/unit/scripts/test_run_precomp.py`` and
``tests/unit/probes/test_g1_campaign.py`` already use), never a real
llama-server binary, a real GPU, or a real network call."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import run_g1 as runner
import soundfile as sf

from meeting_minutes_agent.chunking.rttm import write_rttm_text
from meeting_minutes_agent.chunking.slicer import TurnSpan, materialize_slice_plan
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.probes import g1, g1_campaign

_NITE_XMLNS = 'xmlns:nite="http://nite.sourceforge.net/"'
_XML_HEADER = '<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>\n'


# ---------------------------------------------------------------------------
# import verification + --help
# ---------------------------------------------------------------------------


def test_module_imports_cleanly():
    assert hasattr(runner, "main")
    assert hasattr(runner, "run_chunk")
    assert hasattr(runner, "run_item")
    assert hasattr(runner, "resolve_slice_plan")


def test_help_does_not_run_anything(capsys):
    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--help"])
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# --summary-only: safe right now, no PRECOMP-cache I/O, no model contact
# ---------------------------------------------------------------------------


class TestSummaryOnly:
    def test_floors_mode_reports_dev18_and_all_four_arms(self, capsys):
        rc = runner.main(["--mode", "floors", "--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["meetings"]) == 18
        assert payload["arms"] == list(g1.ARMS)
        assert payload["n_work_items"] == 18 * 4

    def test_path_mode_reports_the_two_registered_meetings(self, capsys):
        rc = runner.main(["--mode", "path", "--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["meetings"] == list(g1_campaign.PATH_MEETINGS)
        assert payload["n_work_items"] == 2 * 4

    def test_ceilings_are_the_registered_defaults(self, capsys):
        rc = runner.main(["--mode", "path", "--data-dir", "unused", "--summary-only"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["ceilings"]["max_calls"] == g1_campaign.CAMPAIGN_MAX_CALLS
        assert payload["ceilings"]["max_gpu_hours"] == g1_campaign.CAMPAIGN_MAX_GPU_HOURS
        assert payload["ceilings"]["max_wall_hours"] == g1_campaign.CAMPAIGN_MAX_WALL_HOURS

    def test_no_qa_questions_without_meetingqa_root(self, capsys):
        rc = runner.main(["--mode", "path", "--data-dir", "unused", "--summary-only"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["n_qa_questions_capped"] == 0

    def test_unknown_mode_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit):
            runner.main(["--mode", "bogus", "--data-dir", "unused", "--summary-only"])


# ---------------------------------------------------------------------------
# required-args gate for a real invocation
# ---------------------------------------------------------------------------


def test_run_chunk_without_server_cmd_errors_cleanly():
    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--mode", "path", "--data-dir", "unused", "--run-chunk", "0"])
    assert excinfo.value.code != 0


def test_missing_run_chunk_and_summary_only_errors_cleanly():
    with pytest.raises(SystemExit):
        runner.main(["--mode", "path", "--data-dir", "unused"])


# ---------------------------------------------------------------------------
# resolve_slice_plan / resolve_all_slice_plans: real RTTM/NXT rebuild
# ---------------------------------------------------------------------------


def _write_nxt(root: Path, meeting_id: str, *, n_utterances: int = 2) -> None:
    def write(subdir: str, name: str, content: str) -> None:
        path = root / subdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_XML_HEADER + content, encoding="utf-8")

    words = "\n".join(
        f'   <w nite:id="{meeting_id}.A.words{i}" starttime="{i * 1.0}" endtime="{i * 1.0 + 0.8}">word{i}</w>'
        for i in range(n_utterances)
    )
    write("words", f"{meeting_id}.A.words.xml", f'<nite:root nite:id="{meeting_id}.A.words" {_NITE_XMLNS}>\n{words}\n</nite:root>\n')

    segments = "\n".join(
        f'   <segment nite:id="{meeting_id}.A.seg.{i}" channel="0" transcriber_start="{i * 1.0}" transcriber_end="{i * 1.0 + 0.8}">\n'
        f'      <nite:child href="{meeting_id}.A.words.xml#id({meeting_id}.A.words{i})..id({meeting_id}.A.words{i})"/>\n'
        f"   </segment>"
        for i in range(n_utterances)
    )
    write("segments", f"{meeting_id}.A.segments.xml", f'<nite:root nite:id="{meeting_id}.A.segs" {_NITE_XMLNS}>\n{segments}\n</nite:root>\n')


def _write_synth_wav(path: Path, duration_s: float = 3.0, *, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(duration_s * sr))
    t = np.arange(n) / sr
    y = 0.2 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    sf.write(str(path), y, sr, subtype="PCM_16")


def _fixture(tmp_path: Path, meeting_id: str = "MTG1", *, duration_s: float = 3.0) -> dict:
    data_dir = tmp_path / "data"
    _write_nxt(data_dir / "datasets/ami/annotations/manual_1.6.2", meeting_id)
    audio_path = data_dir / "datasets/ami/amicorpus" / meeting_id / "audio" / f"{meeting_id}.Mix-Headset.wav"
    _write_synth_wav(audio_path, duration_s=duration_s)

    derived_root = data_dir / "derived/meeting-minutes/precomp"
    rttm_path = derived_root / "rttm" / f"{meeting_id}.rttm"
    rttm_path.parent.mkdir(parents=True, exist_ok=True)
    rttm_path.write_text(write_rttm_text((TurnSpan(0.0, duration_s, "spk1"),), file_id=meeting_id), encoding="utf-8")

    nxt_corpus = NxtCorpus(data_dir / "datasets/ami/annotations/manual_1.6.2")
    return {"data_dir": data_dir, "derived_root": derived_root, "nxt_corpus": nxt_corpus, "audio_path": audio_path}


def _materialize(fx: dict, plan, slice_dir_relative: str, meeting_id: str) -> None:
    """Cut ``plan``'s slice WAVs onto disk at the SAME cache-directory
    convention ``resolve_slice_plan`` names -- what PRECOMP's own
    ``materialize_slice_plan`` call already did for a real campaign; this
    test fixture reproduces that one step so ``run_item``/``run_chunk`` can
    resolve real audio bytes for their transport calls."""

    output_dir = fx["data_dir"] / slice_dir_relative / meeting_id
    materialize_slice_plan(plan, fx["audio_path"], output_dir)


class TestResolveSlicePlan:
    def test_z_turn_rebuilds_from_the_cached_rttm(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_TURN, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        assert plan.meeting_id == "MTG1"
        assert plan.turn_provenance.value == "tool-diar"
        assert slice_dir == runner.DEFAULT_SLICE_DIR_RELATIVE_TOOL

    def test_z_free_reuses_the_same_tool_plan_as_z_turn(self, tmp_path):
        fx = _fixture(tmp_path)
        turn_plan, _ = runner.resolve_slice_plan(
            g1.ARM_Z_TURN, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        free_plan, _ = runner.resolve_slice_plan(
            g1.ARM_Z_FREE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        assert free_plan.content_hash == turn_plan.content_hash

    def test_z_oracle_rebuilds_from_nxt_gold(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_ORACLE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        assert plan.turn_provenance.value == "oracle-turn"
        assert slice_dir == runner.DEFAULT_SLICE_DIR_RELATIVE_ORACLE

    def test_z_nodiar_without_a_vad_manifest_dir_fails_closed(self, tmp_path):
        fx = _fixture(tmp_path)
        with pytest.raises(g1.G1VadSupplementMissingError):
            runner.resolve_slice_plan(
                g1.ARM_Z_NODIAR, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
                nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
            )

    def test_z_nodiar_with_a_missing_manifest_file_fails_closed(self, tmp_path):
        fx = _fixture(tmp_path)
        with pytest.raises(g1.G1VadSupplementMissingError):
            runner.resolve_slice_plan(
                g1.ARM_Z_NODIAR, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
                nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=tmp_path / "vad-manifests",
            )

    def test_z_nodiar_loads_a_real_precomp_written_manifest_end_to_end(self, tmp_path):
        # Closes the gap this mission targets: a manifest written by the
        # REAL PRECOMP VAD-supplement writer resolves cleanly through this
        # script's own --vad-manifest-dir seam -- the exact path a real
        # Z-nodiar flight takes.
        from meeting_minutes_agent.chunking.slicer import build_vad_slice_plan
        from meeting_minutes_agent.precomp.pipeline import write_vad_slice_plan_manifest

        fx = _fixture(tmp_path)
        manifest_dir = fx["derived_root"] / "slices" / "vad-manifest"
        plan = build_vad_slice_plan("MTG1", 3.0)
        write_vad_slice_plan_manifest(manifest_dir, plan)

        loaded_plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_NODIAR, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=manifest_dir,
        )
        assert loaded_plan.meeting_id == "MTG1"
        assert loaded_plan.content_hash == plan.content_hash
        assert slice_dir == runner.DEFAULT_SLICE_DIR_RELATIVE_VAD

    def test_resolve_all_slice_plans_covers_every_meeting_arm_pair(self, tmp_path):
        fx = _fixture(tmp_path)
        plans = runner.resolve_all_slice_plans(
            ["MTG1"], (g1.ARM_Z_TURN, g1.ARM_Z_ORACLE, g1.ARM_Z_FREE), data_dir=fx["data_dir"],
            derived_root=fx["derived_root"], nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        assert set(plans) == {("MTG1", g1.ARM_Z_TURN), ("MTG1", g1.ARM_Z_ORACLE), ("MTG1", g1.ARM_Z_FREE)}


# ---------------------------------------------------------------------------
# run_item / run_chunk: dispatch through a fake transport
# ---------------------------------------------------------------------------


def _canned_post(text: str = "A|hello world"):
    def post(url, body):
        return json.dumps(
            {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}
        ).encode("utf-8")

    return post


def _fake_transport(text: str = "A|hello world") -> LlamaServerTransport:
    budget = CallBudget(BudgetLimits(max_calls=1000, max_audio_seconds=100_000.0))
    return LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=_canned_post(text))


class TestRunItem:
    def test_transcribe_only_arm_dispatches_exactly_n_slice_calls(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_FREE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        _materialize(fx, plan, slice_dir, "MTG1")
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plan.slices))
        receipt = runner.run_item(
            item, data_dir=fx["data_dir"], plan=plan, slice_dir_relative=slice_dir, transport=_fake_transport(),
            sink=None, qa_questions=(),
        )
        assert receipt["ok"] is True, receipt.get("error")
        assert receipt["n_calls"] == len(plan.slices)

    def test_attribution_arm_dispatches_transcribe_plus_minutes(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_TURN, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        _materialize(fx, plan, slice_dir, "MTG1")
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_TURN, n_transcribe=len(plan.slices), n_minutes=1, n_qa=0)
        receipt = runner.run_item(
            item, data_dir=fx["data_dir"], plan=plan, slice_dir_relative=slice_dir, transport=_fake_transport(),
            sink=None, qa_questions=(),
        )
        assert receipt["ok"] is True, receipt.get("error")
        assert receipt["n_calls"] == len(plan.slices) + 1  # + one minutes call

    def test_attribution_arm_dispatches_qa_calls_too(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_ORACLE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        _materialize(fx, plan, slice_dir, "MTG1")
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_ORACLE, n_transcribe=len(plan.slices), n_minutes=1, n_qa=2)

        class Q:
            def __init__(self, i):
                self.example_id = f"q{i}"
                self.question = f"question {i}?"

        receipt = runner.run_item(
            item, data_dir=fx["data_dir"], plan=plan, slice_dir_relative=slice_dir, transport=_fake_transport(),
            sink=None, qa_questions=[Q(1), Q(2)],
        )
        assert receipt["ok"] is True, receipt.get("error")
        assert receipt["n_calls"] == len(plan.slices) + 1 + 2

    def test_a_transport_failure_is_caught_and_recorded_not_raised(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_FREE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        _materialize(fx, plan, slice_dir, "MTG1")

        def failing_post(url, body):
            raise ConnectionError("simulated")

        budget = CallBudget(BudgetLimits(max_calls=10, max_audio_seconds=10_000.0))
        transport = LlamaServerTransport(TransportConfig(base_url="http://x", max_retries=0), budget, post=failing_post)
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plan.slices))
        receipt = runner.run_item(item, data_dir=fx["data_dir"], plan=plan, slice_dir_relative=slice_dir, transport=transport, sink=None, qa_questions=())
        assert receipt["ok"] is False
        assert receipt["error"]

    def test_response_sink_writes_a_line_per_contact(self, tmp_path):
        fx = _fixture(tmp_path)
        plan, slice_dir = runner.resolve_slice_plan(
            g1.ARM_Z_FREE, "MTG1", data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        _materialize(fx, plan, slice_dir, "MTG1")
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plan.slices))
        sink_path = tmp_path / "responses.jsonl"
        with runner.ResponseSink(sink_path) as sink:
            runner.run_item(item, data_dir=fx["data_dir"], plan=plan, slice_dir_relative=slice_dir, transport=_fake_transport(), sink=sink, qa_questions=())
        lines = sink_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == len(plan.slices)
        record = json.loads(lines[0])
        assert record["outcome"] == "ok"
        assert record["arm"] == g1.ARM_Z_FREE


class TestRunChunk:
    def test_runs_every_item_and_writes_receipts(self, tmp_path):
        fx = _fixture(tmp_path)
        plans = runner.resolve_all_slice_plans(
            ["MTG1"], (g1.ARM_Z_TURN, g1.ARM_Z_FREE), data_dir=fx["data_dir"], derived_root=fx["derived_root"],
            nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None,
        )
        for (meeting_id, _arm), (plan, slice_dir) in plans.items():
            _materialize(fx, plan, slice_dir, meeting_id)
        items = tuple(
            g1_campaign.WorkItem(meeting_id="MTG1", arm=arm, n_transcribe=len(plans[("MTG1", arm)][0].slices), n_minutes=(1 if arm in g1.ARMS_WITH_MINUTES_QA else 0))
            for arm in (g1.ARM_Z_TURN, g1.ARM_Z_FREE)
        )
        chunk = g1_campaign.Chunk(index=0, items=items)
        out_dir = tmp_path / "out"
        budget = g1_campaign.G1Budget()

        receipt = runner.run_chunk(
            chunk, data_dir=fx["data_dir"], slice_plans_by_meeting_arm=plans, transport=_fake_transport(), sink=None,
            qa_questions=(), out_dir=out_dir, resume=False, budget=budget,
        )
        assert receipt["n_ok"] == 2
        assert (out_dir / "receipts" / "MTG1-Z-turn-receipt.json").is_file()
        assert (out_dir / "receipts" / "MTG1-Z-free-receipt.json").is_file()

    def test_resume_skips_an_already_ok_item(self, tmp_path):
        fx = _fixture(tmp_path)
        plans = runner.resolve_all_slice_plans(["MTG1"], (g1.ARM_Z_FREE,), data_dir=fx["data_dir"], derived_root=fx["derived_root"], nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None)
        out_dir = tmp_path / "out"
        g1_campaign.write_item_receipt(
            out_dir, g1_campaign.build_item_receipt(meeting_id="MTG1", arm=g1.ARM_Z_FREE, ok=True, error=None, n_calls=1, gpu_seconds=0.0, wall_seconds=0.0, contacts=[])
        )
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plans[("MTG1", g1.ARM_Z_FREE)][0].slices))
        chunk = g1_campaign.Chunk(index=0, items=(item,))

        transport = _fake_transport()
        budget = g1_campaign.G1Budget()
        receipt = runner.run_chunk(chunk, data_dir=fx["data_dir"], slice_plans_by_meeting_arm=plans, transport=transport, sink=None, qa_questions=(), out_dir=out_dir, resume=True, budget=budget)
        assert receipt["n_items"] == 0  # the item was skipped, never re-dispatched

    def test_stop_file_yields_before_the_next_item(self, tmp_path):
        fx = _fixture(tmp_path, "MTG1")
        fx2 = _fixture(tmp_path, "MTG2")
        plans = {}
        plans.update(runner.resolve_all_slice_plans(["MTG1"], (g1.ARM_Z_FREE,), data_dir=fx["data_dir"], derived_root=fx["derived_root"], nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None))
        plans.update(runner.resolve_all_slice_plans(["MTG2"], (g1.ARM_Z_FREE,), data_dir=fx["data_dir"], derived_root=fx["derived_root"], nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None))
        items = (
            g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plans[("MTG1", g1.ARM_Z_FREE)][0].slices)),
            g1_campaign.WorkItem(meeting_id="MTG2", arm=g1.ARM_Z_FREE, n_transcribe=len(plans[("MTG2", g1.ARM_Z_FREE)][0].slices)),
        )
        chunk = g1_campaign.Chunk(index=0, items=items)
        stop_file = tmp_path / "G1_YIELD"
        stop_file.write_text("", encoding="utf-8")
        out_dir = tmp_path / "out"

        receipt = runner.run_chunk(chunk, data_dir=fx["data_dir"], slice_plans_by_meeting_arm=plans, transport=_fake_transport(), sink=None, qa_questions=(), out_dir=out_dir, resume=False, budget=g1_campaign.G1Budget(), stop_file=stop_file)
        assert receipt["n_items"] == 0
        assert "stop-file" in receipt["stopped_reason"]

    def test_budget_exhaustion_yields_before_the_next_item(self, tmp_path):
        fx = _fixture(tmp_path)
        plans = runner.resolve_all_slice_plans(["MTG1"], (g1.ARM_Z_FREE,), data_dir=fx["data_dir"], derived_root=fx["derived_root"], nxt_corpus=fx["nxt_corpus"], vad_manifest_dir=None)
        item = g1_campaign.WorkItem(meeting_id="MTG1", arm=g1.ARM_Z_FREE, n_transcribe=len(plans[("MTG1", g1.ARM_Z_FREE)][0].slices))
        chunk = g1_campaign.Chunk(index=0, items=(item,))
        out_dir = tmp_path / "out"
        budget = g1_campaign.G1Budget(max_calls=0)

        receipt = runner.run_chunk(chunk, data_dir=fx["data_dir"], slice_plans_by_meeting_arm=plans, transport=_fake_transport(), sink=None, qa_questions=(), out_dir=out_dir, resume=False, budget=budget)
        assert receipt["n_items"] == 0
        assert receipt["stopped_reason"] is not None
