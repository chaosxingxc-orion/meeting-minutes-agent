"""The DiarizationBackend seam (deferred change, ``docs/plans/2026-08-18-
agent-backbone-and-layout.md`` SS5.2 DIARIZE pre-stage: "a frozen, pinned,
logged TOOL-level pre-pass producing speaker-attributed spans... answer
authority stays with the core; the tool only segments").

Turn-aware slice packing (:mod:`.slicer`) needs a speaker-turn table before
it can run. Until this module existed, the only source wired in anywhere in
this repository was the NXT gold layer, reached DIRECTLY
(:func:`meeting_minutes_agent.chunking.adapters.turn_table_from_resolved_meeting`
+ :func:`~.adapters.turn_table_provenance` passed straight into
:func:`~.slicer.build_turn_aware_slice_plan`). This module names that
dependency as an explicit seam -- :class:`DiarizationBackend` -- so a pinned
tool diarizer can be swapped in later without touching the slicer or the
harness again.

Two implementations ship today:

- :class:`NxtOracleDiarization` -- wraps the existing NXT gold-turn path
  (:mod:`.adapters`), tagged :data:`~.leakage.BoundaryProvenance.ORACLE_TURN`
  (Tier-M1). This is the G1 oracle-turn CEILING arm
  (``docs/readiness/2026-08-18-g1-preregistration-draft.md`` SS2, Z-turn's
  ceiling tier: "oracle-diar turns on AMI = the ceiling"). Gold usage stays
  on the scoring/ceiling side of the M0/M1 gate (:mod:`.leakage`), never a
  silent runtime default: the ``ORACLE_TURN`` tag this backend returns is
  the SAME tag :func:`~.adapters.turn_table_provenance` already returns, so
  it is caught by the exact same
  :func:`~.leakage.assert_runtime_admissible` gate
  :func:`~.slicer.build_turn_aware_slice_plan` already enforces at the
  slicer boundary -- this seam sits one layer further out, ahead of that
  gate, never around it.
- :class:`PinnedToolDiarization` -- an honest stub. The deployable
  diarization tool (pyannote.audio vs NeMo vs wespeaker, per the backbone
  doc SS5.2's open decision: "evaluate... under {no paid, pinnable revision,
  license-compatible, WSL-venv installable with owner approval}") is not yet
  selected or pinned. Calling it raises
  :class:`DiarizationToolNotPinnedError` naming
  ``docs/plans/2026-08-18-diarization-tool-selection.md`` rather than
  guessing at a shape nothing has chosen yet -- the same honest-stub
  discipline :class:`meeting_minutes_agent.controller.dispatcher.
  TaskDispatchNotImplementedError` already uses for ``re_listen``/
  ``answer_question``.

:func:`build_turn_aware_slice_plan_from_backend` is the generic (corpus-
agnostic) seam-threading entry point; :func:`build_turn_aware_slice_plan_for_resolved_meeting`
is the NXT-specific convenience wrapper whose ``backend`` parameter DEFAULTS
to :class:`NxtOracleDiarization` wrapping the meeting handed in, so every
existing caller that relied on the direct NXT-turn-table path keeps
producing an identical :class:`~.slicer.SlicePlan` without passing anything
new -- "default remains the oracle backend" (task instruction) is this
default, not a hidden fallback inside :class:`DiarizationBackend` itself
(a truly generic backend-consuming function never hardcodes a corpus
default; only the NXT-specific wrapper does).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from .constants import (
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from .leakage import BoundaryProvenance
from .slicer import SlicePlan, TurnSpan, build_turn_aware_slice_plan

if TYPE_CHECKING:
    from ..corpora.nxt.models import ResolvedMeeting

__all__ = [
    "DiarizationResult",
    "DiarizationBackend",
    "NxtOracleDiarization",
    "DiarizationToolNotPinnedError",
    "PinnedToolDiarization",
    "build_turn_aware_slice_plan_from_backend",
    "build_turn_aware_slice_plan_for_resolved_meeting",
]


@dataclass(frozen=True)
class DiarizationResult:
    """One backend call's output: a speaker-turn table plus the
    :class:`~.leakage.BoundaryProvenance` tag that decides whether the M0/M1
    gate (:mod:`.leakage`) will admit it into a runtime plan by default."""

    turns: tuple[TurnSpan, ...]
    provenance: BoundaryProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "turns": [t.to_dict() for t in self.turns],
            "provenance": self.provenance.value,
        }


class DiarizationBackend(ABC):
    """The seam. ``diarize`` never touches the frozen core -- a diarizer is
    a frozen, pinned, LOGGED tool-level pre-pass (module docstring); final
    answer authority stays with the core regardless of which backend is in
    force -- and never mutates its inputs."""

    @abstractmethod
    def diarize(self, meeting_id: str, audio_ref: Path | str | None) -> DiarizationResult:
        """Return the speaker-turn table (+ provenance tag) for
        ``meeting_id``. ``audio_ref`` is the audio this backend would
        diarize a real tool backend needs it; an oracle backend built over
        a specific ``ResolvedMeeting`` ignores it -- the gold layer is keyed
        on ``meeting_id`` alone, not on any audio file."""


class NxtOracleDiarization(DiarizationBackend):
    """Wraps the existing NXT gold-turn path (:mod:`.adapters`), explicitly
    tagged oracle. Constructed over either ONE ``ResolvedMeeting`` (the
    common case: a caller already holds the meeting it wants diarized), a
    ``{meeting_id: ResolvedMeeting}`` mapping, or a ``meeting_id ->
    ResolvedMeeting`` resolver callable -- all three shapes are accepted so
    this backend can sit behind either a single-meeting harness call or a
    multi-meeting campaign driver without a second class."""

    def __init__(
        self,
        resolved_meetings: "ResolvedMeeting | Mapping[str, ResolvedMeeting] | Callable[[str], ResolvedMeeting]",
    ) -> None:
        self._source = resolved_meetings

    def _resolve(self, meeting_id: str) -> "ResolvedMeeting":
        source = self._source
        if isinstance(source, Mapping):
            try:
                return source[meeting_id]
            except KeyError as error:
                raise KeyError(
                    f"NxtOracleDiarization has no ResolvedMeeting registered for "
                    f"meeting_id={meeting_id!r}"
                ) from error
        if callable(source):
            return source(meeting_id)
        # A single ResolvedMeeting handed in directly -- refuse a mismatched
        # meeting_id rather than silently diarizing the wrong meeting.
        source_meeting_id = getattr(source, "meeting_id", None)
        if source_meeting_id != meeting_id:
            raise KeyError(
                f"NxtOracleDiarization was constructed for meeting_id={source_meeting_id!r}, cannot "
                f"diarize a different meeting_id={meeting_id!r}"
            )
        return source

    def diarize(self, meeting_id: str, audio_ref: Path | str | None = None) -> DiarizationResult:
        # Lazy import (module docstring: this module must not force-import
        # .adapters at module scope -- .adapters itself never imports THIS
        # module, so there is no cycle to break, only the repository's
        # standing convention of keeping cross-submodule imports lazy at the
        # call site that actually needs them).
        from .adapters import turn_table_from_resolved_meeting, turn_table_provenance

        resolved = self._resolve(meeting_id)
        turns = turn_table_from_resolved_meeting(resolved)
        provenance = turn_table_provenance()  # always ORACLE_TURN -- M1, ceiling-arm only
        return DiarizationResult(turns=turns, provenance=provenance)


class DiarizationToolNotPinnedError(NotImplementedError):
    """Raised by :class:`PinnedToolDiarization` -- the deployable
    diarization tool has not been selected or pinned yet (backbone doc
    SS5.2's open decision between pyannote.audio / NeMo / wespeaker).
    Honest-stub discipline: name the precondition, never guess at a request
    shape nothing has chosen yet."""


class PinnedToolDiarization(DiarizationBackend):
    """Stub for the eventual deployable (Tier-M0, ``TOOL_DIAR``) diarization
    tool. There is nothing to implement here until
    ``docs/plans/2026-08-18-diarization-tool-selection.md`` resolves the
    tool choice; every call raises :class:`DiarizationToolNotPinnedError`
    naming that ticket rather than shipping a fabricated turn table."""

    def diarize(self, meeting_id: str, audio_ref: Path | str | None) -> DiarizationResult:
        raise DiarizationToolNotPinnedError(
            "PinnedToolDiarization.diarize: no deployable diarization tool is selected or pinned "
            "yet -- see docs/plans/2026-08-18-diarization-tool-selection.md (the open decision "
            "between pyannote.audio / NeMo / wespeaker recorded in "
            "docs/plans/2026-08-18-agent-backbone-and-layout.md SS5.2). This backend cannot "
            f"diarize meeting_id={meeting_id!r} until that ticket lands a pinned tool."
        )


def build_turn_aware_slice_plan_from_backend(
    meeting_id: str,
    audio_ref: Path | str | None,
    *,
    backend: DiarizationBackend,
    allow_oracle_turns: bool = False,
    total_duration_s: float | None = None,
    fallback_pause_transitions: Sequence[float] = (),
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
) -> SlicePlan:
    """The generic (corpus-agnostic) seam-threading entry point: ask
    ``backend`` for ``meeting_id``'s turn table + provenance, then delegate
    to :func:`~.slicer.build_turn_aware_slice_plan`. This is the function
    that REPLACES the old direct-to-NXT wiring pattern (extract via
    :mod:`.adapters`, then call the slicer straight with the result) --
    every caller now names a :class:`DiarizationBackend` instead of a
    corpus-specific extraction function. No corpus default lives here (a
    generic function never hardcodes one); see
    :func:`build_turn_aware_slice_plan_for_resolved_meeting` for the
    NXT-specific convenience wrapper that DOES default to the oracle
    backend."""

    result = backend.diarize(meeting_id, audio_ref)
    return build_turn_aware_slice_plan(
        meeting_id,
        result.turns,
        turn_provenance=result.provenance,
        allow_oracle_turns=allow_oracle_turns,
        total_duration_s=total_duration_s,
        fallback_pause_transitions=fallback_pause_transitions,
        nominal_s=nominal_s,
        min_s=min_s,
        max_s=max_s,
        snap_s=snap_s,
    )


def build_turn_aware_slice_plan_for_resolved_meeting(
    resolved: "ResolvedMeeting",
    *,
    backend: DiarizationBackend | None = None,
    audio_ref: Path | str | None = None,
    allow_oracle_turns: bool = False,
    total_duration_s: float | None = None,
    fallback_pause_transitions: Sequence[float] = (),
    nominal_s: float = TRANSPORT_SLICE_TARGET_S,
    min_s: float = TRANSPORT_SLICE_MIN_S,
    max_s: float = TRANSPORT_SLICE_MAX_S,
    snap_s: float = TRANSPORT_SLICE_SNAP_S,
) -> SlicePlan:
    """Turn-aware slice plan for one ``ResolvedMeeting``, through the
    :class:`DiarizationBackend` seam rather than the old
    ``turn_table_from_resolved_meeting`` + ``turn_table_provenance`` direct
    wiring. ``backend`` DEFAULTS to :class:`NxtOracleDiarization` wrapping
    ``resolved`` itself, so every existing caller that relied on the NXT
    gold-turn path keeps producing an identical plan without passing
    anything new -- the ``allow_oracle_turns=True`` opt-in this still needs
    (:mod:`.leakage`'s M0/M1 gate) is unchanged from the direct-wiring era."""

    effective_backend = backend if backend is not None else NxtOracleDiarization(resolved)
    return build_turn_aware_slice_plan_from_backend(
        resolved.meeting_id,
        audio_ref,
        backend=effective_backend,
        allow_oracle_turns=allow_oracle_turns,
        total_duration_s=total_duration_s,
        fallback_pause_transitions=fallback_pause_transitions,
        nominal_s=nominal_s,
        min_s=min_s,
        max_s=max_s,
        snap_s=snap_s,
    )
