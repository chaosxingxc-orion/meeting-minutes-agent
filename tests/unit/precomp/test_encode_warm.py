"""Tests for :mod:`meeting_minutes_agent.precomp.encode_warm`: the
encode-warm contact whose reply text is never read.

Every transport call in this module's tests goes through a FAKE ``post``
callable (:class:`~meeting_minutes_agent.client.transport.LlamaServerTransport`'s
own injection seam) -- zero network, zero model contact, mirroring every
other test file in this repository."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_minutes_agent.chunking.slicer import SliceManifest, SliceManifestEntry
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.precomp.budget import PrecompBudget, PrecompBudgetExceeded, WaveCeilings
from meeting_minutes_agent.precomp.encode_warm import (
    DEFAULT_ENCODE_WARM_MAX_TOKENS,
    build_encode_warm_decoding_params,
    encode_warm_manifest,
    encode_warm_slice,
)

#: A distinctive marker the fake server's reply text carries -- every test
#: below that asserts "never read" greps the FULL outcome/receipt payload
#: for this marker and asserts it is absent, rather than trusting a single
#: field-by-field check to catch a leak.
_SECRET_MARKER = "SECRET-GENERATED-TEXT-MARKER-0xDEADBEEF"


def _canned_response(text: str = _SECRET_MARKER, usage: dict | None = None) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": text}}], "usage": usage or {"prompt_tokens": 40, "completion_tokens": 1, "total_tokens": 41}}
    ).encode("utf-8")


def _write_fake_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF....WAVEfmt ")


def _transport(post, *, max_calls: int = 100, max_audio_seconds: float = 10_000.0) -> LlamaServerTransport:
    budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    return LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=post)


# ---------------------------------------------------------------------------
# build_encode_warm_decoding_params
# ---------------------------------------------------------------------------


class TestBuildEncodeWarmDecodingParams:
    def test_defaults_to_one_token(self):
        assert build_encode_warm_decoding_params() == {"max_tokens": 1}

    def test_honours_a_larger_explicit_cap(self):
        assert build_encode_warm_decoding_params(4) == {"max_tokens": 4}

    def test_merges_onto_extra_without_dropping_other_keys(self):
        params = build_encode_warm_decoding_params(1, extra={"temperature": 0.0})
        assert params == {"temperature": 0.0, "max_tokens": 1}

    def test_extra_max_tokens_is_overridden_by_the_explicit_cap(self):
        params = build_encode_warm_decoding_params(1, extra={"max_tokens": 999})
        assert params["max_tokens"] == 1

    @pytest.mark.parametrize("bad", [0, -1, 1.5, True])
    def test_rejects_a_non_positive_or_non_int_cap(self, bad):
        with pytest.raises(ValueError):
            build_encode_warm_decoding_params(bad)


# ---------------------------------------------------------------------------
# encode_warm_slice: request shape + discard-unread proof
# ---------------------------------------------------------------------------


class TestEncodeWarmSlice:
    def test_request_carries_the_one_token_cap_by_default(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        bodies = []

        def post(url, body):
            bodies.append(json.loads(body.decode("utf-8")))
            return _canned_response()

        encode_warm_slice(_transport(post), request_id="r1", audio_path=audio_path, audio_seconds=10.0)
        assert len(bodies) == 1
        assert bodies[0]["max_tokens"] == DEFAULT_ENCODE_WARM_MAX_TOKENS == 1

    def test_request_honours_a_caller_supplied_cap(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        bodies = []

        def post(url, body):
            bodies.append(json.loads(body.decode("utf-8")))
            return _canned_response()

        encode_warm_slice(_transport(post), request_id="r1", audio_path=audio_path, audio_seconds=10.0, max_tokens=3)
        assert bodies[0]["max_tokens"] == 3

    def test_outcome_carries_the_discard_unread_proof_field(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        outcome = encode_warm_slice(
            _transport(lambda url, body: _canned_response()), request_id="r1", audio_path=audio_path, audio_seconds=10.0
        )
        assert outcome["text_discarded_unread"] is True

    def test_outcome_never_carries_the_reply_text_anywhere(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        outcome = encode_warm_slice(
            _transport(lambda url, body: _canned_response()), request_id="r1", audio_path=audio_path, audio_seconds=10.0
        )
        assert "text" not in outcome
        # Grep the whole serialized outcome for the marker, not just the
        # "text" key -- proves the marker text was never copied into any
        # OTHER field either (e.g. smuggled into an "error" or "usage" key).
        assert _SECRET_MARKER not in json.dumps(outcome)

    def test_outcome_carries_usage_and_attempt_count(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        outcome = encode_warm_slice(
            _transport(lambda url, body: _canned_response(usage={"prompt_tokens": 7, "completion_tokens": 1})),
            request_id="r1",
            audio_path=audio_path,
            audio_seconds=10.0,
        )
        assert outcome["usage"] == {"prompt_tokens": 7, "completion_tokens": 1}
        assert outcome["n_attempts"] == 1
        assert outcome["max_tokens"] == 1

    def test_flight_receipt_records_the_ledger_without_leaking_text(self, tmp_path):
        audio_path = tmp_path / "s.wav"
        _write_fake_audio(audio_path)
        call_budget = CallBudget(BudgetLimits(max_calls=10, max_audio_seconds=1000.0))
        transport = LlamaServerTransport(TransportConfig(base_url="http://x"), call_budget, post=lambda url, body: _canned_response())
        server_identity = ServerIdentity(base_url="http://x", model_files=(ModelFileRef(path="m.gguf", sha256="a" * 64),))
        flight_receipt = FlightReceipt(server_identity, call_budget)

        encode_warm_slice(
            transport, request_id="r1", audio_path=audio_path, audio_seconds=10.0, flight_receipt=flight_receipt
        )

        assert len(flight_receipt.entries) == 1
        assert _SECRET_MARKER not in json.dumps(list(flight_receipt.entries))


# ---------------------------------------------------------------------------
# encode_warm_manifest: iterates a whole SliceManifest, budget-guarded
# ---------------------------------------------------------------------------


def _manifest(n: int, meeting_id: str = "MTG") -> SliceManifest:
    entries = tuple(
        SliceManifestEntry(
            index=i, start=float(i) * 90.0, end=float(i + 1) * 90.0, filename=f"{meeting_id}-slice{i:04d}.wav",
            sha256=f"h{i}", vad_snap_applied=False, encoder_chunk_count=3,
        )
        for i in range(n)
    )
    return SliceManifest(meeting_id=meeting_id, mode="turn_aware", turn_provenance="tool-diar", sample_rate=16000, channels=1, entries=entries, content_hash="ch")


class TestEncodeWarmManifest:
    def test_dispatches_one_request_per_entry_in_index_order(self, tmp_path):
        for i in range(3):
            _write_fake_audio(tmp_path / f"MTG-slice{i:04d}.wav")

        outcomes = encode_warm_manifest(_transport(lambda url, body: _canned_response()), _manifest(3), tmp_path, request_id_prefix="precomp-tool-MTG")
        assert [o["request_id"] for o in outcomes] == [f"precomp-tool-MTG-slice{i:04d}" for i in range(3)]
        assert all(o["text_discarded_unread"] for o in outcomes)

    def test_budget_checked_before_every_contact_and_trips_mid_manifest(self, tmp_path):
        for i in range(3):
            _write_fake_audio(tmp_path / f"MTG-slice{i:04d}.wav")
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=2))

        with pytest.raises(PrecompBudgetExceeded):
            encode_warm_manifest(
                _transport(lambda url, body: _canned_response()), _manifest(3), tmp_path,
                request_id_prefix="precomp-tool-MTG", budget=budget,
            )
        assert budget.encode_calls_used == 2  # the first two succeeded before the third tripped

    def test_records_onto_the_shared_budget(self, tmp_path):
        for i in range(2):
            _write_fake_audio(tmp_path / f"MTG-slice{i:04d}.wav")
        budget = PrecompBudget(WaveCeilings(wave=2, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=None, max_encode_calls=10))

        encode_warm_manifest(
            _transport(lambda url, body: _canned_response()), _manifest(2), tmp_path,
            request_id_prefix="precomp-oracle-MTG", budget=budget,
        )
        assert budget.encode_calls_used == 2

    def test_query_gpu_none_records_zero_gpu_seconds(self, tmp_path):
        _write_fake_audio(tmp_path / "MTG-slice0000.wav")
        outcomes = encode_warm_manifest(
            _transport(lambda url, body: _canned_response()), _manifest(1), tmp_path,
            request_id_prefix="precomp-tool-MTG", query_gpu=None,
        )
        assert outcomes[0]["gpu_seconds_estimate"] == 0.0

    def test_no_marker_text_anywhere_in_any_outcome(self, tmp_path):
        for i in range(2):
            _write_fake_audio(tmp_path / f"MTG-slice{i:04d}.wav")
        outcomes = encode_warm_manifest(
            _transport(lambda url, body: _canned_response()), _manifest(2), tmp_path, request_id_prefix="precomp-tool-MTG"
        )
        assert _SECRET_MARKER not in json.dumps(outcomes)
