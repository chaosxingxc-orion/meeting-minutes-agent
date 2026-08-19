"""PRECOMP wave rosters + the fail-closed exposure exclusion gate.

Registered design: ``docs/readiness/2026-08-19-precomp-preregistration.md``
SS2 -- "Wave-1 (now): the dev-18 meetings... Wave-2 (night batch, resumable
chunks): the remaining usable-discovery meetings (~83)... eval-16 and
reserved-final-reporting meetings are NOT precomputed (untouchable until
their governed use)."

This module builds both wave rosters from the single committed source of
AMI meeting identity, :mod:`meeting_minutes_agent.corpora.roles`
(``configs/corpora/ami-role-registry.json``), and never hand-lists a
meeting id of its own -- exactly the same "the registry is the program's
single machine-checked exposure gate" discipline
``scripts/build_pattr_manifest.py::build_manifest`` already applies.

Two independent axes, deliberately NOT collapsed into one (roles.py's own
docstring: "the two axes are independent"):

- :class:`~meeting_minutes_agent.corpora.roles.MeetingRole` -- governs
  whether this repository may expose a meeting's AUDIO to the frozen core
  at all. Only the three ACTIVE roles (``asr-eval``, ``qa-eval``,
  ``glossary-discovery``) permit exposure; the two RESERVED roles
  (``held-out-confirmatory`` == eval-16, ``held-out-reserve``) permit none.
- :class:`~meeting_minutes_agent.corpora.roles.QuestionUsagePolicy` --
  governs whether a meeting's MeetingQA *questions* are a free discovery
  surface right now. ``usable-discovery`` (train/dev MeetingQA split,
  meeting outside eval-16) is that surface.

Because the two axes are independent, a meeting can carry
``QuestionUsagePolicy.USABLE_DISCOVERY`` while its :class:`MeetingRole` is
``held-out-reserve`` -- 14 real AMI meetings do exactly this (e.g.
``EN2001b``). PRECOMP's wave-2 roster is built by intersecting BOTH axes
(:func:`usable_discovery_exposable_roster`), never by reading the
QuestionUsagePolicy axis alone: this pass sends real audio BYTES to the
frozen core (the encode-warm contact), so meeting exposure is gated
exactly like every other frozen-core contact in this repository --
``registry.assert_exposable`` -- regardless of what a DIFFERENT, orthogonal
policy says about that meeting's MeetingQA questions.
"""

from __future__ import annotations

from typing import Sequence

from ..corpora.roles import (
    FROZEN_DEV_18,
    AmiRoleRegistry,
    HeldOutLeakageError,
    MeetingRole,
    load_role_registry,
)

WAVE_1 = 1
WAVE_2 = 2
WAVES: tuple[int, ...] = (WAVE_1, WAVE_2)

#: The AMI meeting roles PRECOMP is permitted to touch at all -- exactly
#: the exposable roles (``registry.assert_exposable``'s own admission set),
#: named here so :func:`usable_discovery_exposable_roster` reads as one
#: intersection rather than a re-derivation of ``assert_exposable``'s logic.
_EXPOSABLE_PRECOMP_ROLES: tuple[MeetingRole, ...] = (
    MeetingRole.ASR_EVAL,
    MeetingRole.QA_EVAL,
    MeetingRole.GLOSSARY_DISCOVERY,
)


class PrecompRosterError(ValueError):
    """A wave number outside :data:`WAVES`, or another roster-construction
    refusal that is not itself a :class:`~..corpora.roles.RoleRegistryError`."""


def _registry_or_default(registry: AmiRoleRegistry | None) -> AmiRoleRegistry:
    return registry if registry is not None else load_role_registry()


def dev18_roster(registry: AmiRoleRegistry | None = None) -> tuple[str, ...]:
    """Wave-1's roster: the frozen ASR dev-18, sorted. ``registry`` is
    accepted (and, when given, its ``asr-eval`` role set is cross-checked
    against :data:`~..corpora.roles.FROZEN_DEV_18`) purely for symmetry with
    the other roster functions and as defense in depth against a corrupted
    registry file -- the frozen split itself is a Python constant, not
    reconstructed from the file."""

    reg = _registry_or_default(registry)
    asr_eval = set(reg.meetings_with_role(MeetingRole.ASR_EVAL))
    if asr_eval != set(FROZEN_DEV_18):
        raise PrecompRosterError(
            "AMI role registry's asr-eval role set does not match FROZEN_DEV_18; refusing to build "
            f"the wave-1 roster from a registry that disagrees with the frozen split freeze: "
            f"extra={sorted(asr_eval - set(FROZEN_DEV_18))} missing={sorted(set(FROZEN_DEV_18) - asr_eval)}"
        )
    return tuple(sorted(FROZEN_DEV_18))


def usable_discovery_exposable_roster(registry: AmiRoleRegistry | None = None) -> tuple[str, ...]:
    """Every meeting that is BOTH a usable-discovery MeetingQA surface AND
    audio-exposable to the frozen core (module docstring): the intersection
    of :meth:`~..corpora.roles.AmiRoleRegistry.usable_discovery_questions`
    and the three ACTIVE :class:`~..corpora.roles.MeetingRole` values.
    Sorted, deduplicated by construction (both source sets are already
    meeting-id sets)."""

    reg = _registry_or_default(registry)
    usable = set(reg.usable_discovery_questions())
    exposable = {m for role in _EXPOSABLE_PRECOMP_ROLES for m in reg.meetings_with_role(role)}
    return tuple(sorted(usable & exposable))


def wave2_roster(registry: AmiRoleRegistry | None = None) -> tuple[str, ...]:
    """Wave-2's roster (prereg SS2): :func:`usable_discovery_exposable_roster`
    MINUS the wave-1 dev-18 set -- "the remaining usable-discovery
    meetings"."""

    reg = _registry_or_default(registry)
    remaining = set(usable_discovery_exposable_roster(reg)) - set(FROZEN_DEV_18)
    return tuple(sorted(remaining))


def default_wave_meetings(wave: int, registry: AmiRoleRegistry | None = None) -> tuple[str, ...]:
    """The registered default roster for ``wave`` (1 or 2). Raises
    :class:`PrecompRosterError` for any other value -- there is no silent
    fall-through to a default wave."""

    if wave == WAVE_1:
        return dev18_roster(registry)
    if wave == WAVE_2:
        return wave2_roster(registry)
    raise PrecompRosterError(f"unknown PRECOMP wave {wave!r}; expected one of {WAVES}")


def assert_wave_roster_admissible(meetings: Sequence[str], registry: AmiRoleRegistry | None = None) -> None:
    """Fail-closed exposure gate (module docstring, prereg discipline
    SS6): every meeting in ``meetings`` must carry an ACTIVE (exposable)
    :class:`~..corpora.roles.MeetingRole`. Delegates to
    ``registry.assert_exposable``, which raises
    :class:`~..corpora.roles.HeldOutLeakageError` for BOTH reserved roles --
    ``held-out-confirmatory`` (eval-16) and ``held-out-reserve`` -- and
    :class:`~..corpora.roles.UnknownMeetingError` for a meeting id absent
    from the roster entirely. Defense in depth: called unconditionally by
    the wave runner on EVERY meeting list it is about to touch, whether
    that list came from :func:`default_wave_meetings` (already exposable by
    construction) or an operator-supplied ``--meetings`` override (not
    otherwise checked before this gate)."""

    reg = _registry_or_default(registry)
    for meeting_id in meetings:
        reg.assert_exposable(meeting_id)


__all__ = [
    "WAVE_1",
    "WAVE_2",
    "WAVES",
    "PrecompRosterError",
    "HeldOutLeakageError",
    "dev18_roster",
    "usable_discovery_exposable_roster",
    "wave2_roster",
    "default_wave_meetings",
    "assert_wave_roster_admissible",
]
