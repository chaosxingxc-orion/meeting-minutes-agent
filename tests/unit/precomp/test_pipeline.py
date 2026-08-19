"""Tests for :mod:`meeting_minutes_agent.precomp.pipeline`: the CPU
slice-cutting worker pool, and the whole per-meeting pipeline
(:func:`run_meeting`) exercised end to end on tiny synthetic fixtures --
real audio (via ``soundfile``/``librosa``, same as
``tests/unit/chunking/test_slicer.py``), a real (but hand-built, minimal)
NXT annotation tree, a FAKE diar subprocess, and a FAKE transport ``post``.
Zero real tool binary, zero real GPU, zero real network/model contact,
mirroring every other test file in this repository."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from meeting_minutes_agent.chunking.diarization import ToolDiarizationConfig
from meeting_minutes_agent.chunking.rttm import write_rttm_text
from meeting_minutes_agent.chunking.slicer import (
    SliceManifest,
    TurnSpan,
    build_vad_slice_plan,
)
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.precomp.budget import PrecompBudget, PrecompBudgetExceeded, WaveCeilings, ceilings_for_wave
from meeting_minutes_agent.precomp.pipeline import cut_slice_plans_parallel, run_meeting

_SECRET_MARKER = "SECRET-GENERATED-TEXT-MARKER-0xDEADBEEF"
_NITE_XMLNS = 'xmlns:nite="http://nite.sourceforge.net/"'
_XML_HEADER = '<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>\n'


# ---------------------------------------------------------------------------
# cut_slice_plans_parallel: pure worker-pool dispatch, fake materialize_fn
# ---------------------------------------------------------------------------


def _fake_manifest(meeting_id: str) -> SliceManifest:
    return SliceManifest(
        meeting_id=meeting_id, mode="vad", turn_provenance=None, sample_rate=16000, channels=1, entries=(), content_hash="h"
    )


class TestCutSlicePlansParallel:
    def test_dispatches_every_job_and_preserves_keys(self):
        calls: list[str] = []

        def fake_materialize(plan, audio_path, out_dir):
            calls.append(plan.meeting_id)
            return _fake_manifest(plan.meeting_id)

        plan_a = build_vad_slice_plan("m-tool", 100.0)
        plan_b = build_vad_slice_plan("m-oracle", 50.0)
        results = cut_slice_plans_parallel(
            {"tool": (plan_a, Path("a.wav"), Path("outA")), "oracle": (plan_b, Path("b.wav"), Path("outB"))},
            workers=2,
            materialize_fn=fake_materialize,
        )
        assert set(results) == {"tool", "oracle"}
        assert results["tool"].meeting_id == "m-tool"
        assert results["oracle"].meeting_id == "m-oracle"
        assert sorted(calls) == ["m-oracle", "m-tool"]

    def test_rejects_a_non_positive_worker_count(self):
        with pytest.raises(ValueError):
            cut_slice_plans_parallel({}, workers=0)

    def test_propagates_a_worker_exception(self):
        def boom(plan, audio_path, out_dir):
            raise RuntimeError("cutting exploded")

        plan = build_vad_slice_plan("m1", 100.0)
        with pytest.raises(RuntimeError, match="cutting exploded"):
            cut_slice_plans_parallel({"x": (plan, Path("a"), Path("b"))}, workers=1, materialize_fn=boom)

    def test_empty_jobs_returns_empty_dict(self):
        assert cut_slice_plans_parallel({}, workers=4) == {}


# ---------------------------------------------------------------------------
# run_meeting: end-to-end synthetic fixtures
# ---------------------------------------------------------------------------


def _write_nxt(root: Path, meeting_id: str) -> Path:
    """A minimal, hand-built NXT annotation tree for ONE meeting, two
    speakers, words+segments layers only (the layers
    :func:`~meeting_minutes_agent.chunking.adapters.turn_table_from_resolved_meeting`
    actually needs -- no topics/dialogue-acts/abstractive, unlike
    ``tests/unit/nxt/fixtures.py::build_tiny_corpus``'s fuller MEET1, which
    this deliberately does not import, to keep this test file
    self-contained across the ``tests/unit/precomp`` <-> ``tests/unit/nxt``
    directory boundary)."""

    def write(subdir: str, name: str, content: str) -> None:
        path = root / subdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_XML_HEADER + content, encoding="utf-8")

    write(
        "words",
        f"{meeting_id}.A.words.xml",
        f"""<nite:root nite:id="{meeting_id}.A.words" {_NITE_XMLNS}>
   <w nite:id="{meeting_id}.A.words0" starttime="0.0" endtime="1.8">Hello</w>
</nite:root>
""",
    )
    write(
        "segments",
        f"{meeting_id}.A.segments.xml",
        f"""<nite:root nite:id="{meeting_id}.A.segs" {_NITE_XMLNS}>
   <segment nite:id="{meeting_id}.A.seg.1" channel="0" transcriber_start="0.0" transcriber_end="1.8">
      <nite:child href="{meeting_id}.A.words.xml#id({meeting_id}.A.words0)..id({meeting_id}.A.words0)"/>
   </segment>
</nite:root>
""",
    )
    write(
        "words",
        f"{meeting_id}.B.words.xml",
        f"""<nite:root nite:id="{meeting_id}.B.words" {_NITE_XMLNS}>
   <w nite:id="{meeting_id}.B.words0" starttime="2.0" endtime="3.8">Thanks</w>
</nite:root>
""",
    )
    write(
        "segments",
        f"{meeting_id}.B.segments.xml",
        f"""<nite:root nite:id="{meeting_id}.B.segs" {_NITE_XMLNS}>
   <segment nite:id="{meeting_id}.B.seg.1" channel="1" transcriber_start="2.0" transcriber_end="3.8">
      <nite:child href="{meeting_id}.B.words.xml#id({meeting_id}.B.words0)..id({meeting_id}.B.words0)"/>
   </segment>
</nite:root>
""",
    )
    return root


def _write_synth_wav(path: Path, duration_s: float, *, sr: int = 16000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(duration_s * sr))
    t = np.arange(n) / sr
    y = 0.2 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    sf.write(str(path), y, sr, subtype="PCM_16")
    return path


def _tool_config() -> ToolDiarizationConfig:
    return ToolDiarizationConfig(
        tool_name="fake-nemo-speech-b",
        tool_version="1.0",
        checkpoint_sha256="b" * 64,
        command_template=("fake-diar", "{audio_path}", "--output", "{rttm_path}"),
    )


def _rttm_writer(turns=(TurnSpan(0.0, 1.8, "spk1"), TurnSpan(2.0, 3.8, "spk2"))):
    def run(args, *, timeout):
        (rttm_path,) = [a for a in args if a.endswith(".rttm")]
        Path(rttm_path).write_text(write_rttm_text(turns, file_id="MTG"), encoding="utf-8")

        class _Completed:
            returncode = 0
            stderr = ""

        return _Completed()

    return run


def _failing_run_subprocess(calls: list):
    def run(args, *, timeout):
        calls.append(args)

        class _Completed:
            returncode = 1
            stderr = "diar tool exploded"

        return _Completed()

    return run


def _canned_post(text: str = _SECRET_MARKER):
    def post(url, body):
        return json.dumps(
            {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}
        ).encode("utf-8")

    return post


def _fixtures(tmp_path: Path, meeting_id: str = "PMEET1"):
    ami_root = tmp_path / "ami"
    _write_nxt(ami_root, meeting_id)
    audio_path = _write_synth_wav(tmp_path / "audio" / f"{meeting_id}.wav", 4.5)
    nxt_corpus = NxtCorpus(ami_root)
    call_budget = CallBudget(BudgetLimits(max_calls=100, max_audio_seconds=10_000.0))
    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), call_budget, post=_canned_post())
    derived = tmp_path / "derived"
    cache_dir = tmp_path / "cache"
    return {
        "meeting_id": meeting_id,
        "audio_path": audio_path,
        "nxt_corpus": nxt_corpus,
        "transport": transport,
        "rttm_dir": derived / "rttm",
        "tool_slice_dir": derived / "slices" / "tool" / meeting_id,
        "oracle_slice_dir": derived / "slices" / "oracle" / meeting_id,
        "cache_dir": cache_dir,
    }


class TestRunMeetingSuccess:
    def test_ok_receipt_with_every_block_populated(self, tmp_path):
        fx = _fixtures(tmp_path)
        budget = PrecompBudget(ceilings_for_wave(1))

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=_tool_config(),
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            transport=fx["transport"],
            budget=budget,
            cache_dir=fx["cache_dir"],
            workers=2,
            run_subprocess=_rttm_writer(),
            query_gpu=None,
        )

        assert receipt["ok"] is True
        assert receipt["error"] is None
        assert receipt["diar"]["n_turns"] == 2
        assert receipt["diar"]["contact"]["return_code"] == 0
        assert receipt["slice_plans"]["tool"]["n_slices"] >= 1
        assert receipt["slice_plans"]["oracle"]["n_slices"] >= 1
        assert receipt["cutting"]["tool"]["n_entries"] == receipt["slice_plans"]["tool"]["n_slices"]
        assert receipt["cutting"]["oracle"]["n_entries"] == receipt["slice_plans"]["oracle"]["n_slices"]
        expected_calls = receipt["slice_plans"]["tool"]["n_slices"] + receipt["slice_plans"]["oracle"]["n_slices"]
        assert receipt["encode_warm"]["n_calls"] == expected_calls
        assert budget.encode_calls_used == expected_calls
        assert receipt["metrics"]["turn_counts"] == {"tool_turns": 2, "oracle_turns": 2}

    def test_encode_warm_outcomes_never_carry_the_reply_text(self, tmp_path):
        fx = _fixtures(tmp_path)
        budget = PrecompBudget(ceilings_for_wave(1))

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=_tool_config(),
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            transport=fx["transport"],
            budget=budget,
            cache_dir=fx["cache_dir"],
            workers=2,
            run_subprocess=_rttm_writer(),
        )

        for outcome in [*receipt["encode_warm"]["tool"], *receipt["encode_warm"]["oracle"]]:
            assert outcome["text_discarded_unread"] is True
            assert "text" not in outcome
        assert _SECRET_MARKER not in json.dumps(receipt)

    def test_receipt_is_json_serializable(self, tmp_path):
        fx = _fixtures(tmp_path)
        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=_tool_config(),
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            transport=fx["transport"],
            budget=PrecompBudget(ceilings_for_wave(1)),
            cache_dir=fx["cache_dir"],
            workers=1,
            run_subprocess=_rttm_writer(),
        )
        json.dumps(receipt)  # must not raise


class TestRunMeetingFailureIsolation:
    def test_diar_tool_failure_is_recorded_not_raised(self, tmp_path):
        fx = _fixtures(tmp_path)
        calls: list = []

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=_tool_config(),
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            transport=fx["transport"],
            budget=PrecompBudget(ceilings_for_wave(1)),
            cache_dir=fx["cache_dir"],
            run_subprocess=_failing_run_subprocess(calls),
        )

        assert receipt["ok"] is False
        assert "ToolDiarizationInvocationError" in receipt["error"]
        assert receipt["diar"]["contact"]["return_code"] == 1
        assert receipt["diar"]["n_turns"] is None
        # nothing downstream of diar was reached
        assert receipt["slice_plans"] == {"tool": None, "oracle": None}
        assert receipt["encode_warm"]["n_calls"] == 0
        assert len(calls) == 1  # exactly one subprocess attempt, never retried silently


class TestRunMeetingBudgetGuard:
    def test_budget_exceeded_raises_before_any_diar_contact(self, tmp_path):
        fx = _fixtures(tmp_path)
        calls: list = []

        def tracking_run(args, *, timeout):
            calls.append(args)
            return _rttm_writer()(args, timeout=timeout)

        budget = PrecompBudget(
            WaveCeilings(wave=1, max_diar_gpu_hours=0.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=10)
        )

        with pytest.raises(PrecompBudgetExceeded):
            run_meeting(
                fx["meeting_id"],
                wave=1,
                audio_path=fx["audio_path"],
                tool_config=_tool_config(),
                nxt_corpus=fx["nxt_corpus"],
                rttm_dir=fx["rttm_dir"],
                tool_slice_dir=fx["tool_slice_dir"],
                oracle_slice_dir=fx["oracle_slice_dir"],
                transport=fx["transport"],
                budget=budget,
                cache_dir=fx["cache_dir"],
                run_subprocess=tracking_run,
            )
        assert calls == []
