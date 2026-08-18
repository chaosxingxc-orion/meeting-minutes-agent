"""P-ATTR capability smoke: the three arms' request builders.

Pre-registered design (``docs/readiness/2026-08-18-g1-preregistration-draft.md``
SS0):

======  ======================================================================================  ===============================
Arm     Request shape                                                                            Measures
======  ======================================================================================  ===============================
A-grid  ``transcribe_attribute`` template WITH the declared per-slice turn/speaker grid.          boundary respect + confusion cost
A-free  Same template, minus the grid -- the model attributes freely.                             what the declared grid buys
A-turn  One request per speaker TURN; audio cut to the turn span; speaker known from the           the zero-attribution-risk
        manifest (attribution by construction); ``transcribe_only`` template (no attribution       fallback's WER and call cost
        instruction at all).
======  ======================================================================================  ===============================

This module is a pure request BUILDER, mirroring every existing head's own
scope ("a prompt template builder + a response parser, no transport calls",
:mod:`meeting_minutes_agent.heads`): it reads an already-frozen
:class:`PattrManifest` (built by ``scripts/build_pattr_manifest.py`` from
real AMI bytes -- the one place in the P-ATTR machinery that touches audio
I/O, per the slicer's own "freeze the manifest BEFORE any arm runs"
discipline, :mod:`meeting_minutes_agent.chunking.slicer` module docstring)
and turns it into deterministic :class:`PattrRequestSpec` records. No network
call, no audio decode, zero model contact -- resolving a spec's audio bytes
happens only when a caller (the future flight launcher,
``scripts/launch_pattr_smoke.py``) hands ``request_id``/``audio_path``/
``audio_seconds`` to a real transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..heads.request import HeadRequest
from ..heads.transcribe_attribute import (
    build_transcribe_attribute_request,
    build_transcribe_only_request,
)

SCHEMA_VERSION = "1.0.0"

ARM_A_GRID = "A-grid"
ARM_A_FREE = "A-free"
ARM_A_TURN = "A-turn"
ARMS: tuple[str, ...] = (ARM_A_GRID, ARM_A_FREE, ARM_A_TURN)

#: Zero-supply block: P-ATTR is a capability smoke, not a glossary-supply
#: probe (docs/readiness/2026-08-18-g1-preregistration-draft.md SS0 measures
#: attribution, not supply gain) -- the same "(none)" convention already
#: used by this head's own tests.
NO_SUPPLY_TEXT = "=== KNOWN TERMS ===\n(none)"


class PattrManifestError(ValueError):
    """The manifest JSON failed the fail-closed load check (unknown schema
    version, missing block, a request built against a meeting the manifest
    does not carry, ...)."""


# ---------------------------------------------------------------------------
# manifest loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PattrManifest:
    """A validated, in-memory view of the frozen smoke-manifest binding
    JSON (``configs/probes/pattr/*.json``, built by
    ``scripts/build_pattr_manifest.py``). Thin: this class does not
    re-derive anything the file does not already carry -- it is a
    fail-closed loader plus small accessors, matching
    :mod:`meeting_minutes_agent.corpora.roles`'s own loader shape.
    """

    raw: Mapping[str, Any]
    source_path: Path | None

    @property
    def seed(self) -> int:
        return int(self.raw["seed"])

    @property
    def selected_meetings(self) -> tuple[str, ...]:
        return tuple(self.raw["selected_meetings"])

    @property
    def slice_output_dir_relative(self) -> str:
        return str(self.raw["slice_output_dir_relative"])

    @property
    def turn_clip_output_dir_relative(self) -> str:
        return str(self.raw["turn_clip_output_dir_relative"])

    @property
    def transport_bound_violations(self) -> tuple[Mapping[str, Any], ...]:
        """Slices ``scripts/build_pattr_manifest.py`` found exceeding the
        transport layer's hard ``max_audio_seconds_per_request`` guard
        (its own ``find_oversized_slices`` docstring for how this can
        happen) -- ``()`` for a manifest built before this diagnostic
        existed, or one with no violations. A caller building A-grid/
        A-free requests should check this before a real flight: this
        module does not filter or refuse a violating slice on its own (a
        request-BUILDING seam, per this module's own scope, never a
        policy seam)."""

        return tuple(self.raw.get("transport_bound_violations", ()))

    def meeting(self, meeting_id: str) -> Mapping[str, Any]:
        try:
            return self.raw["meetings"][meeting_id]
        except KeyError:
            raise PattrManifestError(
                f"meeting {meeting_id!r} is not on this P-ATTR manifest's roster "
                f"({sorted(self.raw['meetings'])})"
            ) from None

    def slice_entries(self, meeting_id: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.meeting(meeting_id)["slice_plan"]["entries"])

    def turn_clip_entries(self, meeting_id: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.meeting(meeting_id)["turn_clips"])

    def slice_audio_relpath(self, meeting_id: str, filename: str) -> str:
        return f"{self.slice_output_dir_relative}/{meeting_id}/{filename}"

    def turn_clip_audio_relpath(self, meeting_id: str, filename: str) -> str:
        return f"{self.turn_clip_output_dir_relative}/{meeting_id}/{filename}"

    def resolve_audio_path(self, data_dir: Path | str, relpath: str) -> Path:
        return Path(data_dir) / relpath


_REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "seed",
    "selected_meetings",
    "slice_output_dir_relative",
    "turn_clip_output_dir_relative",
    "meetings",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PattrManifestError(message)


def load_pattr_manifest(path: Path | str) -> PattrManifest:
    """Load and minimally validate a P-ATTR smoke-manifest JSON. Fail-closed
    (raises :class:`PattrManifestError`), mirroring the repository's other
    loaders: unknown ``schema_version``, a missing top-level field, an empty
    or non-list ``selected_meetings``, or a ``selected_meetings`` entry
    absent from ``meetings`` are all refusals, never a silently degraded
    manifest."""

    resolved = Path(path)
    document = json.loads(resolved.read_text(encoding="utf-8"))

    missing = [f for f in _REQUIRED_TOP_LEVEL_FIELDS if f not in document]
    _require(not missing, f"P-ATTR manifest {resolved} is missing top-level fields: {missing}")
    _require(
        document["schema_version"] == SCHEMA_VERSION,
        f"P-ATTR manifest {resolved} declares schema_version={document['schema_version']!r}, "
        f"expected {SCHEMA_VERSION!r}",
    )
    selected = document["selected_meetings"]
    _require(
        isinstance(selected, list) and len(selected) > 0,
        f"P-ATTR manifest {resolved} carries an empty or non-list selected_meetings",
    )
    meetings = document["meetings"]
    _require(isinstance(meetings, dict), f"P-ATTR manifest {resolved} carries a non-object 'meetings' block")
    missing_meetings = [m for m in selected if m not in meetings]
    _require(
        not missing_meetings,
        f"P-ATTR manifest {resolved}: selected_meetings names meetings absent from 'meetings': {missing_meetings}",
    )
    for meeting_id in selected:
        record = meetings[meeting_id]
        _require(
            isinstance(record, dict) and "slice_plan" in record and "turn_clips" in record,
            f"P-ATTR manifest {resolved}: meeting {meeting_id!r} is missing 'slice_plan'/'turn_clips'",
        )

    return PattrManifest(raw=document, source_path=resolved)


# ---------------------------------------------------------------------------
# request specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PattrRequestSpec:
    """One arm's one built request: everything a launcher needs to dispatch
    it via :class:`meeting_minutes_agent.client.transport.LlamaServerTransport`,
    plus the scoring-side metadata (``slice_index``/``turn_index``/
    ``known_speaker``) a later read needs to reassemble per-speaker
    hypothesis streams (:mod:`.pattr_scoring`)."""

    request_id: str
    arm: str
    meeting_id: str
    slice_index: int | None
    turn_index: int | None
    audio_relpath: str
    audio_seconds: float
    known_speaker: str | None
    head_request: HeadRequest

    def to_transport_kwargs(self, *, data_dir: Path | str) -> dict[str, object]:
        """Merge this spec's audio identity into its
        :class:`~meeting_minutes_agent.heads.request.HeadRequest`, producing
        the exact kwargs
        :meth:`meeting_minutes_agent.client.transport.LlamaServerTransport.request`
        expects. ``data_dir`` is the ``SPEECHRL_DATA_DIR`` root the
        manifest's relative paths resolve against."""

        return self.head_request.to_transport_kwargs(
            request_id=self.request_id,
            audio_path=Path(data_dir) / self.audio_relpath,
            audio_seconds=self.audio_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "arm": self.arm,
            "meeting_id": self.meeting_id,
            "slice_index": self.slice_index,
            "turn_index": self.turn_index,
            "audio_relpath": self.audio_relpath,
            "audio_seconds": self.audio_seconds,
            "known_speaker": self.known_speaker,
            "template_id": self.head_request.template_id,
        }


def _request_id(arm_slug: str, meeting_id: str, *, slice_index: int | None = None, turn_index: int | None = None) -> str:
    if slice_index is not None:
        return f"pattr-{arm_slug}-{meeting_id}-slice{slice_index:04d}"
    if turn_index is not None:
        return f"pattr-{arm_slug}-{meeting_id}-turn{turn_index:04d}"
    raise ValueError("_request_id requires slice_index or turn_index")


def _meetings_or_all(manifest: PattrManifest, meetings: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(meetings) if meetings is not None else manifest.selected_meetings


def build_grid_requests(
    manifest: PattrManifest, *, meetings: Sequence[str] | None = None
) -> tuple[PattrRequestSpec, ...]:
    """A-grid: one request per transport slice, WITH the declared per-slice
    turn/speaker grid (the slice's own ``turns`` table). Request count ==
    the manifest's total slice count over the selected meetings."""

    specs: list[PattrRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        for entry in manifest.slice_entries(meeting_id):
            head_request = build_transcribe_attribute_request(
                supply_text=NO_SUPPLY_TEXT, declared_grid_turns=entry["turns"]
            )
            specs.append(
                PattrRequestSpec(
                    request_id=_request_id("grid", meeting_id, slice_index=entry["index"]),
                    arm=ARM_A_GRID,
                    meeting_id=meeting_id,
                    slice_index=entry["index"],
                    turn_index=None,
                    audio_relpath=manifest.slice_audio_relpath(meeting_id, entry["filename"]),
                    audio_seconds=float(entry["end"]) - float(entry["start"]),
                    known_speaker=None,
                    head_request=head_request,
                )
            )
    return tuple(specs)


def build_free_requests(
    manifest: PattrManifest, *, meetings: Sequence[str] | None = None
) -> tuple[PattrRequestSpec, ...]:
    """A-free: same template as A-grid, one request per transport slice,
    WITHOUT the declared grid -- the model attributes freely. Request count
    equals A-grid's, by construction (same slice set, same manifest)."""

    specs: list[PattrRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        for entry in manifest.slice_entries(meeting_id):
            head_request = build_transcribe_attribute_request(supply_text=NO_SUPPLY_TEXT)
            specs.append(
                PattrRequestSpec(
                    request_id=_request_id("free", meeting_id, slice_index=entry["index"]),
                    arm=ARM_A_FREE,
                    meeting_id=meeting_id,
                    slice_index=entry["index"],
                    turn_index=None,
                    audio_relpath=manifest.slice_audio_relpath(meeting_id, entry["filename"]),
                    audio_seconds=float(entry["end"]) - float(entry["start"]),
                    known_speaker=None,
                    head_request=head_request,
                )
            )
    return tuple(specs)


def build_turn_requests(
    manifest: PattrManifest, *, meetings: Sequence[str] | None = None
) -> tuple[PattrRequestSpec, ...]:
    """A-turn: one request per speaker TURN, audio cut to that turn's own
    span (the manifest's pre-materialized turn clips -- never the whole
    slice). ``known_speaker`` carries the manifest's own speaker label for
    this turn, so the scoring path attributes the reply BY CONSTRUCTION,
    never by parsing a speaker label out of the model's reply (the
    transcribe-only template asks for none)."""

    specs: list[PattrRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        for entry in manifest.turn_clip_entries(meeting_id):
            head_request = build_transcribe_only_request()
            specs.append(
                PattrRequestSpec(
                    request_id=_request_id("turn", meeting_id, turn_index=entry["turn_index"]),
                    arm=ARM_A_TURN,
                    meeting_id=meeting_id,
                    slice_index=entry.get("slice_index"),
                    turn_index=entry["turn_index"],
                    audio_relpath=manifest.turn_clip_audio_relpath(meeting_id, entry["filename"]),
                    audio_seconds=float(entry["duration_s"]),
                    known_speaker=str(entry["speaker"]),
                    head_request=head_request,
                )
            )
    return tuple(specs)


_ARM_BUILDERS = {
    ARM_A_GRID: build_grid_requests,
    ARM_A_FREE: build_free_requests,
    ARM_A_TURN: build_turn_requests,
}


def build_arm_requests(
    manifest: PattrManifest, arm: str, *, meetings: Sequence[str] | None = None
) -> tuple[PattrRequestSpec, ...]:
    """Dispatch to the arm-specific builder above by name (one of
    :data:`ARMS`). Unknown arm names raise -- there is no silent
    fall-through to a default arm."""

    try:
        builder = _ARM_BUILDERS[arm]
    except KeyError:
        raise ValueError(f"unknown P-ATTR arm {arm!r}; expected one of {ARMS}") from None
    return builder(manifest, meetings=meetings)


# ---------------------------------------------------------------------------
# per-arm summaries (expected request counts + audio seconds)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmSummary:
    arm: str
    n_requests: int
    n_meetings: int
    total_audio_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "n_requests": self.n_requests,
            "n_meetings": self.n_meetings,
            "total_audio_seconds": self.total_audio_seconds,
        }


def summarize_arm(arm: str, requests: Sequence[PattrRequestSpec]) -> ArmSummary:
    return ArmSummary(
        arm=arm,
        n_requests=len(requests),
        n_meetings=len({r.meeting_id for r in requests}),
        total_audio_seconds=sum(r.audio_seconds for r in requests),
    )


def summarize_all_arms(
    manifest: PattrManifest, *, meetings: Sequence[str] | None = None
) -> dict[str, ArmSummary]:
    """One :class:`ArmSummary` per arm in :data:`ARMS` order -- the "report
    expected counts and total audio seconds" deliverable, computed purely
    from the frozen manifest, no model contact."""

    return {arm: summarize_arm(arm, build_arm_requests(manifest, arm, meetings=meetings)) for arm in ARMS}


__all__ = [
    "SCHEMA_VERSION",
    "ARM_A_GRID",
    "ARM_A_FREE",
    "ARM_A_TURN",
    "ARMS",
    "NO_SUPPLY_TEXT",
    "PattrManifestError",
    "PattrManifest",
    "load_pattr_manifest",
    "PattrRequestSpec",
    "build_grid_requests",
    "build_free_requests",
    "build_turn_requests",
    "build_arm_requests",
    "ArmSummary",
    "summarize_arm",
    "summarize_all_arms",
]
