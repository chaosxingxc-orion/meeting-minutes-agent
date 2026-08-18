"""``FrozenMeetingCore``: the openJiuwen single door to the frozen meeting
core.

Owner ruling (``docs/plans/2026-08-18-agent-backbone-and-layout.md`` SS5.3,
"Agent-loop framework: openJiuwen AgentLoop"): the agent is developed ON
openJiuwen (openjiuwen 0.1.16.post2, the SAEA-proven pin) as an AgentLoop
design, not ReAct/DeepAgents; the mapping table names "our client component
(E6) wrapping the meeting repo's core client" as the single door -- this
module is that component.

Lineage (recorded cross-repo import; CLAUDE.md "Research object" /
2026-08-17 owner decision): reimplements, small, the SAEA study's
``reproduction/ojw/components.py::FrozenCoreASR`` single-door shape and the
None-deletion session-state discipline documented in
``docs/readiness/2026-08-08-ojw-rebuild-notes.md`` (studies/speech-aware-
evidence-acquisition, umbrella commit range including ``12590d4``). No code
is imported from that study. Dropped, deliberately, because this
repository's E7 controller (not yet built) owns its own loop/state shape:
the SAEA slice-boundary/tail/trace-record apparatus, the D2 arm-payload
builder, and the driver-side ``ObsSampleState`` object -- this module is
only the door itself, kept intentionally small so E7 can wrap it however
its own task-manager loop needs to.

Component discipline (owner ruling, carried over from the SAEA rebuild
notes verbatim): ``FrozenMeetingCore`` DERIVES from the framework's
``ComponentExecutable`` line via ``WorkflowComponent`` (the framework's own
standard user-component base); ``Workflow``/``Start``/``End`` are COMPOSED
here only to build the smallest graph that proves the wiring
(:func:`build_single_request_workflow`) -- the real, larger graph is E7's.
No openJiuwen LLM/model client (``foundation/llm`` or otherwise) is ever
imported or instantiated anywhere in this repository; the ONLY path to the
frozen core is the constructor-injected client this component wraps.

Import discipline (zero-dependency gate, carried over from SAEA red line 2):
openjiuwen NEVER enters this repository's ``pyproject.toml``. This module
imports openjiuwen at import time; importing it without openjiuwen
installed raises ``ImportError`` naming :data:`OJW_INSTALL_HINT`, which
``pytest.importorskip("meeting_minutes_agent.client.component")`` turns
into a clean skip for every test in this module's own test file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

OJW_INSTALL_HINT = (
    "meeting_minutes_agent.client.component requires the openjiuwen framework, which "
    "is not importable in this environment; install the pinned openjiuwen==0.1.16.post2 "
    "into the shared WSL research venv (see "
    "docs/plans/2026-08-18-agent-backbone-and-layout.md SS5.3) -- openjiuwen never enters "
    "pyproject.toml (zero-dependency gate), and this module cannot be used without it. "
    "Use meeting_minutes_agent.client.transport.LlamaServerTransport directly if no "
    "openJiuwen graph is needed."
)

try:
    from openjiuwen.core.context_engine import ModelContext
    from openjiuwen.core.graph.executable import Input, Output
    from openjiuwen.core.session.node import Session
    from openjiuwen.core.workflow import End, Start, Workflow, WorkflowComponent
except ImportError as error:  # pragma: no cover - exercised via importorskip
    raise ImportError(OJW_INSTALL_HINT) from error


class ComponentError(RuntimeError):
    """FrozenMeetingCore refused: a malformed client, or a required
    per-invocation field missing from the session-seeded inputs."""


@runtime_checkable
class MeetingCoreClient(Protocol):
    """The shape :class:`FrozenMeetingCore` requires of its injected
    client: :class:`~meeting_minutes_agent.client.transport.
    LlamaServerTransport` in production, a test fake anywhere else. Never a
    framework LLM client (module docstring)."""

    def request(
        self,
        *,
        request_id: str,
        task_instruction: str,
        audio_path: Path,
        audio_seconds: float,
        supplied_text: Sequence[str] = (),
        decoding_params: Mapping[str, object] | None = None,
    ) -> Any: ...


# Session GLOBAL-state key for the loop-carried response log (single writer:
# this component, appending one entry per invocation; a future E7 reader
# consumes it as the accumulating record of what the door has answered so
# far). Flat underscore name -- the framework's nested-path split is ".",
# so a dotted key would be misread as a path (mirrors the SAEA study's own
# ACCEPTED_SPANS_KEY convention).
RESPONSE_LOG_KEY = "meeting_core_response_log"

START_NODE_ID = "start"
CORE_NODE_ID = "core"
END_NODE_ID = "end"

_REQUIRED_INPUT_FIELDS = ("request_id", "task_instruction", "audio_path", "audio_seconds")


def _required(inputs: Mapping[str, object], key: str) -> object:
    """A required per-invocation input. Fail-closed: a missing value means
    the workflow was invoked without seeding it -- refuse rather than
    guess (mirrors the SAEA study's own ``components._static`` discipline
    for required session-seeded values)."""

    if key not in inputs or inputs[key] is None:
        raise ComponentError(
            f"FrozenMeetingCore invocation is missing required input {key!r}; the workflow "
            "must be invoked with all of "
            f"{_REQUIRED_INPUT_FIELDS} seeded (see build_single_request_workflow's own "
            "inputs_schema)"
        )
    return inputs[key]


class FrozenMeetingCore(WorkflowComponent):
    """THE single door to the frozen meeting core.

    Wraps a constructor-injected client's ``.request(...)`` call (never a
    framework LLM/model client). Reads its four required per-invocation
    values (``request_id``, ``task_instruction``, ``audio_path``,
    ``audio_seconds``) from the framework input state, and two optional
    ones (``supplied_text``, ``decoding_params``) with the None-deletion
    discipline: the framework's session-state merge deletes a None-valued
    key entirely (SAEA rebuild-notes "Framework findings" SS1: "A component
    output like ``{"pre_sha256": None}`` arrives at the next node WITHOUT
    the key"), so a missing key here IS the None/absent default that was
    set -- read back with ``.get()``, never a bare ``inputs[key]``.

    After each call, appends a small summary (never the raw response text,
    to keep session state light) to the session GLOBAL response log under
    :data:`RESPONSE_LOG_KEY`, read back the same None-deletion-safe way on
    the next invocation.
    """

    def __init__(self, client: MeetingCoreClient) -> None:
        super().__init__()
        if not hasattr(client, "request") or not callable(getattr(client, "request")):
            raise ComponentError(
                "FrozenMeetingCore requires a client exposing a callable .request(...) "
                "method (meeting_minutes_agent.client.transport.LlamaServerTransport or a "
                f"test fake); got {type(client).__name__}"
            )
        self._client = client

    async def invoke(self, inputs: Input, session: Session, context: ModelContext) -> Output:
        request_id = _required(inputs, "request_id")
        task_instruction = _required(inputs, "task_instruction")
        audio_path = _required(inputs, "audio_path")
        audio_seconds = _required(inputs, "audio_seconds")
        # Optional fields: None-deletion discipline (class docstring) --
        # `.get()` with an explicit default, never a bare subscript.
        supplied_text = inputs.get("supplied_text") or ()
        decoding_params = inputs.get("decoding_params") or {}

        response = self._client.request(
            request_id=str(request_id),
            task_instruction=str(task_instruction),
            audio_path=Path(audio_path),
            audio_seconds=float(audio_seconds),
            supplied_text=tuple(supplied_text),
            decoding_params=dict(decoding_params),
        )

        # Same None-deletion-safe read on the way in: an empty/absent log is
        # exactly `session.get_global_state(...) or []`, never a KeyError.
        log = list(session.get_global_state(RESPONSE_LOG_KEY) or [])
        log.append(
            {
                "request_id": response.request_id,
                "text_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
                "attempt_count": len(response.attempts),
            }
        )
        session.update_global_state({RESPONSE_LOG_KEY: log})

        return {
            "text": response.text,
            "usage": dict(response.usage),
            "request_id": response.request_id,
        }


def build_single_request_workflow(client: MeetingCoreClient) -> Workflow:
    """The smallest graph that proves the door's wiring: ``Start ->
    FrozenMeetingCore -> End``, one request in, one response out. Mirrors
    the SAEA study's own ojw test pattern
    (``reproduction/ojw/runner.py::build_obs_workflow``, minus the OBS loop
    body this repository has no equivalent of yet) -- E7's controller graph
    is the real, larger consumer of :class:`FrozenMeetingCore`; this
    function exists for tests and as a worked example of the wiring.

    Must be called from inside a running asyncio event loop (e.g. inside the
    same coroutine an ``await flow.invoke(...)`` follows in, itself run via
    ``asyncio.run``), never at bare sync top level -- the framework's graph
    vertices create asyncio primitives at construction time (SAEA rebuild-
    notes "Framework findings" SS2: "Build inside the loop"). A graph built
    outside a running loop can appear to work once (Python's legacy
    ``get_event_loop()`` auto-creates a loop the first time) and then fail
    with ``RuntimeError: There is no current event loop`` the next time a
    graph is built in the same process, once an earlier ``asyncio.run`` has
    already closed its own loop -- always build a fresh graph (and a fresh
    session) inside the coroutine that will invoke it, one pair per
    request, never reused across invocations."""

    flow = Workflow()
    flow.set_start_comp(
        START_NODE_ID,
        Start(),
        inputs_schema={
            "request_id": "${request_id}",
            "task_instruction": "${task_instruction}",
            "audio_path": "${audio_path}",
            "audio_seconds": "${audio_seconds}",
            "supplied_text": "${supplied_text}",
            "decoding_params": "${decoding_params}",
        },
    )
    flow.add_workflow_comp(
        CORE_NODE_ID,
        FrozenMeetingCore(client),
        inputs_schema={
            "request_id": f"${{{START_NODE_ID}.request_id}}",
            "task_instruction": f"${{{START_NODE_ID}.task_instruction}}",
            "audio_path": f"${{{START_NODE_ID}.audio_path}}",
            "audio_seconds": f"${{{START_NODE_ID}.audio_seconds}}",
            "supplied_text": f"${{{START_NODE_ID}.supplied_text}}",
            "decoding_params": f"${{{START_NODE_ID}.decoding_params}}",
        },
    )
    flow.set_end_comp(END_NODE_ID, End(), inputs_schema={"core": f"${{{CORE_NODE_ID}}}"})
    flow.add_connection(START_NODE_ID, CORE_NODE_ID)
    flow.add_connection(CORE_NODE_ID, END_NODE_ID)
    return flow
