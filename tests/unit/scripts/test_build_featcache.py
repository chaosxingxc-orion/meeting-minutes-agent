"""Tests for ``scripts/build_featcache.py``: the standalone cold-cache
generator a collaborator runs over THEIR OWN audio, with none of this
repository's diarization/manifest/budget machinery.

Every transport call goes through a FAKE ``post`` callable
(:class:`~meeting_minutes_agent.client.transport.LlamaServerTransport`'s own
injection seam) -- zero network, zero model contact, mirroring every other
test file in this repository (e.g. ``tests/unit/precomp/test_encode_warm.py``,
whose discard-unread-proof pattern this file reuses).

The fake ``post`` used below additionally SIMULATES the llama.cpp featcache
patch's own miss-path disk back-fill: the first time it sees a given
request body (which varies only by the audio bytes it carries, since this
script always sends the same one-token-capped transcribe-only template) it
writes a new ``.feat``-suffixed file into a shared ``cache_dir``; every
later contact carrying the SAME body writes nothing more. That is exactly
the content-addressed behaviour the real patch's FNV bitmap-content-id key
gives it (``third_party/llama.cpp-featcache/COLD-CACHE.md``), so it is
enough to exercise this script's own before/after entry-count delta logic
without a real patched server."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import build_featcache as tool
import numpy as np
import pytest
import soundfile as sf

from meeting_minutes_agent.chunking.constants import TRANSPORT_SLICE_MAX_S
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig

_SECRET_MARKER = "SECRET-GENERATED-TEXT-MARKER-0xDEADBEEF"


def _canned_response(text: str = _SECRET_MARKER) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 1, "total_tokens": 41},
        }
    ).encode("utf-8")


def _write_wav(path: Path, seconds: float = 2.0, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.zeros(int(seconds * sr), dtype=np.float32)
    sf.write(str(path), samples, sr, subtype="PCM_16")


def _transport(post, *, max_calls: int = 100, max_audio_seconds: float = 10_000.0, max_retries: int = 1) -> LlamaServerTransport:
    budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    return LlamaServerTransport(
        TransportConfig(base_url="http://x", max_retries=max_retries), budget, post=post
    )


def _cache_backfilling_post(cache_dir: Path, *, seen: set | None = None):
    """A fake ``post`` that mimics the patch's miss-path back-fill (module
    docstring): first sight of a request body writes a ``.feat`` file into
    ``cache_dir``; a repeat of the same body writes nothing further."""

    seen = seen if seen is not None else set()
    cache_dir.mkdir(parents=True, exist_ok=True)

    def post(url: str, body: bytes) -> bytes:
        key = hashlib.sha256(body).hexdigest()[:16]
        if key not in seen:
            seen.add(key)
            (cache_dir / f"{key}.feat").write_bytes(b"\x00" * 8)
        return _canned_response()

    return post


# ---------------------------------------------------------------------------
# import-verification
# ---------------------------------------------------------------------------


def test_module_imports_cleanly_without_side_effects():
    for name in ("main", "run_build", "build_transport", "discover_audio_files", "resolve_slices_from_manifest"):
        assert hasattr(tool, name)


def test_help_exits_zero():
    with pytest.raises(SystemExit) as excinfo:
        tool.main(["--help"])
    assert excinfo.value.code == 0


def test_missing_server_url_is_rejected_by_argparse(tmp_path):
    _write_wav(tmp_path / "s0.wav")
    with pytest.raises(SystemExit):
        tool.main(["--audio-dir", str(tmp_path)])


# ---------------------------------------------------------------------------
# discover_audio_files / resolve_slices_from_directory
# ---------------------------------------------------------------------------


class TestDiscoverAudioFiles:
    def test_finds_and_sorts_by_name(self, tmp_path):
        _write_wav(tmp_path / "b.wav")
        _write_wav(tmp_path / "a.wav")
        _write_wav(tmp_path / "c.flac")
        files = tool.discover_audio_files(tmp_path)
        assert [f.name for f in files] == ["a.wav", "b.wav", "c.flac"]

    def test_ignores_non_audio_files(self, tmp_path):
        _write_wav(tmp_path / "a.wav")
        (tmp_path / "notes.txt").write_text("not audio")
        files = tool.discover_audio_files(tmp_path)
        assert [f.name for f in files] == ["a.wav"]

    def test_nonexistent_directory_raises(self, tmp_path):
        with pytest.raises(tool.BuildFeatCacheError):
            tool.discover_audio_files(tmp_path / "missing")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(tool.BuildFeatCacheError):
            tool.discover_audio_files(tmp_path)


class TestResolveSlicesFromDirectory:
    def test_measures_real_duration_from_the_wav_header(self, tmp_path):
        _write_wav(tmp_path / "s0.wav", seconds=2.0)
        slices = tool.resolve_slices_from_directory(tmp_path)
        assert len(slices) == 1
        assert slices[0].audio_seconds == pytest.approx(2.0, abs=0.01)
        assert slices[0].audio_seconds_source == "measured"
        assert slices[0].index == 0

    def test_assigns_index_in_sorted_order(self, tmp_path):
        _write_wav(tmp_path / "b.wav")
        _write_wav(tmp_path / "a.wav")
        slices = tool.resolve_slices_from_directory(tmp_path)
        assert [s.index for s in slices] == [0, 1]
        assert slices[0].path.name == "a.wav"

    def test_falls_back_to_assumed_duration_for_an_unreadable_file(self, tmp_path):
        bogus = tmp_path / "bad.wav"
        bogus.write_bytes(b"not a real wav file")
        slices = tool.resolve_slices_from_directory(tmp_path, fallback_seconds=17.0)
        assert slices[0].audio_seconds == 17.0
        assert slices[0].audio_seconds_source == "assumed"


# ---------------------------------------------------------------------------
# resolve_slices_from_manifest
# ---------------------------------------------------------------------------


class TestResolveSlicesFromManifest:
    def test_generic_list_shape_with_explicit_audio_seconds(self, tmp_path):
        _write_wav(tmp_path / "s0.wav")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps([{"path": "s0.wav", "audio_seconds": 12.5}]), encoding="utf-8")
        slices = tool.resolve_slices_from_manifest(manifest)
        assert slices[0].audio_seconds == 12.5
        assert slices[0].audio_seconds_source == "manifest"
        assert slices[0].path == tmp_path / "s0.wav"

    def test_entries_object_shape_is_accepted(self, tmp_path):
        _write_wav(tmp_path / "s0.wav")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"meeting_id": "MTG", "entries": [{"path": "s0.wav", "audio_seconds": 1.0}]}),
            encoding="utf-8",
        )
        slices = tool.resolve_slices_from_manifest(manifest)
        assert len(slices) == 1

    def test_slice_manifest_filename_start_end_shape(self, tmp_path):
        audio_dir = tmp_path / "slices"
        _write_wav(audio_dir / "MTG-slice0000.wav")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps([{"filename": "MTG-slice0000.wav", "start": 0.0, "end": 90.0}]), encoding="utf-8"
        )
        slices = tool.resolve_slices_from_manifest(manifest, base_dir=audio_dir)
        assert slices[0].audio_seconds == 90.0
        assert slices[0].audio_seconds_source == "manifest"
        assert slices[0].path == audio_dir / "MTG-slice0000.wav"

    def test_base_dir_defaults_to_the_manifest_files_own_directory(self, tmp_path):
        _write_wav(tmp_path / "s0.wav")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps([{"path": "s0.wav", "audio_seconds": 1.0}]), encoding="utf-8")
        slices = tool.resolve_slices_from_manifest(manifest)
        assert slices[0].path == tmp_path / "s0.wav"

    def test_explicit_index_is_honoured(self, tmp_path):
        _write_wav(tmp_path / "s0.wav")
        _write_wav(tmp_path / "s1.wav")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                [
                    {"path": "s1.wav", "audio_seconds": 1.0, "index": 7},
                    {"path": "s0.wav", "audio_seconds": 1.0, "index": 3},
                ]
            ),
            encoding="utf-8",
        )
        slices = tool.resolve_slices_from_manifest(manifest)
        assert [s.index for s in slices] == [7, 3]

    def test_missing_audio_seconds_and_start_end_probes_the_real_file(self, tmp_path):
        _write_wav(tmp_path / "s0.wav", seconds=3.0)
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps([{"path": "s0.wav"}]), encoding="utf-8")
        slices = tool.resolve_slices_from_manifest(manifest)
        assert slices[0].audio_seconds == pytest.approx(3.0, abs=0.01)
        assert slices[0].audio_seconds_source == "measured"

    def test_entry_without_path_or_filename_raises(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps([{"audio_seconds": 1.0}]), encoding="utf-8")
        with pytest.raises(tool.BuildFeatCacheError):
            tool.resolve_slices_from_manifest(manifest)

    def test_non_object_entry_raises(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
        with pytest.raises(tool.BuildFeatCacheError):
            tool.resolve_slices_from_manifest(manifest)

    def test_empty_manifest_raises(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps([]), encoding="utf-8")
        with pytest.raises(tool.BuildFeatCacheError):
            tool.resolve_slices_from_manifest(manifest)

    def test_unrecognised_top_level_shape_raises(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps("just a string"), encoding="utf-8")
        with pytest.raises(tool.BuildFeatCacheError):
            tool.resolve_slices_from_manifest(manifest)


# ---------------------------------------------------------------------------
# count_cache_entries
# ---------------------------------------------------------------------------


class TestCountCacheEntries:
    def test_none_cache_dir_is_unobservable(self):
        assert tool.count_cache_entries(None) is None

    def test_missing_directory_reads_as_zero(self, tmp_path):
        assert tool.count_cache_entries(tmp_path / "does-not-exist-yet") == 0

    def test_counts_only_feat_files(self, tmp_path):
        (tmp_path / "a.feat").write_bytes(b"")
        (tmp_path / "b.feat").write_bytes(b"")
        (tmp_path / "ignore.tmp").write_bytes(b"")
        (tmp_path / "ignore.txt").write_bytes(b"")
        assert tool.count_cache_entries(tmp_path) == 2


# ---------------------------------------------------------------------------
# run_build
# ---------------------------------------------------------------------------


def _slices(paths: list[Path]) -> list[tool.SliceInput]:
    return [tool.SliceInput(index=i, path=p, audio_seconds=1.0, audio_seconds_source="manifest") for i, p in enumerate(paths)]


class TestRunBuildDispatch:
    def test_dispatches_one_request_per_slice_in_index_order(self, tmp_path):
        paths = [tmp_path / f"s{i}.wav" for i in range(3)]
        for p in paths:
            _write_wav(p)
        seen_ids = []

        def post(url, body):
            return _canned_response()

        transport = _transport(post)
        summary = tool.run_build(transport, _slices(paths), cache_dir=None, request_id_prefix="pfx")
        assert [s["request_id"] for s in summary["slices"]] == [f"pfx-slice{i:04d}" for i in range(3)]

    def test_never_leaks_reply_text_anywhere_in_the_summary(self, tmp_path):
        paths = [tmp_path / "s0.wav"]
        _write_wav(paths[0])
        transport = _transport(lambda url, body: _canned_response())
        summary = tool.run_build(transport, _slices(paths), cache_dir=None, request_id_prefix="pfx")
        assert _SECRET_MARKER not in json.dumps(summary)
        assert "text" not in summary["slices"][0]


class TestRunBuildCacheObservation:
    def test_cache_dir_none_reports_unknown_status(self, tmp_path):
        paths = [tmp_path / "s0.wav"]
        _write_wav(paths[0])
        transport = _transport(lambda url, body: _canned_response())
        summary = tool.run_build(transport, _slices(paths), cache_dir=None, request_id_prefix="pfx")
        assert summary["slices"][0]["outcome_kind"] == "unknown"
        assert summary["entries_added_total"] is None

    def test_first_run_over_distinct_slices_reports_encoded_and_grows_the_cache(self, tmp_path):
        cache_dir = tmp_path / "cache"
        paths = [tmp_path / "s0.wav", tmp_path / "s1.wav"]
        _write_wav(paths[0], seconds=1.0)
        _write_wav(paths[1], seconds=2.0)  # distinct content -> distinct simulated body -> distinct key
        transport = _transport(_cache_backfilling_post(cache_dir))

        summary = tool.run_build(transport, _slices(paths), cache_dir=cache_dir, request_id_prefix="pfx")

        assert summary["entries_before"] == 0
        assert summary["entries_after"] == 2
        assert summary["entries_added_total"] == 2
        assert summary["n_encoded"] == 2
        assert all(s["outcome_kind"] == "encoded" for s in summary["slices"])

    def test_rerun_over_the_same_slices_is_idempotent(self, tmp_path):
        cache_dir = tmp_path / "cache"
        paths = [tmp_path / "s0.wav", tmp_path / "s1.wav"]
        _write_wav(paths[0], seconds=1.0)
        _write_wav(paths[1], seconds=2.0)
        seen: set = set()

        first = tool.run_build(
            _transport(_cache_backfilling_post(cache_dir, seen=seen)), _slices(paths), cache_dir=cache_dir, request_id_prefix="pfx"
        )
        assert first["n_encoded"] == 2

        second = tool.run_build(
            _transport(_cache_backfilling_post(cache_dir, seen=seen)), _slices(paths), cache_dir=cache_dir, request_id_prefix="pfx"
        )

        assert second["entries_before"] == 2
        assert second["entries_after"] == 2
        assert second["entries_added_total"] == 0
        assert second["n_already_cached"] == 2
        assert all(s["outcome_kind"] == "already_cached" for s in second["slices"])


class TestRunBuildFailureHandling:
    def test_an_oversized_slice_is_recorded_as_an_error_and_the_run_continues(self, tmp_path):
        good = tmp_path / "s0.wav"
        _write_wav(good)
        slices = [
            tool.SliceInput(index=0, path=good, audio_seconds=1.0, audio_seconds_source="manifest"),
            tool.SliceInput(
                index=1, path=good, audio_seconds=TRANSPORT_SLICE_MAX_S + 1.0, audio_seconds_source="manifest"
            ),
            tool.SliceInput(index=2, path=good, audio_seconds=1.0, audio_seconds_source="manifest"),
        ]
        transport = _transport(lambda url, body: _canned_response())

        summary = tool.run_build(transport, slices, cache_dir=None, request_id_prefix="pfx")

        assert summary["n_error"] == 1
        assert summary["slices"][1]["outcome_kind"] == "error"
        assert "status" in summary["slices"][1]
        # the run must not have stopped: slice 2 still got its own outcome
        assert len(summary["slices"]) == 3
        assert summary["slices"][2]["outcome_kind"] == "unknown"

    def test_a_missing_audio_file_is_recorded_as_an_error(self, tmp_path):
        missing = tmp_path / "does-not-exist.wav"
        slices = [tool.SliceInput(index=0, path=missing, audio_seconds=1.0, audio_seconds_source="manifest")]
        transport = _transport(lambda url, body: _canned_response())

        summary = tool.run_build(transport, slices, cache_dir=None, request_id_prefix="pfx")

        assert summary["n_error"] == 1
        assert summary["slices"][0]["outcome_kind"] == "error"

    def test_budget_exhaustion_stops_the_run_and_reports_partial_results(self, tmp_path):
        paths = [tmp_path / f"s{i}.wav" for i in range(3)]
        for p in paths:
            _write_wav(p)
        transport = _transport(lambda url, body: _canned_response(), max_calls=2)

        summary = tool.run_build(transport, _slices(paths), cache_dir=None, request_id_prefix="pfx")

        assert summary["stopped_reason"] is not None
        assert len(summary["slices"]) == 3
        assert summary["slices"][2]["outcome_kind"] == "stopped"
        assert summary["slices"][0]["outcome_kind"] == "unknown"
        assert summary["slices"][1]["outcome_kind"] == "unknown"


# ---------------------------------------------------------------------------
# _resolve_cache_dir / _resolve_slices (argparse-level wiring)
# ---------------------------------------------------------------------------


class TestResolveCacheDir:
    def _args(self, **overrides):
        defaults = {"cache_dir": None, "dataset": None, "encoder": None, "featcache_root": None}
        defaults.update(overrides)
        return argparse_namespace(**defaults)

    def test_explicit_cache_dir_wins(self, tmp_path):
        args = self._args(cache_dir=str(tmp_path / "explicit"), dataset="ds", encoder="enc", featcache_root=str(tmp_path))
        assert tool._resolve_cache_dir(args) == tmp_path / "explicit"

    def test_dataset_and_encoder_resolve_via_campaign_cache_dir(self, tmp_path):
        args = self._args(dataset="ds", encoder="enc", featcache_root=str(tmp_path))
        assert tool._resolve_cache_dir(args) == tmp_path / "ds-enc"

    def test_dataset_without_encoder_raises(self):
        args = self._args(dataset="ds")
        with pytest.raises(tool.BuildFeatCacheError):
            tool._resolve_cache_dir(args)

    def test_neither_given_returns_none(self):
        args = self._args()
        assert tool._resolve_cache_dir(args) is None


class TestResolveSlices:
    def test_neither_audio_dir_nor_manifest_raises(self):
        args = argparse_namespace(audio_dir=None, manifest=None, base_dir=None, fallback_audio_seconds=30.0)
        with pytest.raises(tool.BuildFeatCacheError):
            tool._resolve_slices(args)

    def test_both_audio_dir_and_manifest_raises(self, tmp_path):
        args = argparse_namespace(
            audio_dir=str(tmp_path), manifest=str(tmp_path / "m.json"), base_dir=None, fallback_audio_seconds=30.0
        )
        with pytest.raises(tool.BuildFeatCacheError):
            tool._resolve_slices(args)


def argparse_namespace(**kwargs):
    import argparse

    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# main(): CLI wiring end to end, transport injected via monkeypatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_directory_mode_end_to_end_with_cache_dir(self, tmp_path, monkeypatch, capsys):
        audio_dir = tmp_path / "slices"
        _write_wav(audio_dir / "s0.wav", seconds=1.0)
        _write_wav(audio_dir / "s1.wav", seconds=2.0)  # distinct content from s0 -> distinct simulated key
        cache_dir = tmp_path / "cache"

        fake_transport = _transport(_cache_backfilling_post(cache_dir))
        monkeypatch.setattr(tool, "build_transport", lambda **kwargs: fake_transport)

        rc = tool.main(
            ["--audio-dir", str(audio_dir), "--server-url", "http://x", "--cache-dir", str(cache_dir), "--quiet"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["n_slices"] == 2
        assert payload["n_encoded"] == 2
        assert _SECRET_MARKER not in out

    def test_out_json_is_written(self, tmp_path, monkeypatch):
        audio_dir = tmp_path / "slices"
        _write_wav(audio_dir / "s0.wav")
        fake_transport = _transport(lambda url, body: _canned_response())
        monkeypatch.setattr(tool, "build_transport", lambda **kwargs: fake_transport)
        out_json = tmp_path / "summary.json"

        rc = tool.main(
            [
                "--audio-dir", str(audio_dir),
                "--server-url", "http://x",
                "--out-json", str(out_json),
                "--quiet",
            ]
        )
        assert rc == 0
        assert out_json.is_file()
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        assert payload["n_slices"] == 1

    def test_dataset_without_encoder_raises(self, tmp_path, monkeypatch):
        audio_dir = tmp_path / "slices"
        _write_wav(audio_dir / "s0.wav")
        monkeypatch.setattr(tool, "build_transport", lambda **kwargs: _transport(lambda url, body: _canned_response()))
        with pytest.raises(tool.BuildFeatCacheError):
            tool.main(["--audio-dir", str(audio_dir), "--server-url", "http://x", "--dataset", "ds"])

    def test_audio_dir_and_manifest_together_raises(self, tmp_path):
        with pytest.raises(tool.BuildFeatCacheError):
            tool.main(
                ["--audio-dir", str(tmp_path), "--manifest", str(tmp_path / "m.json"), "--server-url", "http://x"]
            )
