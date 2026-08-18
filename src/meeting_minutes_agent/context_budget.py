"""Plan-time serving-context budget arithmetic.

Owner G1 lock item (c), ``docs/readiness/2026-08-18-chunk-slice-granularity-
analysis.md`` SS2-SS5. Every number here is either read out of the pinned
llama.cpp source or a flown SAEA measurement (the analysis document's own
provenance) -- nothing here is invented; this module only turns those
numbers into a reusable, config-value-driven assertion.

Two facts this module exists to encode as CODE, not just as a document
comment, because getting either wrong makes the two G1-blocking defects the
2026-08-18 mission was built to fix:

1. **13 audio tokens per second, floor-quantized** (``clip.cpp``
   ``PROJECTOR_TYPE_QWEN3A``: 100 mel frames -> 13 tokens; 100 mel frames =
   1.00 s at the flown 16 kHz / hop-160 audio front end).
2. **The per-request context is ``n_ctx / n_parallel``, never the whole
   ``-c`` value.** The flown server runs ``-c 49152 -np 4``, so the REAL
   per-slot budget is 12,288 tokens -- ``SlotContextConfig`` never lets a
   caller silently default to 49,152; ``slot_context_tokens`` is always an
   explicit, declared field (analysis SS2, "make slot context a config
   value, never assume 49,152").

Overrun at the real server is a HARD REFUSAL, not graceful truncation
(``ctx_shift`` is force-disabled under mmproj): an oversized request gets
``ERROR_TYPE_EXCEED_CONTEXT_SIZE`` and the slot is released. So the only
sound place to catch an oversized plan is PLAN TIME, before any bytes are
sent -- :func:`assert_fits` is that check, and every caller that plans a
request the frozen core will see (:mod:`.chunking.planner`'s single_pass
gate, :mod:`.chunking.slicer`'s per-slice plan) must run it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# -- measured constants (analysis SS1-SS2; never re-derive these from
#    memory -- they are read out of the pinned llama.cpp source / flown
#    receipts named in the analysis document's own provenance block) -------
AUDIO_TOKENS_PER_SECOND = 13
DEFAULT_N_CTX_TOTAL = 49152
DEFAULT_N_PARALLEL = 4
DEFAULT_SLOT_CONTEXT_TOKENS = DEFAULT_N_CTX_TOTAL // DEFAULT_N_PARALLEL  # 12,288 -- NOT 49,152

# -- planning estimates (analysis SS2: "not load-bearing... a 2x error in
#    the reserves moves the feasible ceiling by under 8%" -- audio tokens
#    dominate at 13/s) ------------------------------------------------------
DEFAULT_FIXED_RESERVE_TOKENS = 950  # meeting LISTEN: instruction + supply + tail, planning estimate
DEFAULT_COMPLETION_TOKENS_PER_AUDIO_SECOND = 4.0  # transcription + speaker attribution, planning upper bound
DEFAULT_CONTEXT_SAFETY_MARGIN = 0.9


class SlotContextExceededError(ValueError):
    """A planned request's estimated prompt+completion token need exceeds
    the safety-margined per-slot context. Raised at PLAN TIME, never at
    request time (module docstring): the real server hard-refuses an
    oversized request rather than truncating it, so this exception must
    fire before any transport call is attempted."""


@dataclass(frozen=True)
class SlotContextConfig:
    """The per-slot serving-context budget a plan is checked against.

    Every field is a DECLARED config value, never a hard-coded assumption
    -- in particular ``slot_context_tokens`` defaults to 12,288 (the flown
    ``-c 49152 -np 4`` config's ``n_ctx / n_parallel``), never the whole
    49,152 (module docstring). Raising ``-np`` beyond 4 halves the slot
    again; re-derive rather than reuse this default if the serving config
    changes (analysis SS8.4).
    """

    slot_context_tokens: int = DEFAULT_SLOT_CONTEXT_TOKENS
    audio_tokens_per_second: int = AUDIO_TOKENS_PER_SECOND
    fixed_reserve_tokens: int = DEFAULT_FIXED_RESERVE_TOKENS
    completion_tokens_per_audio_second: float = DEFAULT_COMPLETION_TOKENS_PER_AUDIO_SECOND
    safety_margin: float = DEFAULT_CONTEXT_SAFETY_MARGIN

    def validate(self) -> "SlotContextConfig":
        if (
            isinstance(self.slot_context_tokens, bool)
            or not isinstance(self.slot_context_tokens, int)
            or self.slot_context_tokens <= 0
        ):
            raise ValueError(f"slot_context_tokens must be a positive integer, got {self.slot_context_tokens!r}")
        if (
            isinstance(self.audio_tokens_per_second, bool)
            or not isinstance(self.audio_tokens_per_second, int)
            or self.audio_tokens_per_second <= 0
        ):
            raise ValueError(
                f"audio_tokens_per_second must be a positive integer, got {self.audio_tokens_per_second!r}"
            )
        if (
            isinstance(self.fixed_reserve_tokens, bool)
            or not isinstance(self.fixed_reserve_tokens, int)
            or self.fixed_reserve_tokens < 0
        ):
            raise ValueError(
                f"fixed_reserve_tokens must be a non-negative integer, got {self.fixed_reserve_tokens!r}"
            )
        if (
            isinstance(self.completion_tokens_per_audio_second, bool)
            or not isinstance(self.completion_tokens_per_audio_second, (int, float))
            or not math.isfinite(self.completion_tokens_per_audio_second)
            or self.completion_tokens_per_audio_second < 0
        ):
            raise ValueError(
                "completion_tokens_per_audio_second must be a finite, non-negative number, got "
                f"{self.completion_tokens_per_audio_second!r}"
            )
        if (
            isinstance(self.safety_margin, bool)
            or not isinstance(self.safety_margin, (int, float))
            or not math.isfinite(self.safety_margin)
            or not (0.0 < self.safety_margin <= 1.0)
        ):
            raise ValueError(f"safety_margin must be in (0, 1], got {self.safety_margin!r}")
        return self

    def required_tokens(self, audio_seconds: float) -> float:
        """Estimated prompt+completion token need for ``audio_seconds`` of
        audio: floor-quantized audio tokens (module docstring, "13 tokens
        per audio-second... floor-quantized to whole seconds") + the fixed
        text reserve + an audio-proportional completion estimate."""

        if (
            isinstance(audio_seconds, bool)
            or not isinstance(audio_seconds, (int, float))
            or not math.isfinite(audio_seconds)
            or audio_seconds < 0
        ):
            raise ValueError(f"audio_seconds must be a finite, non-negative number, got {audio_seconds!r}")
        audio_tokens = math.floor(audio_seconds) * self.audio_tokens_per_second
        completion_tokens = self.completion_tokens_per_audio_second * audio_seconds
        return audio_tokens + self.fixed_reserve_tokens + completion_tokens

    def budget_tokens(self) -> float:
        """The safety-margined token ceiling a plan must fit under."""

        return self.safety_margin * self.slot_context_tokens

    def fits(self, audio_seconds: float) -> bool:
        return self.required_tokens(audio_seconds) <= self.budget_tokens()

    def max_feasible_audio_seconds(self) -> float:
        """A conservative (never-optimistic) closed-form estimate of the
        longest audio clip that fits, ignoring the small floor-quantization
        saving (``floor(w) <= w``, so this UNDER-estimates the true ceiling
        by at most one second's worth of tokens) -- informational only;
        :meth:`fits`/:func:`assert_fits` are the exact, load-bearing check."""

        budget = self.budget_tokens()
        rate = self.audio_tokens_per_second + self.completion_tokens_per_audio_second
        feasible = (budget - self.fixed_reserve_tokens) / rate
        return max(feasible, 0.0)


def assert_fits(
    audio_seconds: float,
    config: SlotContextConfig = SlotContextConfig(),
    *,
    label: str = "planned request",
) -> None:
    """The plan-time context assertion every planned request must pass
    (17-item change list item 5). Raises :class:`SlotContextExceededError`
    -- fail-closed, at plan time -- if ``audio_seconds`` would not fit
    ``config``'s safety-margined slot budget."""

    config = config.validate()
    if not config.fits(audio_seconds):
        required = config.required_tokens(audio_seconds)
        budget = config.budget_tokens()
        raise SlotContextExceededError(
            f"{label}: {audio_seconds}s of audio needs an estimated {required:.0f} tokens "
            f"(floor({audio_seconds})x{config.audio_tokens_per_second} audio + "
            f"{config.fixed_reserve_tokens} fixed reserve + "
            f"{config.completion_tokens_per_audio_second}x{audio_seconds} completion), which "
            f"exceeds the {config.safety_margin:.0%}-margined slot budget of {budget:.0f} tokens "
            f"(slot_context_tokens={config.slot_context_tokens}). The server hard-refuses an "
            "oversized request (ERROR_TYPE_EXCEED_CONTEXT_SIZE) rather than truncating it -- this "
            "must be caught at plan time, not request time."
        )


__all__ = [
    "AUDIO_TOKENS_PER_SECOND",
    "DEFAULT_N_CTX_TOTAL",
    "DEFAULT_N_PARALLEL",
    "DEFAULT_SLOT_CONTEXT_TOKENS",
    "DEFAULT_FIXED_RESERVE_TOKENS",
    "DEFAULT_COMPLETION_TOKENS_PER_AUDIO_SECOND",
    "DEFAULT_CONTEXT_SAFETY_MARGIN",
    "SlotContextExceededError",
    "SlotContextConfig",
    "assert_fits",
]
