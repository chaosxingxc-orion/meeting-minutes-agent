"""FrozenMeetingCore tests -- openjiuwen-gated (module docstring of
meeting_minutes_agent.client.component: importing it without openjiuwen
raises ImportError with an install hint, which importorskip below turns
into a clean skip for every test in this file)."""

from __future__ import annotations

import asyncio
import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip(
    "meeting_minutes_agent.client.component",
    reason="openjiuwen not installed; FrozenMeetingCore is exercised only in the pinned "
    "WSL research venv (zero-dependency gate: never a pyproject dependency)",
)

from meeting_minutes_agent.client.component import (
    RESPONSE_LOG_KEY,
    ComponentError,
    FrozenMeetingCore,
    build_single_request_workflow,
)


@dataclass
class _FakeAttempt:
    request_id: str
    retry_of: object
    attempt_number: int
    started_at: str
    latency_seconds: float
    outcome: str
    error: object
    audio_seconds: float


@dataclass
class _FakeResponse:
    request_id: str
    text: str
    usage: dict
    attempts: tuple


class _FakeClient:
    """Duck-typed stand-in for LlamaServerTransport -- the "constructor-
    injected client" FrozenMeetingCore wraps, per its own class docstring;
    real production code injects a real transport instead."""

    def __init__(self, response_text_template: str = "transcribed[{task_instruction}]"):
        self.calls: list[dict[str, object]] = []
        self._template = response_text_template

    def request(
        self,
        *,
        request_id,
        task_instruction,
        audio_path,
        audio_seconds,
        supplied_text=(),
        decoding_params=None,
    ):
        self.calls.append(
            dict(
                request_id=request_id,
                task_instruction=task_instruction,
                audio_path=audio_path,
                audio_seconds=audio_seconds,
                supplied_text=supplied_text,
                decoding_params=decoding_params,
            )
        )
        return _FakeResponse(
            request_id=request_id,
            text=self._template.format(task_instruction=task_instruction),
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            attempts=(
                _FakeAttempt(request_id, None, 1, "2026-08-18T00:00:00+00:00", 0.01, "ok", None, audio_seconds),
            ),
        )


class _FakeSession:
    """Minimal duck-typed stand-in for openJiuwen's per-node ``Session``:
    implements only the two methods FrozenMeetingCore actually calls
    (``get_global_state``/``update_global_state``), dict-backed. Real graph
    execution supplies the framework's own per-node session object -- see
    TestFullMinimalWorkflow below for that path; this fake exists so the
    component's own logic (None-deletion discipline, log accumulation, the
    required-field refusal) is testable directly and fast, without paying
    for a full Workflow/Pregel graph build+run per case."""

    def __init__(self) -> None:
        self._global: dict[str, object] = {}

    def get_global_state(self, key=None):
        return self._global.get(key)

    def update_global_state(self, data):
        self._global.update(data)


@pytest.fixture
def audio_file(tmp_path) -> Path:
    path = tmp_path / "clip.wav"
    path.write_bytes(b"RIFF....WAVEfmt ")
    return path


class TestFrozenMeetingCoreConstructor:
    def test_requires_a_callable_request_method(self):
        with pytest.raises(ComponentError, match="callable"):
            FrozenMeetingCore(client=object())

    def test_accepts_a_client_exposing_request(self):
        FrozenMeetingCore(client=_FakeClient())  # must not raise


class TestFrozenMeetingCoreInvoke:
    def test_calls_the_injected_client_and_returns_its_response(self, audio_file):
        client = _FakeClient()
        component = FrozenMeetingCore(client)
        session = _FakeSession()

        async def run():
            return await component.invoke(
                {
                    "request_id": "r1",
                    "task_instruction": "transcribe",
                    "audio_path": str(audio_file),
                    "audio_seconds": 3.0,
                },
                session,
                None,
            )

        output = asyncio.run(run())
        assert output["text"] == "transcribed[transcribe]"
        assert output["request_id"] == "r1"
        assert output["usage"] == {"prompt_tokens": 1, "completion_tokens": 1}
        assert client.calls[0]["audio_path"] == Path(audio_file)
        assert client.calls[0]["audio_seconds"] == 3.0

    def test_optional_fields_default_via_none_deletion_discipline(self, audio_file):
        # Neither supplied_text nor decoding_params given: the component
        # must read them back with .get() (a missing key IS the None/absent
        # default), not raise a KeyError, and pass empty defaults through.
        client = _FakeClient()
        component = FrozenMeetingCore(client)
        session = _FakeSession()

        async def run():
            return await component.invoke(
                {
                    "request_id": "r1",
                    "task_instruction": "t",
                    "audio_path": str(audio_file),
                    "audio_seconds": 1.0,
                },
                session,
                None,
            )

        asyncio.run(run())
        assert client.calls[0]["supplied_text"] == ()
        assert client.calls[0]["decoding_params"] == {}

    def test_optional_fields_are_forwarded_when_present(self, audio_file):
        client = _FakeClient()
        component = FrozenMeetingCore(client)
        session = _FakeSession()

        async def run():
            return await component.invoke(
                {
                    "request_id": "r1",
                    "task_instruction": "t",
                    "audio_path": str(audio_file),
                    "audio_seconds": 1.0,
                    "supplied_text": ["evidence"],
                    "decoding_params": {"temperature": 0.2},
                },
                session,
                None,
            )

        asyncio.run(run())
        assert client.calls[0]["supplied_text"] == ("evidence",)
        assert client.calls[0]["decoding_params"] == {"temperature": 0.2}

    @pytest.mark.parametrize("missing_key", ["request_id", "task_instruction", "audio_path", "audio_seconds"])
    def test_missing_required_field_refuses(self, audio_file, missing_key):
        client = _FakeClient()
        component = FrozenMeetingCore(client)
        session = _FakeSession()
        inputs = {
            "request_id": "r1",
            "task_instruction": "t",
            "audio_path": str(audio_file),
            "audio_seconds": 1.0,
        }
        del inputs[missing_key]

        async def run():
            return await component.invoke(inputs, session, None)

        with pytest.raises(ComponentError, match=missing_key):
            asyncio.run(run())
        assert client.calls == []  # refused before the client was ever touched

    def test_response_log_accumulates_across_invocations_on_the_same_session(self, audio_file):
        client = _FakeClient()
        component = FrozenMeetingCore(client)
        session = _FakeSession()

        async def run_two():
            await component.invoke(
                {"request_id": "r1", "task_instruction": "t1", "audio_path": str(audio_file), "audio_seconds": 1.0},
                session,
                None,
            )
            await component.invoke(
                {"request_id": "r2", "task_instruction": "t2", "audio_path": str(audio_file), "audio_seconds": 1.0},
                session,
                None,
            )

        asyncio.run(run_two())
        log = session.get_global_state(RESPONSE_LOG_KEY)
        assert [entry["request_id"] for entry in log] == ["r1", "r2"]
        assert all("text_sha256" in entry for entry in log)

    def test_response_log_is_absent_until_the_first_invocation(self, audio_file):
        session = _FakeSession()
        assert session.get_global_state(RESPONSE_LOG_KEY) is None


class TestFullMinimalWorkflow:
    """The literal instruction: fake client through a minimal Workflow
    invoke, following the SAEA ojw test pattern -- a real openJiuwen graph
    (Start -> FrozenMeetingCore -> End), driven by the framework's own
    Pregel engine end to end, with a real per-node Session (not the
    duck-typed fake above)."""

    def test_single_request_workflow_invokes_the_fake_client(self, audio_file):
        client = _FakeClient()

        async def build_and_run():
            # Built and invoked inside one running event loop -- the
            # framework's graph vertices create asyncio primitives at
            # construction time (build_single_request_workflow's own
            # docstring); never build the graph at bare sync top level.
            from openjiuwen.core.workflow import create_workflow_session

            flow = build_single_request_workflow(client)
            session = create_workflow_session()
            return await flow.invoke(
                inputs={
                    "request_id": "wf-1",
                    "task_instruction": "summarize the meeting",
                    "audio_path": str(audio_file),
                    "audio_seconds": 5.0,
                    "supplied_text": ["agenda item one"],
                    "decoding_params": {},
                },
                session=session,
            )

        result = asyncio.run(build_and_run())
        core_output = result.result["output"]["core"]
        assert core_output["text"] == "transcribed[summarize the meeting]"
        assert core_output["request_id"] == "wf-1"
        assert len(client.calls) == 1
        assert client.calls[0]["task_instruction"] == "summarize the meeting"
        assert client.calls[0]["supplied_text"] == ("agenda item one",)


def _openjiuwen_importable() -> bool:
    return importlib.util.find_spec("openjiuwen") is not None


@pytest.mark.skipif(
    _openjiuwen_importable(),
    reason="the absent-install refusal path only exists when openjiuwen is not installed",
)
def test_component_module_raises_a_clear_install_hint_when_openjiuwen_absent():
    # This test only actually RUNS in an environment without openjiuwen
    # installed (skipped here, mirroring the SAEA study's own environment-
    # dependent skip discipline for its equivalent absent-refusal test).
    with pytest.raises(ImportError, match="openjiuwen"):
        import meeting_minutes_agent.client.component  # noqa: F401
