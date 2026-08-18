from __future__ import annotations

import http.server
import json
import threading
import urllib.error

import pytest

from meeting_minutes_agent.client.budgets import BudgetExceeded, BudgetLimits, CallBudget
from meeting_minutes_agent.client.transport import (
    LlamaServerTransport,
    RetryExhaustedError,
    TransportConfig,
    TransportError,
    build_request_payload,
)


def _write_wav(path):
    path.write_bytes(b"RIFF....WAVEfmt ")
    return path


def _budget(max_calls=10, max_audio_seconds=1000.0) -> CallBudget:
    return CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))


def _canned_response(text="hello world", prompt_tokens=3, completion_tokens=2) -> bytes:
    return json.dumps(
        {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
    ).encode("utf-8")


class TestTransportConfig:
    def test_rejects_empty_base_url(self):
        with pytest.raises(ValueError, match="base_url"):
            TransportConfig(base_url="").validate()

    def test_rejects_non_positive_timeout(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            TransportConfig(base_url="http://x", timeout_seconds=0).validate()

    def test_rejects_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries"):
            TransportConfig(base_url="http://x", max_retries=-1).validate()

    def test_rejects_non_positive_slots(self):
        with pytest.raises(ValueError, match="slots"):
            TransportConfig(base_url="http://x", slots=0).validate()


class TestBuildRequestPayload:
    def test_payload_shape_text_then_audio_last(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        payload = build_request_payload(
            task_instruction="transcribe this",
            audio_path=audio,
            supplied_text=["evidence one", "evidence two"],
            decoding_params={"temperature": 0.0, "seed": 7},
        )
        assert payload["messages"][0] == {"role": "system", "content": "transcribe this"}
        user_content = payload["messages"][1]["content"]
        assert user_content[0] == {"type": "text", "text": "evidence one"}
        assert user_content[1] == {"type": "text", "text": "evidence two"}
        assert user_content[2]["type"] == "input_audio"
        assert user_content[2]["input_audio"]["format"] == "wav"
        assert isinstance(user_content[2]["input_audio"]["data"], str)
        # decoding_params merged onto the body's top level
        assert payload["temperature"] == 0.0
        assert payload["seed"] == 7

    def test_no_supplied_text_still_carries_the_audio_part_only(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        payload = build_request_payload(task_instruction="t", audio_path=audio)
        user_content = payload["messages"][1]["content"]
        assert len(user_content) == 1
        assert user_content[0]["type"] == "input_audio"

    def test_missing_audio_file_refuses(self, tmp_path):
        with pytest.raises(TransportError, match="not found"):
            build_request_payload(task_instruction="t", audio_path=tmp_path / "missing.wav")

    def test_decoding_params_colliding_with_messages_refuses(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        with pytest.raises(TransportError, match="collides"):
            build_request_payload(
                task_instruction="t", audio_path=audio, decoding_params={"messages": "hijack"}
            )


class TestLlamaServerTransportRetry:
    def test_successful_first_attempt_records_one_attempt(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        posted = []

        def post(url, body):
            posted.append((url, body))
            return _canned_response()

        transport = LlamaServerTransport(TransportConfig(base_url="http://127.0.0.1:1/"), _budget(), post=post)
        response = transport.request(
            request_id="req-0001", task_instruction="t", audio_path=audio, audio_seconds=5.0
        )
        assert response.text == "hello world"
        assert response.request_id == "req-0001"
        assert response.usage == {"prompt_tokens": 3, "completion_tokens": 2}
        assert len(response.attempts) == 1
        assert response.attempts[0].outcome == "ok"
        assert response.attempts[0].retry_of is None
        assert posted[0][0] == "http://127.0.0.1:1/v1/chat/completions"

    def test_timeout_then_success_retries_once_with_a_fresh_derived_id(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def flaky_post(url, body):
            calls.append(body)
            if len(calls) == 1:
                raise TimeoutError("simulated timeout")
            return _canned_response()

        budget = _budget()
        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=1), budget, post=flaky_post
        )
        response = transport.request(
            request_id="req-0001", task_instruction="t", audio_path=audio, audio_seconds=5.0
        )
        # both attempts visible in the returned chain
        assert len(response.attempts) == 2
        first, second = response.attempts
        assert first.request_id == "req-0001"
        assert first.outcome == "error"
        assert first.retry_of is None
        assert second.request_id == "req-0001-r1"
        assert second.outcome == "ok"
        assert second.retry_of == "req-0001"
        assert response.request_id == "req-0001-r1"
        # each attempt (including the failed one) consumed its own budget
        # reservation
        assert budget.totals["calls_used"] == 2
        assert budget.totals["audio_seconds_used"] == 10.0

    def test_connection_error_is_retryable_too(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def flaky_post(url, body):
            calls.append(body)
            if len(calls) == 1:
                raise ConnectionError("refused")
            return _canned_response()

        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=1), _budget(), post=flaky_post
        )
        response = transport.request(
            request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0
        )
        assert len(response.attempts) == 2
        assert response.text == "hello world"

    def test_retries_exhausted_raises_and_every_attempt_consumed_budget(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")

        def always_timeout(url, body):
            raise TimeoutError("still down")

        budget = _budget()
        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=2), budget, post=always_timeout
        )
        with pytest.raises(RetryExhaustedError):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)
        # 1 initial + 2 retries = 3 attempts, each reserving budget
        assert budget.totals["calls_used"] == 3

    def test_max_retries_zero_never_retries(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def always_timeout(url, body):
            calls.append(body)
            raise TimeoutError("down")

        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=0), _budget(), post=always_timeout
        )
        with pytest.raises(RetryExhaustedError):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)
        assert len(calls) == 1

    def test_http_error_response_is_not_retried(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def bad_request(url, body):
            calls.append(body)
            raise urllib.error.HTTPError(url, 400, "Bad Request", hdrs=None, fp=None)

        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=3), _budget(), post=bad_request
        )
        with pytest.raises(TransportError, match="HTTP 400"):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)
        # no retry: exactly one attempt was made
        assert len(calls) == 1

    def test_unrelated_exception_propagates_immediately_without_retry(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def broken(url, body):
            calls.append(body)
            raise ValueError("not a transport failure")

        transport = LlamaServerTransport(
            TransportConfig(base_url="http://x/", max_retries=3), _budget(), post=broken
        )
        with pytest.raises(ValueError, match="not a transport failure"):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)
        assert len(calls) == 1

    def test_malformed_response_is_a_transport_error(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")

        def malformed(url, body):
            return b"not json"

        transport = LlamaServerTransport(TransportConfig(base_url="http://x/"), _budget(), post=malformed)
        with pytest.raises(TransportError, match="malformed response"):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)


class TestLlamaServerTransportBudgetIntegration:
    def test_budget_refusal_prevents_the_call_entirely(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")
        calls = []

        def must_not_be_called(url, body):
            calls.append(body)
            raise AssertionError("transport must not be called when budget refuses")

        budget = _budget(max_calls=1)
        budget.reserve(1.0)  # consume the only call up front
        transport = LlamaServerTransport(TransportConfig(base_url="http://x/"), budget, post=must_not_be_called)
        with pytest.raises(BudgetExceeded):
            transport.request(request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0)
        assert calls == []

    def test_timing_is_recorded_and_positive(self, tmp_path):
        audio = _write_wav(tmp_path / "clip.wav")

        def slow_post(url, body):
            return _canned_response()

        transport = LlamaServerTransport(TransportConfig(base_url="http://x/"), _budget(), post=slow_post)
        response = transport.request(
            request_id="req-1", task_instruction="t", audio_path=audio, audio_seconds=1.0
        )
        assert response.attempts[0].latency_seconds >= 0.0
        assert response.attempts[0].started_at  # non-empty ISO timestamp
        assert response.attempts[0].audio_seconds == 1.0


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    """Real mock HTTP server: echoes back a canned chat-completions response
    and records exactly what was POSTed, for a genuine over-the-socket
    payload-shape check (module-level test class docstring instruction:
    "tests use a mock HTTP server / injected fakes")."""

    captured: dict = {}

    def do_POST(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        type(self).captured["path"] = self.path
        type(self).captured["body"] = json.loads(body)
        response = _canned_response(text="server said hi", prompt_tokens=1, completion_tokens=1)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):  # noqa: A002 - silence test server logs
        pass


@pytest.fixture
def mock_server():
    _EchoHandler.captured = {}
    server = http.server.HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)


class TestLlamaServerTransportOverRealSocket:
    def test_real_http_post_reaches_the_chat_completions_path_with_the_right_shape(
        self, tmp_path, mock_server
    ):
        audio = _write_wav(tmp_path / "clip.wav")
        port = mock_server.server_address[1]
        transport = LlamaServerTransport(TransportConfig(base_url=f"http://127.0.0.1:{port}"), _budget())
        response = transport.request(
            request_id="req-1",
            task_instruction="hi",
            audio_path=audio,
            audio_seconds=2.0,
            supplied_text=["ev"],
        )
        assert response.text == "server said hi"
        assert _EchoHandler.captured["path"] == "/v1/chat/completions"
        body = _EchoHandler.captured["body"]
        assert body["messages"][0] == {"role": "system", "content": "hi"}
        assert body["messages"][1]["content"][0] == {"type": "text", "text": "ev"}
        assert body["messages"][1]["content"][1]["type"] == "input_audio"
