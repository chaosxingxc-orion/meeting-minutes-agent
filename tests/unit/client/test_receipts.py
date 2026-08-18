from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity, hash_model_file
from meeting_minutes_agent.client.transport import ModelResponse, RequestAttempt


def _attempt(request_id="req-1", retry_of=None, attempt_number=1, outcome="ok", error=None) -> RequestAttempt:
    return RequestAttempt(
        request_id=request_id,
        retry_of=retry_of,
        attempt_number=attempt_number,
        started_at="2026-08-18T00:00:00+00:00",
        latency_seconds=0.5,
        outcome=outcome,
        error=error,
        audio_seconds=3.0,
    )


def _identity() -> ServerIdentity:
    return ServerIdentity(
        base_url="http://127.0.0.1:8080",
        model_files=(ModelFileRef(path="model.gguf", sha256="a" * 64), ModelFileRef(path="mmproj.gguf", sha256="b" * 64)),
        slots=2,
    )


class TestModelFileRef:
    def test_rejects_short_sha256(self):
        with pytest.raises(ValueError, match="sha256"):
            ModelFileRef(path="m.gguf", sha256="deadbeef").validate()

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            ModelFileRef(path="", sha256="a" * 64).validate()


class TestServerIdentity:
    def test_requires_at_least_one_model_file(self):
        with pytest.raises(ValueError, match="at least one"):
            ServerIdentity(base_url="http://x", model_files=()).validate()

    def test_to_dict_round_trips_shape(self):
        identity = _identity()
        as_dict = identity.to_dict()
        assert as_dict["base_url"] == "http://127.0.0.1:8080"
        assert as_dict["slots"] == 2
        assert as_dict["model_files"] == [
            {"path": "model.gguf", "sha256": "a" * 64},
            {"path": "mmproj.gguf", "sha256": "b" * 64},
        ]


class TestHashModelFile:
    def test_hashes_local_file_bytes(self, tmp_path):
        path = tmp_path / "m.gguf"
        path.write_bytes(b"some bytes")
        import hashlib

        expected = hashlib.sha256(b"some bytes").hexdigest()
        assert hash_model_file(path) == expected

    def test_missing_file_refuses(self, tmp_path):
        with pytest.raises(ValueError, match="not a file"):
            hash_model_file(tmp_path / "missing.gguf")


class TestFlightReceiptRoundTrip:
    def test_identical_content_hashes_identically_regardless_of_run_id(self):
        budget = CallBudget(BudgetLimits(max_calls=5, max_audio_seconds=100.0))
        receipt = FlightReceipt(_identity(), budget)
        receipt.record(ModelResponse(request_id="req-1", text="hi", usage={"prompt_tokens": 1}, attempts=(_attempt(),)))

        first = receipt.build(repo_root=".", run_id="run-a")
        second = receipt.build(repo_root=".", run_id="run-b")
        assert first.config_hash == second.config_hash
        assert first.run_id != second.run_id

    def test_different_ledger_content_changes_the_hash(self):
        budget = CallBudget(BudgetLimits(max_calls=5, max_audio_seconds=100.0))
        receipt = FlightReceipt(_identity(), budget)
        receipt.record(ModelResponse(request_id="req-1", text="hi", usage={}, attempts=(_attempt(),)))
        before = receipt.build(repo_root=".").config_hash

        receipt.record(ModelResponse(request_id="req-2", text="hi again", usage={}, attempts=(_attempt(request_id="req-2"),)))
        after = receipt.build(repo_root=".").config_hash
        assert before != after

    def test_retry_chain_and_budget_totals_are_both_in_the_ledger_and_hash(self):
        budget = CallBudget(BudgetLimits(max_calls=5, max_audio_seconds=100.0))
        budget.reserve(3.0)  # first (failed) attempt's own reservation
        budget.reserve(3.0)  # retry's reservation
        receipt = FlightReceipt(_identity(), budget)
        response = ModelResponse(
            request_id="req-1-r1",
            text="ok now",
            usage={"prompt_tokens": 2},
            attempts=(
                _attempt(request_id="req-1", outcome="error", error="timed out"),
                _attempt(request_id="req-1-r1", retry_of="req-1", attempt_number=2),
            ),
        )
        receipt.record(response)
        assert len(receipt.entries) == 2
        assert receipt.entries[0]["outcome"] == "error"
        assert receipt.entries[0]["error"] == "timed out"
        assert receipt.entries[1]["retry_of"] == "req-1"
        assert receipt.entries[1]["response_of"] == "req-1-r1"

        built = receipt.build(repo_root=".")
        assert built.config["budget_totals"]["calls_used"] == 2
        assert built.config["budget_totals"]["audio_seconds_used"] == 6.0
        assert built.config["request_ledger"] == list(receipt.entries)

    def test_write_produces_valid_json_readable_back(self, tmp_path):
        budget = CallBudget(BudgetLimits(max_calls=5, max_audio_seconds=100.0))
        receipt = FlightReceipt(_identity(), budget)
        receipt.record(ModelResponse(request_id="req-1", text="hi", usage={}, attempts=(_attempt(),)))
        out = receipt.write(tmp_path / "flight-receipt.json", repo_root=".", run_id="fixed")
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["run_id"] == "fixed"
        assert loaded["config"]["server_identity"]["base_url"] == "http://127.0.0.1:8080"
        assert len(loaded["config"]["request_ledger"]) == 1
        assert loaded["config_hash"] == receipt.build(repo_root=".", run_id="fixed").config_hash

    def test_empty_ledger_still_builds_a_valid_receipt(self):
        budget = CallBudget(BudgetLimits(max_calls=5, max_audio_seconds=100.0))
        receipt = FlightReceipt(_identity(), budget)
        built = receipt.build(repo_root=".")
        assert built.config["request_ledger"] == []
        assert built.config["budget_totals"]["calls_used"] == 0
