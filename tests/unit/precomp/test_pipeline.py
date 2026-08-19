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

import meeting_minutes_agent.precomp.pipeline as pipeline_module
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
from meeting_minutes_agent.precomp.pipeline import (
    InvalidTurnSourcesError,
    cut_slice_plans_parallel,
    run_meeting,
    vad_slice_plan_manifest_path,
    write_vad_slice_plan_manifest,
)

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
        assert receipt["slice_plans"] == {"tool": None, "oracle": None, "vad": None}
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


# ---------------------------------------------------------------------------
# run_meeting: the VAD turn source (the G1 Z-nodiar-ablation PRECOMP
# supplement, docs/readiness/2026-08-19-g1-floors-preregistration.md SS3)
# ---------------------------------------------------------------------------


def _vad_slice_dir(tmp_path: Path, meeting_id: str) -> Path:
    return tmp_path / "derived" / "slices" / "vad" / meeting_id


def _vad_manifest_dir(tmp_path: Path) -> Path:
    return tmp_path / "derived" / "slices" / "vad-manifest"


class TestRunMeetingVadSource:
    def test_vad_only_skips_diar_and_oracle_entirely_and_populates_only_vad_blocks(self, tmp_path, monkeypatch):
        fx = _fixtures(tmp_path)
        budget = PrecompBudget(ceilings_for_wave(1))
        diar_calls: list = []

        def tracking_run_subprocess(args, *, timeout):
            diar_calls.append(args)
            return _rttm_writer()(args, timeout=timeout)

        def _resolve_meeting_must_not_be_called(corpus, meeting_id):
            raise AssertionError("resolve_meeting must never be called for a vad-only turn_sources request")

        monkeypatch.setattr(pipeline_module, "resolve_meeting", _resolve_meeting_must_not_be_called)

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=None,
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            vad_slice_dir=_vad_slice_dir(tmp_path, fx["meeting_id"]),
            vad_manifest_dir=_vad_manifest_dir(tmp_path),
            transport=fx["transport"],
            budget=budget,
            cache_dir=fx["cache_dir"],
            workers=2,
            turn_sources=("vad",),
            run_subprocess=tracking_run_subprocess,
        )

        assert receipt["ok"] is True
        assert receipt["error"] is None
        assert diar_calls == []  # the pinned diar tool was never contacted

        # diar untouched, at its failure/skip default
        assert receipt["diar"] == {"contact": None, "n_turns": None, "wall_seconds": None, "gpu_seconds_estimate": None}

        # tool/oracle stages never ran; vad populated
        assert receipt["slice_plans"]["tool"] is None
        assert receipt["slice_plans"]["oracle"] is None
        assert receipt["slice_plans"]["vad"]["n_slices"] >= 1
        assert receipt["cutting"]["tool"] is None
        assert receipt["cutting"]["oracle"] is None
        assert receipt["cutting"]["vad"]["n_entries"] == receipt["slice_plans"]["vad"]["n_slices"]
        assert receipt["encode_warm"]["tool"] == []
        assert receipt["encode_warm"]["oracle"] == []
        assert len(receipt["encode_warm"]["vad"]) == receipt["slice_plans"]["vad"]["n_slices"]
        assert receipt["encode_warm"]["n_calls"] == len(receipt["encode_warm"]["vad"])
        assert budget.encode_calls_used == len(receipt["encode_warm"]["vad"])
        assert budget.diar_gpu_seconds_used == 0.0  # never charged: the diar stage never ran

        # metrics: only what vad-only actually supports
        assert receipt["metrics"]["vad_slice_count"] == {"vad_slices": receipt["slice_plans"]["vad"]["n_slices"]}
        assert "turn_counts" not in receipt["metrics"]
        assert "slice_counts" not in receipt["metrics"]
        assert "boundary_displacement" not in receipt["metrics"]
        assert "cache" in receipt["metrics"]
        assert "walls" in receipt["metrics"]

        # the G1 Z-nodiar gap this closes: a real, loadable SlicePlan
        # manifest, at the EXACT path probes/g1.py's loader expects.
        manifest_path = _vad_manifest_dir(tmp_path) / f"{fx['meeting_id']}.json"
        assert manifest_path.is_file()
        assert receipt["slice_plans"]["vad"]["manifest_path"] == str(manifest_path)
        manifest_document = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_document["meeting_id"] == fx["meeting_id"]
        assert manifest_document["mode"] == "vad"
        assert manifest_document["turn_provenance"] is None
        assert manifest_document["content_hash"] == receipt["slice_plans"]["vad"]["content_hash"]
        assert len(manifest_document["slices"]) == receipt["slice_plans"]["vad"]["n_slices"]

    def test_vad_only_succeeds_even_when_the_diar_ceiling_is_already_exhausted(self, tmp_path):
        # Proves the diar budget axis is never even CHECKED for a vad-only
        # call (module docstring): a ceiling that would refuse the very
        # first diar contact does not block a run that never attempts one.
        fx = _fixtures(tmp_path)
        budget = PrecompBudget(
            WaveCeilings(wave=1, max_diar_gpu_hours=0.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=100)
        )

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=None,
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            vad_slice_dir=_vad_slice_dir(tmp_path, fx["meeting_id"]),
            vad_manifest_dir=_vad_manifest_dir(tmp_path),
            transport=fx["transport"],
            budget=budget,
            cache_dir=fx["cache_dir"],
            turn_sources=("vad",),
        )

        assert receipt["ok"] is True

    def test_default_turn_sources_run_never_populates_a_vad_block(self, tmp_path):
        # Regression: the unchanged wave-1/2 default (turn_sources omitted)
        # carries a "vad" key (schema-versioning, module docstring) but it
        # stays null/empty -- never silently populated.
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
            workers=2,
            run_subprocess=_rttm_writer(),
        )

        assert receipt["ok"] is True
        assert receipt["slice_plans"]["vad"] is None
        assert receipt["cutting"]["vad"] is None
        assert receipt["encode_warm"]["vad"] == []
        assert "vad_slice_count" not in receipt["metrics"]

    def test_all_three_sources_together_populate_every_block(self, tmp_path):
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
            vad_slice_dir=_vad_slice_dir(tmp_path, fx["meeting_id"]),
            vad_manifest_dir=_vad_manifest_dir(tmp_path),
            transport=fx["transport"],
            budget=budget,
            cache_dir=fx["cache_dir"],
            workers=2,
            turn_sources=("tool", "oracle", "vad"),
            run_subprocess=_rttm_writer(),
        )

        assert receipt["ok"] is True
        for source in ("tool", "oracle", "vad"):
            assert receipt["slice_plans"][source] is not None
            assert receipt["cutting"][source] is not None
            assert len(receipt["encode_warm"][source]) == receipt["slice_plans"][source]["n_slices"]
        for key in ("turn_counts", "slice_counts", "boundary_displacement", "vad_slice_count", "cache", "walls"):
            assert key in receipt["metrics"]

    def test_vad_failure_is_isolated_like_every_other_stage(self, tmp_path):
        fx = _fixtures(tmp_path)

        def boom(plan, audio_path, out_dir):
            raise RuntimeError("vad cutting exploded")

        receipt = run_meeting(
            fx["meeting_id"],
            wave=1,
            audio_path=fx["audio_path"],
            tool_config=None,
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            vad_slice_dir=_vad_slice_dir(tmp_path, fx["meeting_id"]),
            vad_manifest_dir=_vad_manifest_dir(tmp_path),
            transport=fx["transport"],
            budget=PrecompBudget(ceilings_for_wave(1)),
            cache_dir=fx["cache_dir"],
            turn_sources=("vad",),
            materialize_fn=boom,
        )

        assert receipt["ok"] is False
        assert "vad cutting exploded" in receipt["error"]
        assert receipt["slice_plans"]["vad"] is not None  # plan built before cutting failed
        assert receipt["cutting"]["vad"] is None  # cutting itself never completed
        # the manifest is written BEFORE cutting (module docstring: it
        # depends only on the plan, never on cutting succeeding) -- proves
        # a real flight still gets a loadable Z-nodiar manifest for a
        # meeting whose cutting stage later fails.
        manifest_path = _vad_manifest_dir(tmp_path) / f"{fx['meeting_id']}.json"
        assert manifest_path.is_file()


# ---------------------------------------------------------------------------
# run_meeting: turn_sources validation (fail-closed)
# ---------------------------------------------------------------------------


class TestRunMeetingTurnSourceValidation:
    def _base_kwargs(self, fx: dict, tmp_path: Path) -> dict:
        return dict(
            wave=1,
            audio_path=fx["audio_path"],
            nxt_corpus=fx["nxt_corpus"],
            rttm_dir=fx["rttm_dir"],
            tool_slice_dir=fx["tool_slice_dir"],
            oracle_slice_dir=fx["oracle_slice_dir"],
            transport=fx["transport"],
            budget=PrecompBudget(ceilings_for_wave(1)),
            cache_dir=fx["cache_dir"],
        )

    def test_unknown_turn_source_raises(self, tmp_path):
        fx = _fixtures(tmp_path)
        with pytest.raises(InvalidTurnSourcesError):
            run_meeting(fx["meeting_id"], tool_config=None, turn_sources=("bogus",), **self._base_kwargs(fx, tmp_path))

    def test_empty_turn_sources_raises(self, tmp_path):
        fx = _fixtures(tmp_path)
        with pytest.raises(InvalidTurnSourcesError):
            run_meeting(fx["meeting_id"], tool_config=None, turn_sources=(), **self._base_kwargs(fx, tmp_path))

    def test_vad_requested_without_vad_slice_dir_raises(self, tmp_path):
        fx = _fixtures(tmp_path)
        with pytest.raises(InvalidTurnSourcesError):
            run_meeting(fx["meeting_id"], tool_config=None, turn_sources=("vad",), **self._base_kwargs(fx, tmp_path))

    def test_vad_requested_without_vad_manifest_dir_raises(self, tmp_path):
        # vad_slice_dir alone is not enough: the manifest directory is
        # required independently (module docstring), so a caller cannot
        # silently cut VAD slice WAVs without also persisting the manifest
        # G1's Z-nodiar arm needs.
        fx = _fixtures(tmp_path)
        with pytest.raises(InvalidTurnSourcesError):
            run_meeting(
                fx["meeting_id"],
                tool_config=None,
                turn_sources=("vad",),
                vad_slice_dir=_vad_slice_dir(tmp_path, fx["meeting_id"]),
                **self._base_kwargs(fx, tmp_path),
            )

    def test_tool_requested_without_tool_config_raises(self, tmp_path):
        fx = _fixtures(tmp_path)
        with pytest.raises(InvalidTurnSourcesError):
            run_meeting(
                fx["meeting_id"], tool_config=None, turn_sources=("tool", "oracle"), **self._base_kwargs(fx, tmp_path)
            )


# ---------------------------------------------------------------------------
# vad_slice_plan_manifest_path / write_vad_slice_plan_manifest: the pure
# helpers closing the G1 Z-nodiar gap, exercised directly (no full
# run_meeting needed) -- and round-tripped through the REAL consumer,
# meeting_minutes_agent.probes.g1.load_vad_slice_plan, proving the two,
# concurrently-developed modules actually agree on the manifest shape/path
# convention rather than each side's own isolated tests merely assuming it.
# ---------------------------------------------------------------------------


class TestVadSlicePlanManifestHelpers:
    def test_manifest_path_is_meeting_id_json_under_the_given_dir(self, tmp_path):
        path = vad_slice_plan_manifest_path(tmp_path / "vad-manifests", "MTG1")
        assert path == tmp_path / "vad-manifests" / "MTG1.json"

    def test_write_persists_the_to_dict_shape_fsynced(self, tmp_path):
        from meeting_minutes_agent.chunking.slicer import build_vad_slice_plan

        plan = build_vad_slice_plan("MTG9", 200.0)
        manifest_dir = tmp_path / "vad-manifests"

        written_path = write_vad_slice_plan_manifest(manifest_dir, plan)

        assert written_path == manifest_dir / "MTG9.json"
        assert written_path.is_file()
        document = json.loads(written_path.read_text(encoding="utf-8"))
        assert document == plan.to_dict()

    def test_written_manifest_loads_end_to_end_via_the_g1_loader(self, tmp_path):
        # The actual gap this mission closes: a manifest THIS module wrote
        # is readable, unchanged, by probes/g1.py's own fail-closed loader
        # -- the two modules agree on the shape without either importing
        # the other's test fixtures.
        from meeting_minutes_agent.chunking.slicer import build_vad_slice_plan
        from meeting_minutes_agent.probes import g1

        plan = build_vad_slice_plan("MTG7", 150.0, pause_transitions=(30.0, 60.0))
        manifest_dir = tmp_path / "vad-manifests"
        write_vad_slice_plan_manifest(manifest_dir, plan)

        loaded = g1.load_vad_slice_plan(vad_slice_plan_manifest_path(manifest_dir, "MTG7"))

        assert loaded.meeting_id == plan.meeting_id
        assert loaded.mode == plan.mode
        assert loaded.turn_provenance is None
        assert loaded.content_hash == plan.content_hash
        assert len(loaded.slices) == len(plan.slices)
