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
from typing import Any, Iterable, Mapping


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


def _as_float(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def wave_usage_from_receipts(receipts: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Re-derive wave-cumulative usage, across this module's four ceiling
    axes, from a list of already-parsed per-meeting receipt dicts (any
    shape :func:`~.receipts.build_meeting_receipt` produces).

    This is the wave-1 operator wrapper's own reconciliation logic
    (``docs/checks/2026-08-19-precomp-wave1/budget_ledger.py::totals``),
    ported here verbatim rather than re-derived: every receipt on disk is
    summed regardless of its own ``ok`` flag. A meeting whose pipeline
    failed partway through (e.g. diarization completed, encode-warm later
    raised) still spent real diar/cutting GPU-and-wall time up to the point
    of failure -- :mod:`~.pipeline`'s ``FAILURE_STAGE_DEFAULTS`` already
    zero out whichever stage blocks never ran, so summing unconditionally
    never double-counts a stage that did not happen, and never
    under-counts one that did. A non-mapping entry (defensive only -- a
    caller is expected to have already parsed valid JSON) is skipped
    rather than raising.
    """

    used = {
        "diar_gpu_seconds_used": 0.0,
        "cutting_wall_seconds_used": 0.0,
        "encode_gpu_seconds_used": 0.0,
        "encode_calls_used": 0,
    }
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        diar = receipt.get("diar") or {}
        cutting = receipt.get("cutting") or {}
        encode = receipt.get("encode_warm") or {}
        used["diar_gpu_seconds_used"] += _as_float(diar.get("gpu_seconds_estimate"))
        used["cutting_wall_seconds_used"] += _as_float(cutting.get("wall_seconds"))
        used["encode_calls_used"] += int(_as_float(encode.get("n_calls")))
        for key in ("tool", "oracle"):
            for outcome in encode.get(key) or []:
                if isinstance(outcome, Mapping):
                    used["encode_gpu_seconds_used"] += _as_float(outcome.get("gpu_seconds_estimate"))
    return used


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

    # -- cross-process re-derivation ------------------------------------

    def precharge(self, receipts: Iterable[Mapping[str, Any]]) -> None:
        """Fold wave-cumulative usage already spent by ``receipts``
        (:func:`wave_usage_from_receipts`) into this budget's own counters,
        BEFORE this process's own loop runs any meeting.

        A wave runner builds one fresh, all-zero :class:`PrecompBudget` per
        process; without this, a meeting-by-meeting invocation loop (the
        shape the wave-1 yield protocol needed before this class carried a
        stop hook -- ``docs/checks/2026-08-19-precomp-wave1/README.md``'s
        "Deviation recorded for coordinator review") would silently reset
        the WAVE-level ceilings on every process start, because a fresh
        :class:`PrecompBudget` never sees what earlier receipts already
        spent. Calling this once, immediately after construction and
        before the first meeting, closes that hole natively: the shared
        in-process budget instance is then accurate for the rest of the
        run (every subsequent meeting's ``check_before_*`` call already
        sees the full wave history), so there is no need to re-scan the
        output directory before each individual meeting the way the
        operator wrapper's per-process ledger had to.

        Additive only -- never destructive, never resets a counter -- so it
        is safe even if usage was already recorded on this instance (e.g.
        in a test) before this call. Raises nothing itself; call
        ``check_before_diar``/``check_before_cutting``/``check_before_encode``
        (or :meth:`check_all`) afterward for the fail-closed refusal."""

        used = wave_usage_from_receipts(receipts)
        self.diar_gpu_seconds_used += used["diar_gpu_seconds_used"]
        self.cutting_wall_seconds_used += used["cutting_wall_seconds_used"]
        self.encode_gpu_seconds_used += used["encode_gpu_seconds_used"]
        self.encode_calls_used += int(used["encode_calls_used"])

    def check_all(self) -> None:
        """Run every per-axis ceiling check (diar, cutting, encode) this
        budget knows about, in the same order :func:`~.pipeline.run_meeting`
        applies them. Meant to run right after :meth:`precharge`: re-derived
        history that already meets or exceeds ANY axis then refuses before
        the wave attempts even a diarization contact for the next meeting,
        rather than only discovering the breach once that meeting's
        pipeline happens to reach the specific stage whose axis was
        exceeded. Raises :class:`PrecompBudgetExceeded` -- the first
        ceiling found already reached, if any; never returns a boolean a
        caller could ignore."""

        self.check_before_diar()
        self.check_before_cutting()
        self.check_before_encode()

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
    "wave_usage_from_receipts",
]
