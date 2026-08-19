"""The encode-warm contact: a minimal, generation-capped frozen-core
request whose reply TEXT is never read.

Registered discipline (``docs/readiness/2026-08-19-precomp-preregistration.md``
SS3/SS6): "Featcache warm pass: encode-only frozen-core contact per slice
(minimal generation cap, outputs NEVER read -- the contact exists solely to
populate the feature cache)... encode-warm outputs are never read
(fail-closed: the runner discards generation text unread, receipts carry
counts only)."

The proof this module offers is STRUCTURAL, not a promise recorded
alongside the code: :func:`encode_warm_slice` never binds
:attr:`~meeting_minutes_agent.client.transport.ModelResponse.text` to any
name, never passes it to ``len``/a hasher/a logger/a print -- read this
module's own source and the only thing extracted from the transport's
``ModelResponse`` is ``usage`` (the server's own out-of-band token-count
metadata, reported alongside the reply, never derived FROM the reply text
by this code) and the attempt-chain length. The ``text_discarded_unread``
field on the returned dict is a receipt-side marker of that fact for a
later reader who does not want to re-read this module's source to confirm
it; :func:`generation is capped <build_encode_warm_decoding_params>` to
``max_tokens=1`` by default so even the SERVER does the minimum possible
generation work -- the contact's only real purpose is to make the frozen
core's audio encoder run once over the slice's audio, warming the
mmproj-encoder feature cache (``meeting_minutes_agent.client.featcache``)
keyed on those exact bytes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from ..heads.transcribe_attribute import build_transcribe_only_request

if TYPE_CHECKING:
    from ..chunking.slicer import SliceManifest
    from ..client.receipts import FlightReceipt
    from ..client.transport import LlamaServerTransport
    from .budget import PrecompBudget

#: The registered default: "minimal generation cap" (prereg SS3) -- one
#: token, the smallest positive generation length ``max_tokens`` admits.
DEFAULT_ENCODE_WARM_MAX_TOKENS = 1


def build_encode_warm_decoding_params(
    max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS, *, extra: Mapping[str, object] | None = None
) -> dict[str, object]:
    """``decoding_params`` for one encode-warm request: whatever ``extra``
    a caller already built (e.g. from a
    :class:`~..heads.request.HeadRequest`'s own, normally-empty
    ``decoding_params``), with ``max_tokens`` forced onto it -- the
    generation-cap discipline this whole module exists to enforce is never
    optional, so it is applied here rather than left to a caller to
    remember."""

    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError(f"max_tokens must be a positive integer, got {max_tokens!r}")
    params = dict(extra or {})
    params["max_tokens"] = max_tokens
    return params


def encode_warm_slice(
    transport: "LlamaServerTransport",
    *,
    request_id: str,
    audio_path: Path,
    audio_seconds: float,
    max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS,
    flight_receipt: "FlightReceipt | None" = None,
) -> dict[str, Any]:
    """One encode-warm contact (module docstring). ``flight_receipt``, when
    given, has the request's full :class:`~..client.transport.ModelResponse`
    recorded onto it via :meth:`~..client.receipts.FlightReceipt.record` --
    that method itself only ever reads ``response.attempts``, never
    ``response.text`` (see its own source,
    :mod:`meeting_minutes_agent.client.receipts`), so wiring the transport
    ledger through does not compromise the discard-unread guarantee."""

    head_request = build_transcribe_only_request()
    kwargs = head_request.to_transport_kwargs(request_id=request_id, audio_path=audio_path, audio_seconds=audio_seconds)
    kwargs["decoding_params"] = build_encode_warm_decoding_params(max_tokens, extra=kwargs.get("decoding_params"))

    response = transport.request(**kwargs)
    if flight_receipt is not None:
        flight_receipt.record(response)

    # PROOF OF DISCARD: `response.text` is never bound to a name, never
    # passed to len()/a hash function/a logger, anywhere below this line or
    # above it in this function. Only `usage` (out-of-band token-count
    # metadata) and the attempt-chain length are extracted.
    return {
        "request_id": response.request_id,
        "usage": dict(response.usage),
        "n_attempts": len(response.attempts),
        "max_tokens": max_tokens,
        "text_discarded_unread": True,
    }


def encode_warm_manifest(
    transport: "LlamaServerTransport",
    manifest: "SliceManifest",
    base_dir: Path,
    *,
    request_id_prefix: str,
    max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS,
    budget: "PrecompBudget | None" = None,
    query_gpu: Callable[[], Mapping[str, float] | None] | None = None,
    flight_receipt: "FlightReceipt | None" = None,
    on_contact: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Encode-warm every slice in a frozen
    :class:`~..chunking.slicer.SliceManifest`, in index order.

    ``budget`` (a :class:`~.budget.PrecompBudget`), when given, is checked
    BEFORE every contact and recorded after -- pass the SAME instance
    across every meeting/manifest in a wave so the per-wave ceiling is
    enforced across the whole wave, never reset per meeting or per
    manifest. ``query_gpu`` is the same best-effort, advisory
    ``nvidia-smi``-snapshot callable
    :func:`meeting_minutes_agent.probes.diar_smoke.query_gpu_utilization_snapshot`
    already provides; ``None`` (the default) records zero GPU seconds per
    contact, exactly like that module's own ``estimate_gpu_seconds(wall,
    None)``."""

    from ..probes.diar_smoke import estimate_gpu_seconds

    outcomes: list[dict[str, Any]] = []
    for entry in manifest.entries:
        if budget is not None:
            budget.check_before_encode()
        audio_path = Path(base_dir) / entry.filename
        request_id = f"{request_id_prefix}-slice{entry.index:04d}"
        started = time.monotonic()
        outcome = encode_warm_slice(
            transport,
            request_id=request_id,
            audio_path=audio_path,
            audio_seconds=entry.end - entry.start,
            max_tokens=max_tokens,
            flight_receipt=flight_receipt,
        )
        wall_seconds = time.monotonic() - started
        snapshot = query_gpu() if query_gpu is not None else None
        gpu_seconds = estimate_gpu_seconds(wall_seconds, snapshot)
        outcome["wall_seconds"] = wall_seconds
        outcome["gpu_seconds_estimate"] = gpu_seconds
        if budget is not None:
            budget.record_encode(gpu_seconds=gpu_seconds, n_calls=1)
        if on_contact is not None:
            on_contact(outcome)
        outcomes.append(outcome)
    return outcomes


__all__ = [
    "DEFAULT_ENCODE_WARM_MAX_TOKENS",
    "build_encode_warm_decoding_params",
    "encode_warm_slice",
    "encode_warm_manifest",
]
