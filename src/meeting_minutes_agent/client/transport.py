"""``LlamaServerTransport``: the lean llama-server HTTP client.

Lineage: reimplements, small, the request-shape and retry lessons of the
SAEA study's ``core/model/transport.py::LlamaServerTransport`` and
``core/model/adapter.py``'s bounded per-slice retry pattern
(``reproduction/obs_loop.py::request_slice_with_retry``, documented in
``docs/readiness/2026-08-08-ojw-rebuild-notes.md`` SS"Bounded per-slice
retry") -- studies/speech-aware-evidence-acquisition, umbrella commit range
including ``12590d4``. No code is imported from that study.

Payload shape (the SAEA study's "system-instruction-v1" order -- the
historical, simplest order; this repository has no per-arm prompt-cache
tuning to preserve, so there is exactly one order, not SAEA's three): a chat
message pair,

    [{"role": "system", "content": <task_instruction>},
     {"role": "user", "content": [<text parts from supplied_text>...,
                                   <one input_audio part>]}]

sent as the body of ``POST {base_url}/v1/chat/completions``, with
``decoding_params`` merged onto the body's top level (refused on any key
collision with ``messages``, so a config typo can never silently replace
the constructed request). The audio part is exactly llama.cpp's
OpenAI-compatible ``input_audio`` content-part shape: base64 file bytes
plus a ``format`` string taken from the file's own suffix.

``supplied_text_after_audio`` (added for the P-PROMPT template/arrangement
sweep, ``meeting_minutes_agent.probes.pprompt``: its A3 arrangement -- "context
in the user turn AFTER the audio" -- needs user-turn text placed AFTER the
audio part, which the original text-then-audio-last order could not express):
an OPTIONAL, additional sequence of text parts appended to the user message
AFTER the audio part. Defaults to ``()`` on both :func:`build_request_payload`
and :meth:`LlamaServerTransport.request`, in which case the content list is
byte-identical to what this module has always produced -- every existing
caller (P-ATTR, every task head) is unaffected.

Slice-bounds guard (17-item change list items 2/10, the second G1-blocking
defect): a request may carry AT MOST one transport slice's audio, never a
whole task chunk or a whole meeting file. ``TransportConfig.
max_audio_seconds_per_request`` (default
:data:`~meeting_minutes_agent.chunking.constants.TRANSPORT_SLICE_MAX_S` =
120 s, the binding proposal's hard slice bound) is checked against every
call's ``audio_seconds`` BEFORE any bytes are read or budget reserved;
:meth:`LlamaServerTransport.request` raises :class:`TransportError`
immediately on an oversized request rather than sending it -- callers must
resolve audio from the frozen slice manifest (:mod:`meeting_minutes_agent.
chunking.slicer`), never a whole chunk or meeting file.

Retry (bounded, per this module's own docstring instruction): retryable =
``TimeoutError``/``ConnectionError`` only -- never an HTTP error response
(a 4xx/5xx is a real, informative answer from the server, not a transient
failure, so it propagates immediately rather than being retried against an
unchanged budget). Each retry is a FRESH request: a derived id
(``<request_id>-r<n>``), a freshly-built payload, and its own budget
reservation -- mirroring the SAEA study's "each retry is a FRESH request:
derived request id... fresh payload build, separately traced and metered".
Every attempt (failed and successful) is returned on
:class:`ModelResponse.attempts`, so a caller building a flight receipt sees
the whole chain, not just the outcome.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

from ..chunking.constants import TRANSPORT_SLICE_MAX_S
from .budgets import CallBudget

# Network-level failures only -- an HTTP error response (urllib.error.HTTPError,
# a urllib.error.URLError subclass) is deliberately NOT retryable here (module
# docstring): it is caught and handled separately below, always as a
# terminal TransportError.
_RETRYABLE_EXCEPTIONS = (TimeoutError, ConnectionError)


class TransportError(RuntimeError):
    """A request attempt failed for a reason other than the bounded retry's
    own exhaustion (malformed response, non-retryable network error, an HTTP
    error status, a missing/invalid audio file, ...)."""


class RetryExhaustedError(TransportError):
    """Every attempt in the bounded retry chain failed with a retryable
    (timeout/connection) error. This module keeps the failure path a plain
    exception -- no partial :class:`ModelResponse` is returned -- matching
    the SAEA study's own "the final failure propagates unchanged
    (fail-closed as before)"."""


@dataclass(frozen=True)
class TransportConfig:
    """Configuration for one :class:`LlamaServerTransport` instance.

    ``slots`` is metadata only (this module never batches or pins requests
    to a slot -- that is a future, larger-scale concern); it rides along so
    a flight receipt's server identity can record how many server slots the
    run was configured against. Defaults to 4 to MATCH the flown ``-np 4``
    serving config (17-item change list item 11: the old default of 1
    contradicted the 4-way batching lock (b) asks to optimize) -- keep
    ``obs_batch_samples <= -np`` when raising this.

    ``max_audio_seconds_per_request`` is the slice-bounds guard (module
    docstring): the hard ceiling on ``audio_seconds`` any single call may
    carry, defaulting to the binding proposal's transport-slice max (120 s).
    """

    base_url: str
    timeout_seconds: float = 300.0
    max_retries: int = 1
    slots: int = 4
    max_audio_seconds_per_request: float = TRANSPORT_SLICE_MAX_S

    def validate(self) -> "TransportConfig":
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ValueError(f"base_url must be a non-empty string, got {self.base_url!r}")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError(f"timeout_seconds must be a positive number, got {self.timeout_seconds!r}")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise ValueError(f"max_retries must be a non-negative integer, got {self.max_retries!r}")
        if isinstance(self.slots, bool) or not isinstance(self.slots, int) or self.slots <= 0:
            raise ValueError(f"slots must be a positive integer, got {self.slots!r}")
        if (
            isinstance(self.max_audio_seconds_per_request, bool)
            or not isinstance(self.max_audio_seconds_per_request, (int, float))
            or self.max_audio_seconds_per_request <= 0
        ):
            raise ValueError(
                "max_audio_seconds_per_request must be a positive number, got "
                f"{self.max_audio_seconds_per_request!r}"
            )
        return self


@dataclass(frozen=True)
class RequestAttempt:
    """One attempt in a request's (possibly length-1) retry chain -- exactly
    what :mod:`.receipts` needs for the request ledger: id, timing, audio
    seconds, and retry-chain linkage."""

    request_id: str
    retry_of: str | None
    attempt_number: int  # 1-based within this chain
    started_at: str  # ISO-8601 UTC
    latency_seconds: float
    outcome: str  # "ok" | "error"
    error: str | None
    audio_seconds: float

    def as_json(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "retry_of": self.retry_of,
            "attempt_number": self.attempt_number,
            "started_at": self.started_at,
            "latency_seconds": self.latency_seconds,
            "outcome": self.outcome,
            "error": self.error,
            "audio_seconds": self.audio_seconds,
        }


@dataclass(frozen=True)
class ModelResponse:
    request_id: str  # the id of the attempt that actually succeeded
    text: str
    usage: Mapping[str, int]
    attempts: tuple[RequestAttempt, ...]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_post(timeout_seconds: float) -> Callable[[str, bytes], bytes]:
    def post(url: str, body: bytes) -> bytes:
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read()

    return post


def build_request_payload(
    *,
    task_instruction: str,
    audio_path: Path,
    supplied_text: Sequence[str] = (),
    supplied_text_after_audio: Sequence[str] = (),
    decoding_params: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the llama-server chat-completions JSON body (module docstring
    for the exact shape). Reads and base64-encodes ``audio_path`` -- the one
    piece of real I/O in this function; everything else is pure."""

    path = Path(audio_path)
    if not path.is_file():
        raise TransportError(f"audio file not found: {path}")
    data_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    audio_part = {
        "type": "input_audio",
        "input_audio": {"data": data_b64, "format": path.suffix.lstrip(".").lower()},
    }
    content: list[dict[str, object]] = [{"type": "text", "text": text} for text in supplied_text]
    content.append(audio_part)
    content.extend({"type": "text", "text": text} for text in supplied_text_after_audio)
    body: dict[str, object] = {
        "messages": [
            {"role": "system", "content": task_instruction},
            {"role": "user", "content": content},
        ]
    }
    for key, value in dict(decoding_params or {}).items():
        if key in body:
            raise TransportError(
                f"decoding_params key {key!r} collides with the constructed request body "
                "and would silently override it"
            )
        body[key] = value
    return body


def _parse_response(raw: bytes) -> tuple[str, dict[str, int]]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
        choice = parsed["choices"][0]
        text = choice["message"]["content"]
        usage = {
            str(k): int(v) for k, v in dict(parsed.get("usage", {})).items() if not isinstance(v, Mapping)
        }
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError) as error:
        raise TransportError(f"server returned a malformed response: {error}") from error
    if not isinstance(text, str):
        raise TransportError(f"server returned a non-string message content: {type(text).__name__}")
    return text, usage


class LlamaServerTransport:
    """One llama-server endpoint, with hard client-side budgets and bounded
    retry. ``post`` is injectable (tests use a mock HTTP server or a fake
    callable -- module docstring; this class never spawns or contacts a
    real ``llama-server`` process in this repository's own test suite)."""

    def __init__(
        self,
        config: TransportConfig,
        budget: CallBudget,
        *,
        post: Callable[[str, bytes], bytes] | None = None,
    ) -> None:
        self._config = config.validate()
        self._budget = budget
        self._url = self._config.base_url.rstrip("/") + "/v1/chat/completions"
        self._post = post or _default_post(self._config.timeout_seconds)

    @property
    def config(self) -> TransportConfig:
        return self._config

    def request(
        self,
        *,
        request_id: str,
        task_instruction: str,
        audio_path: Path,
        audio_seconds: float,
        supplied_text: Sequence[str] = (),
        supplied_text_after_audio: Sequence[str] = (),
        decoding_params: Mapping[str, object] | None = None,
    ) -> ModelResponse:
        if not isinstance(request_id, str) or not request_id:
            raise TransportError(f"request_id must be a non-empty string, got {request_id!r}")
        # Slice-bounds guard (module docstring): checked once, before any
        # attempt, budget reservation, or byte read -- a request may carry
        # AT MOST one transport slice's audio.
        if audio_seconds > self._config.max_audio_seconds_per_request:
            raise TransportError(
                f"request {request_id!r} carries audio_seconds={audio_seconds}, which exceeds this "
                f"transport's max_audio_seconds_per_request={self._config.max_audio_seconds_per_request}; "
                "a core request may carry at most one transport slice's audio "
                "(docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md SS8.1) -- resolve "
                "audio from the frozen slice manifest (meeting_minutes_agent.chunking.slicer), "
                "never a whole task chunk or meeting file"
            )
        attempts: list[RequestAttempt] = []
        retry_of: str | None = None
        max_attempts = self._config.max_retries + 1
        for attempt_number in range(1, max_attempts + 1):
            current_id = request_id if attempt_number == 1 else f"{request_id}-r{attempt_number - 1}"
            # Budget reservation happens BEFORE the transport call, and the
            # transport call itself happens outside CallBudget's own lock
            # (budgets.py docstring) -- a refused reservation here means this
            # attempt is never sent at all, fail-closed.
            self._budget.reserve(audio_seconds)
            payload = build_request_payload(
                task_instruction=task_instruction,
                audio_path=audio_path,
                supplied_text=supplied_text,
                supplied_text_after_audio=supplied_text_after_audio,
                decoding_params=decoding_params,
            )
            started_at = _iso_now()
            started = time.monotonic()
            try:
                raw = self._post(self._url, json.dumps(payload).encode("utf-8"))
            except _RETRYABLE_EXCEPTIONS as error:
                latency = time.monotonic() - started
                attempts.append(
                    RequestAttempt(
                        request_id=current_id,
                        retry_of=retry_of,
                        attempt_number=attempt_number,
                        started_at=started_at,
                        latency_seconds=latency,
                        outcome="error",
                        error=str(error),
                        audio_seconds=float(audio_seconds),
                    )
                )
                retry_of = request_id
                if attempt_number >= max_attempts:
                    raise RetryExhaustedError(
                        f"request {request_id!r} exhausted its retry budget "
                        f"({max_attempts} attempt(s)); last error: {error}"
                    ) from error
                continue
            except urllib.error.HTTPError as error:
                # Not retryable (module docstring): a real HTTP error
                # response, not a transient network failure.
                try:
                    detail = error.read()[:2048].decode("utf-8", "replace")
                except OSError:
                    detail = "<unreadable body>"
                raise TransportError(f"server returned HTTP {error.code} {error.reason}: {detail}") from error
            latency = time.monotonic() - started
            text, usage = _parse_response(raw)
            attempts.append(
                RequestAttempt(
                    request_id=current_id,
                    retry_of=retry_of,
                    attempt_number=attempt_number,
                    started_at=started_at,
                    latency_seconds=latency,
                    outcome="ok",
                    error=None,
                    audio_seconds=float(audio_seconds),
                )
            )
            return ModelResponse(request_id=current_id, text=text, usage=usage, attempts=tuple(attempts))
        # Unreachable: the loop above always either returns or raises on its
        # final iteration.
        raise RetryExhaustedError(f"request {request_id!r} exhausted its retry budget")
