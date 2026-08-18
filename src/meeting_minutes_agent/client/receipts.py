"""Flight receipts: server identity + request ledger + budget totals,
content-hashed via E1's :mod:`meeting_minutes_agent.runreceipt` helpers.

Lineage: reimplements, small, the shape of the SAEA study's
``core/session/receipt.py::SessionReceipt``/``ModelFileRef`` (server/model
identity as a plain, validated value type) and its adapter's
``cost_summary()`` (budget totals travelling with the receipt) --
studies/speech-aware-evidence-acquisition, umbrella commit range including
``12590d4``. No code is imported from that study; this module is
deliberately far smaller -- no gate/attempt-store binding, no umbrella-lock
verification, no liveness re-check against a running process. "Model file
paths+sha256 as configured" (this repository's own instruction) means
exactly that: :class:`ServerIdentity` is built from caller-supplied
configuration, never by probing a live server -- this repository's client
layer makes zero live model contact.

Content-hashing: everything that makes a receipt's content meaningful --
server identity, the full request ledger, budget totals -- is placed in the
``config`` mapping :func:`meeting_minutes_agent.runreceipt.build_run_receipt`
hashes (its ``extra`` field is deliberately unused here), so two receipts
built from identical inputs always hash identically and any difference in
the ledger or totals changes the hash.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..runreceipt import RunReceipt, build_run_receipt, write_run_receipt
from .budgets import CallBudget
from .transport import ModelResponse

_SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class ModelFileRef:
    """One model file's canonical path and sha256, as configured -- never
    verified against a live filesystem or server by this class itself (see
    :func:`hash_model_file` for the opt-in local-file hash a caller may use
    to build one of these before construction)."""

    path: str
    sha256: str

    def validate(self) -> "ModelFileRef":
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError(f"model file path must be a non-empty string, got {self.path!r}")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != _SHA256_HEX_LENGTH
            or any(c not in "0123456789abcdef" for c in self.sha256.lower())
        ):
            raise ValueError(f"model file {self.path!r} sha256 must be a 64-hex digest, got {self.sha256!r}")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class ServerIdentity:
    """The server's identity as configured for a flight: the endpoint plus
    the model file(s) it was launched with. Never independently re-verified
    against a live process by this module (module docstring)."""

    base_url: str
    model_files: tuple[ModelFileRef, ...]
    slots: int = 1

    def validate(self) -> "ServerIdentity":
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ValueError(f"base_url must be a non-empty string, got {self.base_url!r}")
        if not self.model_files:
            raise ValueError("ServerIdentity requires at least one model file")
        for ref in self.model_files:
            if not isinstance(ref, ModelFileRef):
                raise ValueError(f"model_files entries must be ModelFileRef, got {type(ref).__name__}")
            ref.validate()
        if isinstance(self.slots, bool) or not isinstance(self.slots, int) or self.slots <= 0:
            raise ValueError(f"slots must be a positive integer, got {self.slots!r}")
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "model_files": [ref.to_dict() for ref in self.model_files],
            "slots": self.slots,
        }


def hash_model_file(path: str | Path) -> str:
    """Sha256 hex digest of a local file's bytes -- an opt-in convenience
    for a caller that wants to build a :class:`ModelFileRef` from a real
    on-disk GGUF rather than hand-typing a hash. Purely local file I/O, not
    a model contact of any kind."""

    resolved = Path(path)
    if not resolved.is_file():
        raise ValueError(f"cannot hash model file: not a file: {resolved}")
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _attempt_to_dict(response_request_id: str, attempt) -> dict[str, object]:
    entry = attempt.as_json()
    entry["response_of"] = response_request_id
    return entry


class FlightReceipt:
    """Accumulates one flight's request ledger against a fixed server
    identity and budget, and produces a content-hashed
    :class:`~meeting_minutes_agent.runreceipt.RunReceipt` on demand.

    ``record`` is the only mutator; a caller feeds it every
    :class:`~meeting_minutes_agent.client.transport.ModelResponse`
    :meth:`~meeting_minutes_agent.client.transport.LlamaServerTransport.request`
    returns (successful or not -- a :class:`~.transport.RetryExhaustedError`
    carries no response to record, but every attempt up to that failure is
    still visible in whatever the caller separately logs; this class records
    completed responses, each already carrying its own full attempt chain
    per :class:`~.transport.ModelResponse.attempts`).
    """

    def __init__(self, server_identity: ServerIdentity, budget: CallBudget) -> None:
        self.server_identity = server_identity.validate()
        self.budget = budget
        self._entries: list[dict[str, object]] = []

    def record(self, response: ModelResponse) -> None:
        for attempt in response.attempts:
            self._entries.append(_attempt_to_dict(response.request_id, attempt))

    @property
    def entries(self) -> tuple[dict[str, object], ...]:
        return tuple(self._entries)

    def _config(self) -> dict[str, object]:
        return {
            "server_identity": self.server_identity.to_dict(),
            "request_ledger": [dict(entry) for entry in self._entries],
            "budget_totals": dict(self.budget.totals),
        }

    def build(self, *, repo_root: Path | str | None = None, run_id: str | None = None) -> RunReceipt:
        """Build (without writing) the content-hashed receipt. Two
        :class:`FlightReceipt` instances that recorded identical responses
        against identical server identities/budget totals always produce
        the same ``config_hash``, regardless of ``run_id``/timestamp."""

        return build_run_receipt(self._config(), repo_root=repo_root, run_id=run_id)

    def write(
        self, path: Path | str, *, repo_root: Path | str | None = None, run_id: str | None = None
    ) -> Path:
        """Build and write the receipt via E1's ``write_run_receipt`` --
        same atomic-enough (parent-mkdir, pretty JSON) behaviour every other
        run receipt in this repository gets."""

        return write_run_receipt(path, self._config(), repo_root=repo_root, run_id=run_id)
