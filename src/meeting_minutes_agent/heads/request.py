"""``HeadRequest``: the shared shape every task head builds.

A head's job (component C6) is "a prompt template builder + a response
parser, no transport calls" (mission scope). ``HeadRequest`` is exactly the
prompt-building HALF of that: everything a head can decide on its own
(the pinned task instruction, the supplied-text parts -- supply block,
transcript/context text -- and any decoding params), tagged with the
template identity that produced it.

It is deliberately NOT the full transport call shape. Comparing against
:class:`meeting_minutes_agent.client.transport.LlamaServerTransport.request`'s
signature (``request_id, task_instruction, audio_path, audio_seconds,
supplied_text, decoding_params``): ``task_instruction``, ``supplied_text``
and ``decoding_params`` are exactly the three fields a head can determine;
``request_id``, ``audio_path`` and ``audio_seconds`` are per-invocation
transport/scheduling facts only a caller holding the actual audio chunk and
a request-id scheme can supply -- a head has neither. :meth:`HeadRequest.to_transport_kwargs`
is the seam: a caller (a future E7 controller) merges the two halves into
the exact kwargs the transport call (or the equivalent openJiuwen
``FrozenMeetingCore`` invocation inputs, which use the identical field
names) expects.

``template_id`` / ``template_sha256`` are metadata for a caller's OWN
request ledger / flight receipt -- they are never sent over the wire (the
transport payload has no such field); this is how "template_id + sha256 in
every built request's metadata" is satisfied without inventing a new wire
field the frozen core was never asked to understand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class HeadRequest:
    task_instruction: str
    supplied_text: tuple[str, ...] = ()
    decoding_params: Mapping[str, object] = field(default_factory=dict)
    template_id: str = ""
    template_sha256: str = ""

    def to_transport_kwargs(
        self,
        *,
        request_id: str,
        audio_path: Path,
        audio_seconds: float,
    ) -> dict[str, object]:
        """Merge this head-built content with the per-invocation
        transport fields a controller supplies at dispatch time, producing
        the exact kwargs
        :meth:`meeting_minutes_agent.client.transport.LlamaServerTransport.request`
        (equivalently, ``client.component.FrozenMeetingCore``'s invocation
        inputs) expects. ``template_id``/``template_sha256`` are NOT
        included -- they belong on the caller's own request-ledger record,
        never on the wire payload."""

        return {
            "request_id": request_id,
            "task_instruction": self.task_instruction,
            "audio_path": audio_path,
            "audio_seconds": audio_seconds,
            "supplied_text": self.supplied_text,
            "decoding_params": dict(self.decoding_params),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_instruction": self.task_instruction,
            "supplied_text": list(self.supplied_text),
            "decoding_params": dict(self.decoding_params),
            "template_id": self.template_id,
            "template_sha256": self.template_sha256,
        }


def build_supplied_text(*parts: str | None) -> tuple[str, ...]:
    """Filter out ``None``/empty parts, preserving order -- the small,
    repeated pattern every head uses to assemble ``supplied_text`` from an
    optional supply block plus an optional context/transcript block."""

    return tuple(p for p in parts if p)


__all__ = ["HeadRequest", "build_supplied_text"]
