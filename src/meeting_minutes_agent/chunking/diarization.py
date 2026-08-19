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
- :class:`PinnedToolDiarization` -- the real, subprocess-driven pinned-tool
  backend (DIAR-SMOKE, ``docs/readiness/2026-08-18-diar-smoke-
  preregistration.md``; tool identity per ``docs/plans/2026-08-18-
  diarization-tool-selection.md``). It replaces the earlier honest stub that
  raised :class:`DiarizationToolNotPinnedError` unconditionally: the tool
  choice is now registered (NVIDIA Sortformer, Arm A NeMo fp32 / Arm B
  NeMo-Speech.cpp CUDA+GGUF, both RTTM-emitting per the selection ticket),
  so this class runs a caller-configured command, parses its RTTM output
  (:mod:`.rttm`) into a turn table, and logs the contact -- never guesses at
  a tool this repository has not been told to pin. :class:`DiarizationToolNotPinnedError`
  stays defined (still exported, still the right exception FAMILY -- it
  subclasses no longer-reachable-by-default behaviour) for any caller that
  still imports it; :class:`ToolDiarizationInvocationError` is the new
  failure mode a real (mis)configured contact raises.

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

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from .constants import (
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from .leakage import BoundaryProvenance
from .rttm import parse_rttm_file
from .slicer import SlicePlan, TurnSpan, build_turn_aware_slice_plan

if TYPE_CHECKING:
    from ..corpora.nxt.models import ResolvedMeeting

__all__ = [
    "DiarizationResult",
    "DiarizationBackend",
    "NxtOracleDiarization",
    "DiarizationToolNotPinnedError",
    "ToolDiarizationConfig",
    "ToolContactRecord",
    "ToolDiarizationInvocationError",
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
    """Historical: raised by the pre-DIAR-SMOKE :class:`PinnedToolDiarization`
    stub, unconditionally, before ``docs/plans/2026-08-18-diarization-tool-
    selection.md`` resolved the tool choice. Kept defined (and exported) so
    any existing import of this name keeps working; it is no longer raised
    by :class:`PinnedToolDiarization` itself (see
    :class:`ToolDiarizationInvocationError` for its real failure mode)."""


@dataclass(frozen=True)
class ToolDiarizationConfig:
    """One pinned tool's identity + how to invoke it -- exactly the fields
    the frozen-tool-contact rule requires be logged (``docs/readiness/
    2026-08-18-diar-smoke-preregistration.md`` SS7): a command template, the
    tool's own name and version string, its checkpoint's sha256, and any
    extra CLI args. Never hardcodes a real tool's path/command -- DIAR-SMOKE
    is machinery-only at engineering time (no installs, no downloads); a
    real flight supplies this via caller configuration (``scripts/
    launch_diar_smoke.py --arm-config``), never a default baked in here.

    ``command_template`` is a sequence of argv tokens; each token is run
    through ``str.format(audio_path=..., rttm_path=..., meeting_id=...)``
    before the subprocess is invoked, so a template names the audio input,
    the RTTM output path, and/or the meeting id wherever the real tool's own
    CLI expects them (e.g. NeMo-Speech.cpp's own
    ``nemo-speech diarize {audio_path} --model <gguf> --offline --format
    rttm --output {rttm_path}``, selection ticket SS2.4). ``extra_args`` are
    appended after ``command_template``, substituted the same way -- a
    caller-supplied knob (segmentation thresholds, etc.) kept separate from
    the template's own fixed shape.
    """

    tool_name: str
    tool_version: str
    checkpoint_sha256: str
    command_template: tuple[str, ...]
    extra_args: tuple[str, ...] = ()
    timeout_seconds: float = 3600.0

    def validate(self) -> "ToolDiarizationConfig":
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError(f"tool_name must be a non-empty string, got {self.tool_name!r}")
        if not isinstance(self.tool_version, str) or not self.tool_version.strip():
            raise ValueError(f"tool_version must be a non-empty string, got {self.tool_version!r}")
        if (
            not isinstance(self.checkpoint_sha256, str)
            or len(self.checkpoint_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.checkpoint_sha256.lower())
        ):
            raise ValueError(f"checkpoint_sha256 must be a 64-hex digest, got {self.checkpoint_sha256!r}")
        if not self.command_template:
            raise ValueError("command_template must carry at least one argv token")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds!r}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "checkpoint_sha256": self.checkpoint_sha256,
            "command_template": list(self.command_template),
            "extra_args": list(self.extra_args),
            "timeout_seconds": self.timeout_seconds,
        }

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "ToolDiarizationConfig":
        return ToolDiarizationConfig(
            tool_name=str(raw["tool_name"]),
            tool_version=str(raw["tool_version"]),
            checkpoint_sha256=str(raw["checkpoint_sha256"]),
            command_template=tuple(str(t) for t in raw["command_template"]),
            extra_args=tuple(str(t) for t in raw.get("extra_args", ())),
            timeout_seconds=float(raw.get("timeout_seconds", 3600.0)),
        ).validate()


@dataclass(frozen=True)
class ToolContactRecord:
    """One pinned-tool subprocess contact, logged unconditionally --
    success, a non-zero return code, missing RTTM output, or a raised
    subprocess exception all produce exactly one of these (frozen-tool
    per-contact logging rule, prereg SS7: "tool version, checkpoint hash,
    args, wall/GPU"). GPU seconds are not this class's concern -- a
    subprocess contact alone cannot observe them; the smoke runner
    (:mod:`meeting_minutes_agent.probes.diar_smoke`) attaches a best-effort
    ``nvidia-smi`` sample alongside this record instead."""

    tool_name: str
    tool_version: str
    checkpoint_sha256: str
    meeting_id: str
    args: tuple[str, ...]
    wall_seconds: float
    return_code: int | None
    error: str | None
    recorded_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "checkpoint_sha256": self.checkpoint_sha256,
            "meeting_id": self.meeting_id,
            "args": list(self.args),
            "wall_seconds": self.wall_seconds,
            "return_code": self.return_code,
            "error": self.error,
            "recorded_utc": self.recorded_utc,
        }


class ToolDiarizationInvocationError(RuntimeError):
    """:class:`PinnedToolDiarization` refuses to return a fabricated turn
    table: the pinned tool subprocess exited non-zero, raised while being
    launched (missing binary, timeout, ...), or exited 0 but wrote no RTTM
    at the expected path. A :class:`ToolContactRecord` for the attempt is
    always logged BEFORE this is raised."""


def _default_run_subprocess(args: Sequence[str], *, timeout: float) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, check=False)


class PinnedToolDiarization(DiarizationBackend):
    """The real, subprocess-driven pinned-tool backend (module docstring).
    Generic over WHICH tool: ``config`` names the argv template, tool
    identity, and checkpoint hash, so this one class serves both DIAR-SMOKE
    arms (Arm A's NeMo fp32 wrapper, Arm B's NeMo-Speech.cpp CUDA+GGUF CLI)
    -- and the contingent Arm C -- without a tool-specific subclass.

    ``run_subprocess`` is an injection seam (mirrors :class:`~meeting_minutes_agent.
    client.transport.LlamaServerTransport`'s own ``post`` parameter and
    ``run_arm``'s injected transport in ``scripts/launch_pattr_smoke.py``):
    tests supply a fake callable, so this class is fully exercisable without
    a real tool binary, a real GPU, or a real install -- the zero-model/
    zero-tool-contact discipline this repository's test suite holds to.
    """

    def __init__(
        self,
        config: ToolDiarizationConfig,
        *,
        output_dir: Path | str,
        run_subprocess: Callable[..., "subprocess.CompletedProcess[str]"] | None = None,
        on_contact: Callable[[ToolContactRecord], None] | None = None,
    ) -> None:
        self.config = config.validate()
        self._output_dir = Path(output_dir)
        self._run_subprocess = run_subprocess or _default_run_subprocess
        self._on_contact = on_contact
        self._contact_log: list[ToolContactRecord] = []

    @property
    def contact_log(self) -> tuple[ToolContactRecord, ...]:
        return tuple(self._contact_log)

    def _rttm_path_for(self, meeting_id: str) -> Path:
        return self._output_dir / f"{meeting_id}.rttm"

    def _log_contact(self, *, meeting_id: str, args: Sequence[str], wall_seconds: float,
                      return_code: int | None, error: str | None) -> ToolContactRecord:
        record = ToolContactRecord(
            tool_name=self.config.tool_name,
            tool_version=self.config.tool_version,
            checkpoint_sha256=self.config.checkpoint_sha256,
            meeting_id=meeting_id,
            args=tuple(args),
            wall_seconds=wall_seconds,
            return_code=return_code,
            error=error,
            recorded_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._contact_log.append(record)
        if self._on_contact is not None:
            self._on_contact(record)
        return record

    def diarize(self, meeting_id: str, audio_ref: Path | str | None) -> DiarizationResult:
        if audio_ref is None:
            raise ValueError(
                "PinnedToolDiarization.diarize requires audio_ref -- a real tool backend cannot "
                f"diarize meeting_id={meeting_id!r} without audio bytes"
            )
        audio_path = Path(audio_ref)
        rttm_path = self._rttm_path_for(meeting_id)
        rttm_path.parent.mkdir(parents=True, exist_ok=True)

        substitutions = {
            "audio_path": str(audio_path),
            "rttm_path": str(rttm_path),
            "meeting_id": meeting_id,
        }
        args = [
            token.format(**substitutions)
            for token in (*self.config.command_template, *self.config.extra_args)
        ]

        started = time.monotonic()
        try:
            completed = self._run_subprocess(args, timeout=self.config.timeout_seconds)
        except Exception as error:  # noqa: BLE001 -- logged, then re-raised as our own error type
            wall_seconds = time.monotonic() - started
            self._log_contact(
                meeting_id=meeting_id, args=args, wall_seconds=wall_seconds, return_code=None,
                error=f"{type(error).__name__}: {error}",
            )
            raise ToolDiarizationInvocationError(
                f"{self.config.tool_name}: subprocess invocation failed for meeting_id={meeting_id!r}: {error}"
            ) from error

        wall_seconds = time.monotonic() - started
        stderr_text = getattr(completed, "stderr", None) or None
        error_text = stderr_text if completed.returncode != 0 else None
        self._log_contact(
            meeting_id=meeting_id, args=args, wall_seconds=wall_seconds,
            return_code=completed.returncode, error=error_text,
        )

        if completed.returncode != 0:
            raise ToolDiarizationInvocationError(
                f"{self.config.tool_name} exited {completed.returncode} for meeting_id={meeting_id!r}: "
                f"{stderr_text!r}"
            )
        if not rttm_path.is_file():
            raise ToolDiarizationInvocationError(
                f"{self.config.tool_name} exited 0 for meeting_id={meeting_id!r} but wrote no RTTM at "
                f"{rttm_path}"
            )

        turns = parse_rttm_file(rttm_path)
        return DiarizationResult(turns=turns, provenance=BoundaryProvenance.TOOL_DIAR)


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
