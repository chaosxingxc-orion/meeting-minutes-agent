"""E6 -- the core client layer: a lean llama-server HTTP client, hard
client-side budgets, content-hashed flight receipts, per-dataset feature-
cache directory routing, and the openJiuwen single-door component wrapper.

Zero live model contact in this repository's own test suite: every test
drives :class:`.transport.LlamaServerTransport` against a mock HTTP server
or an injected fake ``post`` callable, never a real ``llama-server``
process. No GPU, no paid API spend (program invariant).

Lineage (recorded cross-repo import; CLAUDE.md "Research object" /
2026-08-17 owner decision -- the second such import after
``instrumentation.copy_rate``, the first): this package reimplements, small
and standalone, the *shape* of the speech-aware-evidence-acquisition
study's ``core/model`` transport/adapter and its ``reproduction/ojw`` single-
door component (studies/speech-aware-evidence-acquisition, umbrella commit
range including ``12590d4``) -- no code is imported from that study. Every
module below cites the exact SAEA file its shape reuses in its own
docstring, and this repository deliberately drops the SAEA apparatus that
does not apply here (no ``ExecutionPlan``/gate/attempt-store/umbrella-lock
metering -- this is a "fresh start" repository per its own CLAUDE.md, not
bound by that study's exposure apparatus or experiment ladder).

Import discipline: this ``__init__`` module and every sibling except
``component.py`` import no openjiuwen. ``component.py`` imports openjiuwen
at module level and must be imported explicitly by a caller that needs it
(``from meeting_minutes_agent.client.component import FrozenMeetingCore``)
-- never through this package's own ``__init__``, so the rest of this
package (and the whole repository test suite) stays importable with
openjiuwen absent (zero-dependency gate: openjiuwen never enters
``pyproject.toml``).
"""

from __future__ import annotations

from .budgets import BudgetExceeded, BudgetLimits, CallBudget
from .featcache import FeatCacheError, campaign_cache_dir, server_env
from .receipts import FlightReceipt, ModelFileRef, ServerIdentity, hash_model_file
from .transport import (
    LlamaServerTransport,
    ModelResponse,
    RequestAttempt,
    RetryExhaustedError,
    TransportConfig,
    TransportError,
    build_request_payload,
)

__all__ = [
    "BudgetExceeded",
    "BudgetLimits",
    "CallBudget",
    "FeatCacheError",
    "campaign_cache_dir",
    "server_env",
    "FlightReceipt",
    "ModelFileRef",
    "ServerIdentity",
    "hash_model_file",
    "LlamaServerTransport",
    "ModelResponse",
    "RequestAttempt",
    "RetryExhaustedError",
    "TransportConfig",
    "TransportError",
    "build_request_payload",
]
