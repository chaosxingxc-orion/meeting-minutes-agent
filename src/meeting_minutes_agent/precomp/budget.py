"""Per-wave PRECOMP budget ceilings + the fail-closed guard.

Registered ceilings (``docs/readiness/2026-08-19-precomp-preregistration.md``
SS4): "Wave-1: <=0.5 GPU-h diar + <=2.0 GPU-h encode-warm + <=2 h wall CPU
cutting; <=900 encode calls. Wave-2: <=2.0 GPU-h diar + <=8.0 GPU-h
encode-warm (night window), resumable at meeting granularity; <=4,500
encode calls." Wave-2 carries no registered CPU-cutting wall-hour ceiling
(:data:`WAVE_2_CEILINGS.max_cutting_wall_hours` is ``None``, meaning
unchecked), matching the registration's silence there.

Same post-hoc "check before, record after" shape
:class:`meeting_minutes_agent.probes.diar_smoke.SmokeBudget` already uses,
for the identical reason its own docstring gives: none of a diarization
tool's wall time, a CPU slice-cutting pass's wall time, or a GPU-hour
estimate is knowable in advance the way an LLM request's ``audio_seconds``
is (:class:`meeting_minutes_agent.client.budgets.CallBudget`'s own
pre-reservation model does not apply here either). This class is the ONE
PRECOMP-specific ceiling on top of that transport-level ``CallBudget``: a
real flight builds both -- ``CallBudget`` guards the transport layer's own
call-count/audio-seconds caps per HTTP request, :class:`PrecompBudget`
guards the four PRECOMP-specific axes (diar GPU-hours, encode GPU-hours,
cutting wall-hours, encode call count) the registration actually ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PrecompBudgetExceeded(RuntimeError):
    """Fail-closed refusal: a PRECOMP-specific ceiling (diar GPU-hours,
    encode GPU-hours, cutting wall-hours, or encode call count) would
    already be exceeded by the NEXT contact/step. Checked BEFORE every
    diar contact, cutting pass, and encode-warm contact against usage
    already recorded from completed ones -- a post-hoc guard, never a
    prediction of the next step's own cost. Raised, never returned as a
    boolean a caller could ignore; the wave runner catches this ONE
    exception type at the outer loop to stop the wave and still write
    whatever already completed (mirrors
    ``scripts/launch_diar_smoke.py``'s own ``SmokeBudgetExceeded``
    handling)."""


@dataclass(frozen=True)
class WaveCeilings:
    """One wave's registered ceilings (module docstring). ``wave`` is
    carried on the value itself so a receipt can name which ceilings it was
    checked against without a separate lookup."""

    wave: int
    max_diar_gpu_hours: float
    max_encode_gpu_hours: float
    max_cutting_wall_hours: float | None
    max_encode_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "wave": self.wave,
            "max_diar_gpu_hours": self.max_diar_gpu_hours,
            "max_encode_gpu_hours": self.max_encode_gpu_hours,
            "max_cutting_wall_hours": self.max_cutting_wall_hours,
            "max_encode_calls": self.max_encode_calls,
        }


#: Registered ceilings, verbatim (module docstring).
WAVE_1_CEILINGS = WaveCeilings(
    wave=1, max_diar_gpu_hours=0.5, max_encode_gpu_hours=2.0, max_cutting_wall_hours=2.0, max_encode_calls=900
)
WAVE_2_CEILINGS = WaveCeilings(
    wave=2, max_diar_gpu_hours=2.0, max_encode_gpu_hours=8.0, max_cutting_wall_hours=None, max_encode_calls=4500
)
_CEILINGS_BY_WAVE: dict[int, WaveCeilings] = {1: WAVE_1_CEILINGS, 2: WAVE_2_CEILINGS}


def ceilings_for_wave(wave: int) -> WaveCeilings:
    """The registered :class:`WaveCeilings` for ``wave`` (1 or 2). Raises
    :class:`KeyError` for any other value -- there is no default wave's
    ceilings to silently fall back to."""

    try:
        return _CEILINGS_BY_WAVE[wave]
    except KeyError:
        raise KeyError(f"no registered ceilings for PRECOMP wave {wave!r}; expected one of {sorted(_CEILINGS_BY_WAVE)}") from None


@dataclass
class PrecompBudget:
    """Cumulative usage across a wave, checked before every step against
    ``ceilings`` (module docstring). One instance is shared across every
    meeting a wave runner processes -- the ceilings are WAVE-level, never
    reset per meeting."""

    ceilings: WaveCeilings
    diar_gpu_seconds_used: float = 0.0
    encode_gpu_seconds_used: float = 0.0
    cutting_wall_seconds_used: float = 0.0
    encode_calls_used: int = 0

    # -- diarization ----------------------------------------------------

    def check_before_diar(self) -> None:
        max_seconds = self.ceilings.max_diar_gpu_hours * 3600.0
        if self.diar_gpu_seconds_used >= max_seconds:
            raise PrecompBudgetExceeded(
                f"wave {self.ceilings.wave} diar GPU-hour ceiling already reached: "
                f"{self.diar_gpu_seconds_used:.1f}s used of {max_seconds:.1f}s allowed -- "
                "refusing to start another diarization contact"
            )

    def record_diar(self, gpu_seconds: float) -> None:
        self.diar_gpu_seconds_used += max(0.0, gpu_seconds)

    # -- CPU slice cutting ------------------------------------------------

    def check_before_cutting(self) -> None:
        if self.ceilings.max_cutting_wall_hours is None:
            return
        max_seconds = self.ceilings.max_cutting_wall_hours * 3600.0
        if self.cutting_wall_seconds_used >= max_seconds:
            raise PrecompBudgetExceeded(
                f"wave {self.ceilings.wave} CPU-cutting wall-hour ceiling already reached: "
                f"{self.cutting_wall_seconds_used:.1f}s used of {max_seconds:.1f}s allowed -- "
                "refusing to start another cutting pass"
            )

    def record_cutting(self, wall_seconds: float) -> None:
        self.cutting_wall_seconds_used += max(0.0, wall_seconds)

    # -- encode-warm ------------------------------------------------------

    def check_before_encode(self) -> None:
        max_gpu_seconds = self.ceilings.max_encode_gpu_hours * 3600.0
        if self.encode_gpu_seconds_used >= max_gpu_seconds:
            raise PrecompBudgetExceeded(
                f"wave {self.ceilings.wave} encode-warm GPU-hour ceiling already reached: "
                f"{self.encode_gpu_seconds_used:.1f}s used of {max_gpu_seconds:.1f}s allowed -- "
                "refusing to start another encode-warm contact"
            )
        if self.encode_calls_used >= self.ceilings.max_encode_calls:
            raise PrecompBudgetExceeded(
                f"wave {self.ceilings.wave} encode-warm call-count ceiling already reached: "
                f"{self.encode_calls_used} calls used of {self.ceilings.max_encode_calls} allowed -- "
                "refusing to start another encode-warm contact"
            )

    def record_encode(self, *, gpu_seconds: float, n_calls: int = 1) -> None:
        self.encode_gpu_seconds_used += max(0.0, gpu_seconds)
        self.encode_calls_used += max(0, n_calls)

    # -- reporting ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "ceilings": self.ceilings.to_dict(),
            "diar_gpu_seconds_used": self.diar_gpu_seconds_used,
            "encode_gpu_seconds_used": self.encode_gpu_seconds_used,
            "cutting_wall_seconds_used": self.cutting_wall_seconds_used,
            "encode_calls_used": self.encode_calls_used,
        }


__all__ = [
    "PrecompBudgetExceeded",
    "WaveCeilings",
    "WAVE_1_CEILINGS",
    "WAVE_2_CEILINGS",
    "ceilings_for_wave",
    "PrecompBudget",
]
