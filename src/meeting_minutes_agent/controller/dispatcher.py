"""Pure-logic dispatch (component C7, backbone design doc SS5.1): given a
task + :class:`~meeting_minutes_agent.state.episode.EpisodeState` + chunk
plan, build the head request (via :mod:`meeting_minutes_agent.heads`) and
the supply block (via :mod:`meeting_minutes_agent.supply`), returning an
executable :class:`DispatchUnit`; separately, parse a raw core response and
fold it back into ``EpisodeState`` via :func:`fold_dispatch_result`.

No transport call and no openJiuwen import anywhere in this module -- it is
pure functions over plain data, exactly like every other module the mission
spec names as something :mod:`.loop` orchestrates. :mod:`.loop` is the only
caller that actually invokes the frozen core; this module only decides WHAT
would be asked and WHAT a reply means.

Three real, dispatchable task kinds (:mod:`.tasks` module docstring):

- ``transcribe_span`` -- builds a
  :func:`~meeting_minutes_agent.heads.transcribe_attribute.build_transcribe_attribute_request`
  over chunk ``task.chunk_index``'s audio. Folding a reply runs SPELL+REVISE
  as ONE step: the registered REVISE-stage arm constructor
  (:mod:`meeting_minutes_agent.glossary.arms`) already composes extraction
  with its own arm's normalise/dedupe/gate treatment (module docstring of
  that package: "each arm constructor is the per-chunk REVISE body"), so
  there is no separate SPELL call here -- :data:`GLOSSARY_ARM_CONSTRUCTORS`
  selects which arm constructor is "in force" for this episode. The parsed
  reply's per-segment speaker cues are ALSO mined for self-introduction
  candidates (:func:`find_self_introduction`) and folded into the episode's
  speaker map.
- ``summarize_section`` -- builds a
  :func:`~meeting_minutes_agent.heads.minutes.build_minutes_request` over
  the resolved transcript accumulated so far. Also carries real audio
  (chunk ``task.chunk_index``'s -- a resolved design choice, see module
  docstring "Design note: summarize audio grounding" below), because the
  frozen core is reached ONLY through
  :class:`meeting_minutes_agent.client.component.FrozenMeetingCore`, whose
  four required input fields always include ``audio_path``/``audio_seconds``
  (that component's own docstring/``_REQUIRED_INPUT_FIELDS``) -- there is no
  text-only call shape to fall back to. Folding a reply never touches the
  glossary; it extracts ACTIONS/DECISIONS bullets as ``pending_ledger_bullets``
  for a LATER ``resolve_ledger`` task to fold (the loop-carried handoff
  :mod:`.loop` threads through session state, per backbone design doc SS5.3's
  "loop-carried small state via session global state").
- ``resolve_ledger`` -- a LOCAL fold, no core call at all
  (``requires_core_call=False``, ``head_request=None``, ``chunk=None``):
  folds ``pending_ledger_bullets`` (handed to
  :func:`build_dispatch_unit`/:func:`fold_dispatch_result` by the caller,
  never invented here) into the episode's decision/action ledger via
  :meth:`~meeting_minutes_agent.state.episode.EpisodeState.add_ledger_entry`.

Design note: summarize audio grounding (a real choice, stated for review,
not a forced consequence of the spec). An alternative design would give
``summarize_section`` no audio at all; that is impossible under the
single-door contract above without inventing a second call shape the
frozen-core client does not support, so this module instead reuses the
LAST chunk's own audio as the grounding clip, with the accumulated resolved
transcript supplied as text context (exactly how
:func:`~meeting_minutes_agent.heads.minutes.build_minutes_request` already
renders its ``=== TRANSCRIPT ===`` block) -- the core "listens" to that clip
again alongside the full transcript+glossary context.

Design note: per-chunk ``introduced_by`` (a second resolved ambiguity).
:mod:`meeting_minutes_agent.glossary.arms`' constructors take one
``introduced_by`` value applied uniformly to every entry produced by one
call -- but one chunk may contain several speakers. v1 passes
``introduced_by=None`` at the whole-chunk glossary-extraction call (a term
mined from a multi-speaker chunk's pooled text has no single attributable
introducer at this call granularity); self-introduction-derived SPEAKER MAP
bindings are unaffected by this (they attach to the specific segment/
speaker that produced the self-introduction, not to glossary entries).
Per-speaker-scoped glossary extraction is a real, deferred improvement, not
implemented here.

Design note: synthetic segment timing (a third resolved ambiguity). The
core's transcribe reply is a flat ``speaker|text`` line list with no
per-segment timestamps (module docstring of
:mod:`meeting_minutes_agent.heads.transcribe_attribute`); a chunk's own
``[start, end)`` span is divided evenly across its parsed segment count so
every :class:`~meeting_minutes_agent.chunking.models.Segment` still carries
a monotonic, deterministic ``start``/``end`` (needed for evidence-tag
rendering and downstream ordering), understood as an APPROXIMATION, never a
real per-word alignment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from ..chunking.models import Chunk, ChunkPlan, Segment, SegmentLike
from ..glossary.arms import (
    ArmKind,
    ArmPlan,
    deranged_arm,
    gated_arm,
    naive_raw_arm,
    no_carry_arm,
    scrambled_raw_arm,
    uniform_ungated_arm,
)
from ..glossary.models import GlossaryEntry
from ..heads.minutes import MinutesBulletClaim, MinutesParseResult, build_minutes_request, parse_minutes_response
from ..heads.request import HeadRequest
from ..heads.transcribe_attribute import (
    TranscribeAttributeParseResult,
    TranscribedSegment,
    build_transcribe_attribute_request,
    parse_transcribe_attribute_response,
)
from ..state.episode import EpisodeState
from ..state.models import SpeakerEvidenceSource, LedgerEntryKind
from ..supply.config import SupplyArmConfig
from ..supply.render import render_supply_block
from .tasks import Task, TaskKind

# Which glossary arm constructor is "in force" for a REVISE-stage call, as
# data (mission spec's own phrase) -- never a per-arm branch inside this
# module's dispatch logic.
GLOSSARY_ARM_CONSTRUCTORS: Mapping[ArmKind, Callable[..., ArmPlan]] = {
    ArmKind.GATED: gated_arm,
    ArmKind.NAIVE_RAW: naive_raw_arm,
    ArmKind.SCRAMBLED_RAW: scrambled_raw_arm,
    ArmKind.UNIFORM_UNGATED: uniform_ungated_arm,
    ArmKind.DERANGED: deranged_arm,
    ArmKind.NO_CARRY: no_carry_arm,
}

_LEDGER_SECTIONS: Mapping[str, LedgerEntryKind] = {
    "actions": LedgerEntryKind.ACTION,
    "decisions": LedgerEntryKind.DECISION,
}


class TaskDispatchNotImplementedError(NotImplementedError):
    """Raised by :func:`build_dispatch_unit` for a declared-but-unbuilt task
    kind (:class:`~.tasks.TaskKind.RE_LISTEN` /
    :class:`~.tasks.TaskKind.ANSWER_QUESTION`) -- honest-stub discipline:
    name the precondition, never guess at an unbuilt request shape. For
    ``ANSWER_QUESTION`` the outstanding precondition is controller wiring
    only -- :mod:`meeting_minutes_agent.heads.qa` itself is real, see that
    module's docstring."""


_DISPATCH_PRECONDITION = (
    "controller.dispatcher.build_dispatch_unit cannot dispatch {kind!r}: {reason}. This is an "
    "honest stub (docs/plans/2026-08-18-agent-backbone-and-layout.md SS5.1/SS5.3) -- the enum "
    "member is declared so a caller can queue it, but no request shape has been designed for it yet."
)


# ---------------------------------------------------------------------------
# self-introduction mining (SPELL-adjacent: the speaker-map binding mechanism
# named by backbone design doc SS5.2, "self-introduction mining in SPELL is
# the binding mechanism")
# ---------------------------------------------------------------------------

_SELF_INTRO_RE = re.compile(
    # Scoped inline case-insensitivity on the TRIGGER phrase only ("I'm",
    # "I am", "this is", "my name is" all appear with either casing in a
    # transcript, notably sentence-initial "I'm"/"I am"); the NAME capture
    # group deliberately stays case-SENSITIVE (bare re.IGNORECASE would also
    # loosen `[A-Z]` there, turning "I'm not sure" into a false-positive
    # self-introduction of "Not") -- a real name candidate must still start
    # with an actual capital letter.
    r"\b(?i:this\s+is|i\s*am|i'm|my\s+name\s+is)\s+"
    r"(?P<name>[A-Z][a-zA-Z'\-]*(?:\s+[A-Z][a-zA-Z'\-]*){0,2})",
)


def find_self_introduction(text: str) -> str | None:
    """The first self-introduction candidate name in ``text``, or ``None``.
    Rule-based only (no model contact, matching
    :mod:`meeting_minutes_agent.glossary.extract`'s own zero-model-contact
    discipline): looks for "this is/I am/I'm/my name is" immediately
    followed by one to three capitalized words."""

    match = _SELF_INTRO_RE.search(text)
    if not match:
        return None
    name = match.group("name").strip()
    return name or None


# ---------------------------------------------------------------------------
# DispatchUnit: the executable unit build_dispatch_unit returns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchUnit:
    """Everything :mod:`.loop` needs to either invoke the frozen core (via
    ``head_request.to_transport_kwargs`` merged with the loop's own
    per-invocation audio resolution) or, for a local-fold task, skip the
    core entirely. Never itself makes a call or touches session/openJiuwen
    state -- a plain, inert data bundle."""

    task: Task
    request_id: str
    requires_core_call: bool
    fold_kind: str  # "transcribe_attribute" | "minutes" | "ledger_local"
    head_request: HeadRequest | None
    chunk: Chunk | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "request_id": self.request_id,
            "requires_core_call": self.requires_core_call,
            "fold_kind": self.fold_kind,
            "head_request": self.head_request.to_dict() if self.head_request is not None else None,
            "chunk": self.chunk.to_dict() if self.chunk is not None else None,
        }


def _request_id(task: Task, suffix: str) -> str:
    return f"chunk{task.chunk_index:04d}-{suffix}"


def build_dispatch_unit(
    task: Task,
    *,
    episode_state: EpisodeState,
    chunk_plan: ChunkPlan,
    resolved_segments: Sequence[SegmentLike] = (),
    supply_arm: SupplyArmConfig = SupplyArmConfig(),
    decoding_params: Mapping[str, object] | None = None,
    pending_ledger_bullets: Sequence[MinutesBulletClaim] = (),
) -> DispatchUnit:
    """Build the executable unit for ``task``. Pure: same inputs always
    produce the same (request-content-equal) output; no I/O, no randomness,
    no model contact."""

    if task.kind is TaskKind.TRANSCRIBE_SPAN:
        if not (0 <= task.chunk_index < len(chunk_plan.chunks)):
            raise ValueError(
                f"transcribe_span task names chunk_index {task.chunk_index}, out of range for a "
                f"{len(chunk_plan.chunks)}-chunk plan"
            )
        chunk = chunk_plan.chunks[task.chunk_index]
        supply = render_supply_block(episode_state, arm=supply_arm)
        head_request = build_transcribe_attribute_request(
            supply_text=supply.text,
            span_context=tuple(resolved_segments),
            decoding_params=decoding_params,
        )
        return DispatchUnit(
            task=task,
            request_id=_request_id(task, "transcribe"),
            requires_core_call=True,
            fold_kind="transcribe_attribute",
            head_request=head_request,
            chunk=chunk,
        )

    if task.kind is TaskKind.SUMMARIZE_SECTION:
        if not (0 <= task.chunk_index < len(chunk_plan.chunks)):
            raise ValueError(
                f"summarize_section task names chunk_index {task.chunk_index}, out of range for a "
                f"{len(chunk_plan.chunks)}-chunk plan"
            )
        chunk = chunk_plan.chunks[task.chunk_index]
        supply = render_supply_block(episode_state, arm=supply_arm)
        head_request = build_minutes_request(
            supply_text=supply.text,
            resolved_transcript=tuple(resolved_segments),
            decoding_params=decoding_params,
        )
        return DispatchUnit(
            task=task,
            request_id=_request_id(task, "summarize"),
            requires_core_call=True,
            fold_kind="minutes",
            head_request=head_request,
            chunk=chunk,
        )

    if task.kind is TaskKind.RESOLVE_LEDGER:
        return DispatchUnit(
            task=task,
            request_id=_request_id(task, "ledger"),
            requires_core_call=False,
            fold_kind="ledger_local",
            head_request=None,
            chunk=None,
        )

    if task.kind is TaskKind.RE_LISTEN:
        raise TaskDispatchNotImplementedError(
            _DISPATCH_PRECONDITION.format(
                kind=task.kind.value,
                reason="re-ask needs the DIARIZE/model-invoked re-ask apparatus backbone design "
                "doc SS5.3 reserves for a future arm",
            )
        )

    if task.kind is TaskKind.ANSWER_QUESTION:
        raise TaskDispatchNotImplementedError(
            _DISPATCH_PRECONDITION.format(
                kind=task.kind.value,
                reason="the qa head (meeting_minutes_agent.heads.qa) is built, but "
                "build_dispatch_unit has no request-wiring for it yet -- a separate, "
                "not-yet-built controller-integration ticket",
            )
        )

    raise ValueError(f"unknown task kind: {task.kind!r}")  # pragma: no cover - exhaustive enum above


# ---------------------------------------------------------------------------
# fold: parse a raw response + update EpisodeState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldResult:
    episode_state: EpisodeState
    new_resolved_segments: tuple[SegmentLike, ...]
    minutes_parse: MinutesParseResult | None
    pending_ledger_bullets: tuple[MinutesBulletClaim, ...]
    transcribe_parse: TranscribeAttributeParseResult | None = None


def _segments_from_transcribe_parse(
    parse: TranscribeAttributeParseResult, chunk: Chunk
) -> tuple[Segment, ...]:
    """Divide ``chunk``'s ``[start, end)`` span evenly across
    ``parse.segments`` (module docstring, "Design note: synthetic segment
    timing"). An empty parse produces no segments."""

    n = len(parse.segments)
    if n == 0:
        return ()
    span = max(chunk.end - chunk.start, 0.0)
    step = span / n
    out = []
    for i, seg in enumerate(parse.segments):
        start = chunk.start + step * i
        end = chunk.start + step * (i + 1) if i < n - 1 else chunk.end
        out.append(
            Segment(
                id=f"c{chunk.index:04d}-s{i:04d}",
                speaker=seg.speaker,
                start=start,
                end=end,
                text=seg.text,
            )
        )
    return tuple(out)


def _fold_transcribe_span(
    unit: DispatchUnit,
    raw_response_text: str,
    *,
    episode_state: EpisodeState,
    glossary_arm: ArmKind,
) -> FoldResult:
    assert unit.chunk is not None
    parse = parse_transcribe_attribute_response(raw_response_text)
    new_segments = _segments_from_transcribe_parse(parse, unit.chunk)

    chunk_text = " ".join(seg.text for seg in parse.segments)
    if chunk_text.strip():
        constructor = GLOSSARY_ARM_CONSTRUCTORS[glossary_arm]
        arm_plan: ArmPlan = constructor(chunk_text, chunk_index=unit.task.chunk_index, introduced_by=None)
        entries: tuple[GlossaryEntry, ...] = arm_plan.entries
        if glossary_arm is ArmKind.NO_CARRY:
            import dataclasses as _dc

            episode_state = _dc.replace(episode_state, glossary=entries)
        else:
            episode_state = episode_state.with_glossary_chunk(entries)

    for seg in parse.segments:
        name = find_self_introduction(seg.text)
        if name is not None:
            episode_state = episode_state.bind_speaker(
                cluster_id=seg.speaker,
                roster_name=name,
                source=SpeakerEvidenceSource.SELF_INTRODUCTION,
                chunk=unit.task.chunk_index,
                quote=seg.text,
            )

    return FoldResult(
        episode_state=episode_state,
        new_resolved_segments=new_segments,
        minutes_parse=None,
        pending_ledger_bullets=(),
        transcribe_parse=parse,
    )


def _fold_summarize_section(unit: DispatchUnit, raw_response_text: str, *, episode_state: EpisodeState) -> FoldResult:
    parse = parse_minutes_response(raw_response_text)
    bullets = tuple(b for b in parse.bullets if b.section in _LEDGER_SECTIONS)
    return FoldResult(
        episode_state=episode_state,
        new_resolved_segments=(),
        minutes_parse=parse,
        pending_ledger_bullets=bullets,
    )


def _fold_resolve_ledger(
    unit: DispatchUnit,
    *,
    episode_state: EpisodeState,
    pending_ledger_bullets: Sequence[MinutesBulletClaim],
) -> FoldResult:
    for bullet in pending_ledger_bullets:
        kind = _LEDGER_SECTIONS.get(bullet.section)
        if kind is None:
            continue
        evidence = (bullet.claimed_span_id,) if bullet.claimed_span_id else ()
        episode_state = episode_state.add_ledger_entry(
            kind=kind,
            text=bullet.text,
            owner_speaker=bullet.claimed_speaker,
            chunk=unit.task.chunk_index,
            evidence_span_refs=evidence,
        )
    return FoldResult(
        episode_state=episode_state,
        new_resolved_segments=(),
        minutes_parse=None,
        pending_ledger_bullets=(),
    )


def fold_dispatch_result(
    unit: DispatchUnit,
    raw_response_text: str,
    *,
    episode_state: EpisodeState,
    glossary_arm: ArmKind = ArmKind.GATED,
    pending_ledger_bullets: Sequence[MinutesBulletClaim] = (),
) -> FoldResult:
    """Parse ``raw_response_text`` (empty/ignored for ``ledger_local``) per
    ``unit.fold_kind`` and fold the result into ``episode_state``. Pure:
    returns a :class:`FoldResult`, never mutates ``episode_state`` itself
    (frozen dataclass, ``with_*``/``bind_speaker``/``add_ledger_entry`` all
    already return NEW states)."""

    if unit.fold_kind == "transcribe_attribute":
        return _fold_transcribe_span(unit, raw_response_text, episode_state=episode_state, glossary_arm=glossary_arm)
    if unit.fold_kind == "minutes":
        return _fold_summarize_section(unit, raw_response_text, episode_state=episode_state)
    if unit.fold_kind == "ledger_local":
        return _fold_resolve_ledger(unit, episode_state=episode_state, pending_ledger_bullets=pending_ledger_bullets)
    raise ValueError(f"unknown fold_kind: {unit.fold_kind!r}")  # pragma: no cover - set only by this module


__all__ = [
    "GLOSSARY_ARM_CONSTRUCTORS",
    "TaskDispatchNotImplementedError",
    "find_self_introduction",
    "DispatchUnit",
    "build_dispatch_unit",
    "FoldResult",
    "fold_dispatch_result",
]
