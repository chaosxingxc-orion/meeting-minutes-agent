"""Hard, client-side call-count and audio-seconds budgets.

Lineage: reimplements, small, the metering-atomicity lesson of the SAEA
study's ``core/model/adapter.py::FrozenCoreAdapter`` (studies/speech-aware-
evidence-acquisition, umbrella commit range including ``12590d4``): "the
lock makes [check -> record] atomic... The transport call itself stays
OUTSIDE the lock: holding it across a multi-second model request would
serialize the very concurrency batching exists to provide." This module
keeps exactly that shape -- one lock across check-and-record, nothing else
-- and drops everything SAEA's version carries that does not apply to this
repository: no cross-process attempt store, no sibling-attempt re-read, no
umbrella run-id plan. A budget here is purely in-process and per
:class:`CallBudget` instance.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

_AUDIO_SECONDS_ABS_TOLERANCE = 1e-9


class BudgetExceeded(RuntimeError):
    """Fail-closed refusal: raised by :meth:`CallBudget.reserve` when either
    cap would be crossed. Nothing is mutated when this is raised -- a
    refused reservation is never partially recorded."""


@dataclass(frozen=True)
class BudgetLimits:
    max_calls: int
    max_audio_seconds: float

    def validate(self) -> "BudgetLimits":
        if isinstance(self.max_calls, bool) or not isinstance(self.max_calls, int) or self.max_calls <= 0:
            raise ValueError(f"max_calls must be a positive integer, got {self.max_calls!r}")
        if (
            isinstance(self.max_audio_seconds, bool)
            or not isinstance(self.max_audio_seconds, (int, float))
            or not math.isfinite(self.max_audio_seconds)
            or self.max_audio_seconds <= 0
        ):
            raise ValueError(
                f"max_audio_seconds must be a finite positive number, got {self.max_audio_seconds!r}"
            )
        return self


class CallBudget:
    """Thread-safe hard cap on call count and cumulative audio seconds.

    :meth:`reserve` is the only mutator: it atomically checks both caps and,
    only if both hold, records the reservation -- one lock across
    check-and-record, exactly the SAEA metering lesson (module docstring).
    The caller must always perform the actual network/transport call
    *outside* this method (and outside holding any lock of its own on this
    object): :meth:`reserve` returns before the request is sent, precisely
    so a multi-second call never serializes other threads' reservations.
    """

    def __init__(self, limits: BudgetLimits) -> None:
        self._limits = limits.validate()
        self._lock = threading.Lock()
        self._calls_used = 0
        self._audio_seconds_used = 0.0

    @property
    def limits(self) -> BudgetLimits:
        return self._limits

    def reserve(self, audio_seconds: float) -> None:
        """Reserve budget for one call carrying ``audio_seconds`` of audio.
        Raises :class:`BudgetExceeded` (fail-closed, no partial mutation) if
        either the call-count or audio-seconds cap would be crossed."""

        if (
            isinstance(audio_seconds, bool)
            or not isinstance(audio_seconds, (int, float))
            or not math.isfinite(audio_seconds)
            or audio_seconds < 0
        ):
            raise ValueError(f"audio_seconds must be a finite, non-negative number, got {audio_seconds!r}")
        with self._lock:
            if self._calls_used + 1 > self._limits.max_calls:
                raise BudgetExceeded(
                    f"call budget exhausted: {self._limits.max_calls} calls allowed, "
                    f"{self._calls_used} already used"
                )
            proposed_audio_seconds = self._audio_seconds_used + float(audio_seconds)
            if proposed_audio_seconds > self._limits.max_audio_seconds and not math.isclose(
                proposed_audio_seconds,
                self._limits.max_audio_seconds,
                rel_tol=0.0,
                abs_tol=_AUDIO_SECONDS_ABS_TOLERANCE,
            ):
                raise BudgetExceeded(
                    f"audio budget exhausted: {self._limits.max_audio_seconds} seconds allowed, "
                    f"{self._audio_seconds_used} already used, {audio_seconds} requested"
                )
            self._calls_used += 1
            # Acceptance tolerance only: retain the hard registered cap in
            # receipts instead of recording an IEEE-754 residue above it.
            self._audio_seconds_used = min(proposed_audio_seconds, self._limits.max_audio_seconds)

    @property
    def totals(self) -> dict[str, object]:
        """A JSON-safe snapshot, read under the same lock as ``reserve`` so
        it never observes a torn intermediate state. Consumed by
        :mod:`.receipts` for the flight receipt's budget-totals block."""

        with self._lock:
            return {
                "calls_used": self._calls_used,
                "audio_seconds_used": self._audio_seconds_used,
                "max_calls": self._limits.max_calls,
                "max_audio_seconds": self._limits.max_audio_seconds,
            }
