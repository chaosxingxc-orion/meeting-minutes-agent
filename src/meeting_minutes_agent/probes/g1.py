"""G1 floors campaign -- the four registered arm constructors.

Registered design: ``docs/readiness/2026-08-19-g1-floors-preregistration.md``
(REGISTERED, owner GO 2026-08-19) SS3, over the arm redesign in
``docs/readiness/2026-08-18-g1-preregistration-draft.md`` SS2 and the locked
prompt form in ``docs/readiness/2026-08-18-pprompt-verdict.md``. Four arms:

| Arm      | Transport                                       | Turn source                   | Heads |
|----------|--------------------------------------------------|--------------------------------|-------|
| Z-turn   | 90s turn-aware, PRECOMP-cached                    | pinned diar (TOOL-LOCKED(B))  | transcribe-attribute + minutes + qa |
| Z-oracle | 90s turn-aware, PRECOMP-cached                    | oracle NXT turns               | transcribe-attribute + minutes + qa |
| Z-free   | same tool-turn slices, NO turn metadata in prompt | -- (transcribe-only head)      | transcribe only |
| Z-nodiar | pure-VAD 90s slicing                              | none                            | transcribe only |

Locked prompt form (T1-A1, the P-PROMPT sweep's mechanical winner): "the
bare pinned transcribe-attribute instruction + output-grammar contract,
nothing else, in the system turn" -- audio alone in the user turn, no
context block. Every transcribe request this module builds reuses that
EXACT form by construction, never re-typed: Z-turn/Z-oracle call
:func:`~meeting_minutes_agent.heads.transcribe_attribute.build_transcribe_attribute_request`
with ``supply_text=""`` and no ``span_context``/``declared_grid_turns``
(byte-identical to the P-PROMPT sweep's own T1 rendering,
``probes/pprompt.py``'s ``SYSTEM_INSTRUCTION_TEMPLATE`` reused verbatim);
Z-free/Z-nodiar call
:func:`~meeting_minutes_agent.heads.transcribe_attribute.build_transcribe_only_request`
with no supply text at all -- the "NO turn metadata in prompt" shape the
floors table's Z-free row and Z-nodiar's own by-construction absence of any
turn source both require.

Minutes and qa are wired on Z-turn/Z-oracle only (the floors table). Those
two heads were never part of the P-PROMPT sweep (which tested ONLY the
transcribe-attribute template's own axes), so there is no T1-A1-labelled
cell for them; this module applies the SAME underlying principle -- bare
head instruction, zero supply text, only the head's own load-bearing
structured content (the minutes head's transcript block; the qa head's
question block) -- rather than inventing a second interpretation. This is
a recorded design decision, not a re-derivation of a P-PROMPT result.

Two further recorded design decisions, both driven by the transport layer's
own hard per-request audio cap
(:data:`meeting_minutes_agent.chunking.constants.TRANSPORT_SLICE_MAX_S` =
120s, enforced unconditionally by
:meth:`meeting_minutes_agent.client.transport.LlamaServerTransport.request`):
neither minutes nor qa can carry a whole meeting's audio in one request.

- **Minutes' audio anchor is the arm's LAST transcribe slice** -- mirrors
  ``harness/episode.py``'s own convention of attributing
  ``SUMMARIZE_SECTION``/``RESOLVE_LEDGER`` to the LAST chunk index (that
  module's own docstring): the most recent audio at the point minutes is
  produced, always inside the transport bound, always a slice already cut
  and cached by PRECOMP (or the VAD supplement, for Z-nodiar -- though
  Z-nodiar itself carries no minutes head per the floors table).
- **QA's audio anchor is the arm's FIRST transcribe slice**, shared across
  every question asked about that meeting -- one designated, bounded audio
  window per (arm, meeting), never a per-question timestamp lookup
  (MeetingQA's own official schema carries no audio-grounding timestamp at
  all, per ``corpora/meetingqa/loader.py``'s module docstring). This
  reproduces the registered budget arithmetic exactly: N=200 capped
  questions x 2 arms (Z-turn, Z-oracle) = 400 QA requests, ONE call per
  question per arm, never a per-slice fan-out.

This module is a pure request BUILDER (mirrors ``probes/pprompt.py``'s own
scope: "no network call, no audio decode, zero model contact"): it consumes
an already-built, pure :class:`~meeting_minutes_agent.chunking.slicer.SlicePlan`
for its arm's own turn source and returns deterministic :class:`G1RequestSpec`
records. Resolving that plan from PRECOMP's on-disk cache (RTTM/oracle turns
-> slice plan -> cached slice-WAV filenames) is
:mod:`meeting_minutes_agent.probes.g1_campaign`'s job, exactly mirroring how
``scripts/launch_pprompt_sweep.py`` resolves real I/O while
``probes/pprompt.py`` itself stays I/O-free.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..chunking.leakage import BoundaryProvenance
from ..chunking.models import SegmentLike
from ..chunking.slicer import Slice, SlicePlan, SlicePlanMode, SliceTurnEntry
from ..heads.minutes import build_minutes_request
from ..heads.qa import build_qa_request
from ..heads.request import HeadRequest
from ..heads.transcribe_attribute import (
    SYSTEM_INSTRUCTION_TEMPLATE,
    TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE,
    build_transcribe_attribute_request,
    build_transcribe_only_request,
)

SCHEMA_VERSION = "1.0.0"

ARM_Z_TURN = "Z-turn"
ARM_Z_ORACLE = "Z-oracle"
ARM_Z_FREE = "Z-free"
ARM_Z_NODIAR = "Z-nodiar"
ARMS: tuple[str, ...] = (ARM_Z_TURN, ARM_Z_ORACLE, ARM_Z_FREE, ARM_Z_NODIAR)

#: Arms whose heads include minutes + qa on top of transcribe (floors prereg SS3 table).
ARMS_WITH_MINUTES_QA: tuple[str, ...] = (ARM_Z_TURN, ARM_Z_ORACLE)
#: Arms that attempt attribution from audio alone (the transcribe-attribute head).
ARMS_WITH_ATTRIBUTION: tuple[str, ...] = (ARM_Z_TURN, ARM_Z_ORACLE)
#: Arms that carry no attribution instruction at all (the transcribe-only head).
ARMS_TRANSCRIBE_ONLY: tuple[str, ...] = (ARM_Z_FREE, ARM_Z_NODIAR)

#: The BoundaryProvenance (or, for Z-nodiar, the SlicePlanMode) each arm's
#: slice plan must carry -- checked defensively by every builder below so a
#: caller cannot silently feed Z-turn an oracle plan or vice versa.
EXPECTED_PROVENANCE: dict[str, BoundaryProvenance | None] = {
    ARM_Z_TURN: BoundaryProvenance.TOOL_DIAR,
    ARM_Z_ORACLE: BoundaryProvenance.ORACLE_TURN,
    ARM_Z_FREE: BoundaryProvenance.TOOL_DIAR,  # "same tool-turn slices" (floors prereg SS3)
    ARM_Z_NODIAR: None,  # pure-VAD: SlicePlanMode.VAD carries no turn_provenance
}

#: QA question set (floors prereg SS2): usable-discovery questions attached
#: to dev-18, seeded cap N=200, seed 20260818 (disclosed per SS2/SS7).
QA_CAP_N = 200
QA_CAP_SEED = 20260818


class G1Error(ValueError):
    """A fail-closed refusal in this module: an unknown arm, a slice plan
    whose provenance/mode does not match the arm's own registered turn
    source, or an empty plan/question set a request cannot be built from."""


class G1VadSupplementMissingError(FileNotFoundError):
    """Z-nodiar's slices are consumed, read-only, from wherever the PRECOMP
    VAD supplement (a separate, concurrently-developed extension to
    ``precomp/`` this mission does not touch) has materialized them.
    Fail-closed (floors prereg SS3: "the supplement is the default... fails
    closed if absent"): raised by :func:`load_vad_slice_plan` when the named
    manifest path does not exist, rather than falling back to lazy encode or
    a fabricated slice plan."""


# ---------------------------------------------------------------------------
# arm validation
# ---------------------------------------------------------------------------


def _assert_arm(arm: str) -> None:
    if arm not in ARMS:
        raise G1Error(f"unknown G1 arm {arm!r}; expected one of {ARMS}")


def _assert_plan_matches_arm(arm: str, plan: SlicePlan) -> None:
    if arm == ARM_Z_NODIAR:
        if plan.mode is not SlicePlanMode.VAD:
            raise G1Error(f"{arm} requires a VAD-mode slice plan, got mode={plan.mode!r}")
        if plan.turn_provenance is not None:
            raise G1Error(
                f"{arm} requires a slice plan with no turn provenance, got {plan.turn_provenance!r}"
            )
        return
    expected = EXPECTED_PROVENANCE[arm]
    if plan.turn_provenance is not expected:
        raise G1Error(
            f"{arm} requires a slice plan with turn_provenance={expected!r}, got {plan.turn_provenance!r}"
        )


# ---------------------------------------------------------------------------
# T1-A1-locked transcribe request (module docstring)
# ---------------------------------------------------------------------------


def build_transcribe_request_for_arm(arm: str) -> HeadRequest:
    """The T1-A1-locked transcribe request for ``arm`` (module docstring).
    Every branch passes zero supply text and zero span/grid context, so the
    built request is byte-identical in FORM to the P-PROMPT sweep's own
    winning T1-A1 cell: the pinned template string as the sole system-turn
    content, and an empty ``supplied_text`` tuple (audio alone in the user
    turn)."""

    _assert_arm(arm)
    if arm in ARMS_WITH_ATTRIBUTION:
        return build_transcribe_attribute_request(supply_text="")
    return build_transcribe_only_request()


def assert_t1_a1_form(head_request: HeadRequest, *, attribution: bool) -> None:
    """Assert ``head_request`` is exactly the locked T1-A1 form: the bare
    pinned instruction (whichever of the two transcribe templates
    ``attribution`` selects) and no supplied text at all. A shared,
    reusable assertion so every caller (this module's own builders, and this
    module's tests) checks the SAME thing the SAME way."""

    expected_instruction = SYSTEM_INSTRUCTION_TEMPLATE if attribution else TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE
    if head_request.task_instruction != expected_instruction:
        raise G1Error("head_request.task_instruction does not match the locked T1-A1 instruction text")
    if head_request.supplied_text != ():
        raise G1Error(
            f"head_request carries supplied_text={head_request.supplied_text!r}; the locked T1-A1 "
            "form carries NO context block -- audio alone in the user turn"
        )


# ---------------------------------------------------------------------------
# request spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class G1RequestSpec:
    """One built request: everything the campaign runner needs to dispatch
    it via :class:`meeting_minutes_agent.client.transport.LlamaServerTransport`,
    plus the metadata a later read needs to reassemble per-meeting/per-arm
    scoring inputs."""

    request_id: str
    arm: str
    meeting_id: str
    kind: str  # "transcribe" | "minutes" | "qa"
    slice_index: int | None
    audio_relpath: str
    audio_seconds: float
    head_request: HeadRequest
    question_id: str | None = None

    def to_transport_kwargs(self, *, data_dir: Path | str) -> dict[str, object]:
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
            "kind": self.kind,
            "slice_index": self.slice_index,
            "audio_relpath": self.audio_relpath,
            "audio_seconds": self.audio_seconds,
            "template_id": self.head_request.template_id,
            "question_id": self.question_id,
        }


def _request_id(
    arm: str, meeting_id: str, kind: str, *, slice_index: int | None = None, question_id: str | None = None
) -> str:
    if kind == "transcribe":
        if slice_index is None:
            raise G1Error("_request_id(kind='transcribe', ...) requires slice_index")
        return f"g1-{arm}-{meeting_id}-transcribe-slice{slice_index:04d}"
    if kind == "minutes":
        return f"g1-{arm}-{meeting_id}-minutes"
    if kind == "qa":
        if question_id is None:
            raise G1Error("_request_id(kind='qa', ...) requires question_id")
        return f"g1-{arm}-{meeting_id}-qa-{question_id}"
    raise G1Error(f"unknown request kind {kind!r}; expected 'transcribe', 'minutes' or 'qa'")


#: The deterministic slice-WAV filename convention
#: ``chunking.slicer.materialize_slice_plan`` writes
#: (``f"{meeting_id}-slice{index:04d}.wav"``) -- reused here so a caller can
#: resolve already-cut, cached slice audio by filename alone from a pure
#: :class:`~meeting_minutes_agent.chunking.slicer.SlicePlan`, without
#: re-decoding audio or recomputing a sha256 this module's own
#: request-building has no need for.
def slice_filename(meeting_id: str, slice_index: int) -> str:
    return f"{meeting_id}-slice{slice_index:04d}.wav"


def _slice_audio_relpath(meeting_id: str, slice_index: int, *, slice_dir_relative: str) -> str:
    return f"{slice_dir_relative}/{meeting_id}/{slice_filename(meeting_id, slice_index)}"


# ---------------------------------------------------------------------------
# transcribe requests (all four arms)
# ---------------------------------------------------------------------------


def build_transcribe_requests(
    arm: str, meeting_id: str, plan: SlicePlan, *, slice_dir_relative: str
) -> tuple[G1RequestSpec, ...]:
    """One ``transcribe`` :class:`G1RequestSpec` per slice in ``plan``, in
    slice order -- the per-slice dispatch chain item-14 names
    (``harness/episode.py``'s own docstring), reproduced here at the request-
    builder level for a campaign that bypasses the full harness/controller
    loop (mirrors every other probe in this package)."""

    _assert_arm(arm)
    _assert_plan_matches_arm(arm, plan)
    head_request = build_transcribe_request_for_arm(arm)
    specs = []
    for sl in plan.slices:
        specs.append(
            G1RequestSpec(
                request_id=_request_id(arm, meeting_id, "transcribe", slice_index=sl.index),
                arm=arm,
                meeting_id=meeting_id,
                kind="transcribe",
                slice_index=sl.index,
                audio_relpath=_slice_audio_relpath(meeting_id, sl.index, slice_dir_relative=slice_dir_relative),
                audio_seconds=sl.duration,
                head_request=head_request,
            )
        )
    return tuple(specs)


# ---------------------------------------------------------------------------
# minutes request (Z-turn / Z-oracle only)
# ---------------------------------------------------------------------------


def build_minutes_request_for_meeting(
    arm: str,
    meeting_id: str,
    plan: SlicePlan,
    resolved_transcript: Sequence[SegmentLike],
    *,
    slice_dir_relative: str,
) -> G1RequestSpec:
    """The minutes head's request for one meeting, anchored on the arm's
    LAST transcribe slice (module docstring). ``resolved_transcript`` is the
    already-resolved attributed transcript this meeting's own transcribe
    stage produced (a caller-supplied input, exactly like the underlying
    head's own :func:`~meeting_minutes_agent.heads.minutes.build_minutes_request`
    signature -- this module never invents a transcript)."""

    _assert_arm(arm)
    if arm not in ARMS_WITH_MINUTES_QA:
        raise G1Error(f"{arm} carries no minutes head; expected one of {ARMS_WITH_MINUTES_QA}")
    _assert_plan_matches_arm(arm, plan)
    if not plan.slices:
        raise G1Error(f"cannot anchor a minutes request for meeting {meeting_id!r}: its slice plan is empty")

    anchor = plan.slices[-1]
    head_request = build_minutes_request(supply_text="", resolved_transcript=resolved_transcript)
    return G1RequestSpec(
        request_id=_request_id(arm, meeting_id, "minutes"),
        arm=arm,
        meeting_id=meeting_id,
        kind="minutes",
        slice_index=anchor.index,
        audio_relpath=_slice_audio_relpath(meeting_id, anchor.index, slice_dir_relative=slice_dir_relative),
        audio_seconds=anchor.duration,
        head_request=head_request,
    )


# ---------------------------------------------------------------------------
# QA requests (Z-turn / Z-oracle only) + the seeded question cap
# ---------------------------------------------------------------------------


def select_capped_qa_questions(
    questions: Sequence[Any], *, cap: int = QA_CAP_N, seed: int = QA_CAP_SEED, id_of: Any = lambda q: q.example_id
) -> tuple[Any, ...]:
    """The registered QA cap (floors prereg SS2: "seeded cap N=200, seed
    20260818, cap disclosed"). ``questions`` may be handed in ANY order --
    this function sorts by ``id_of(question)`` first, so the result is
    deterministic regardless of the caller's own iteration order (e.g. a
    dict-derived or filesystem-derived listing), then draws a fixed-size
    sample via ``random.Random(seed).shuffle`` over the index list, and
    returns the CHOSEN subset back in its original (sorted) relative order
    -- never in shuffle order, so a downstream reader sees the cap applied,
    not an additional reshuffling. Returns ``questions`` unchanged (as a
    tuple) when ``len(questions) <= cap`` -- the cap never pads a short
    list."""

    ordered = tuple(sorted(questions, key=id_of))
    if len(ordered) <= cap:
        return ordered
    rng = random.Random(seed)
    indices = list(range(len(ordered)))
    rng.shuffle(indices)
    chosen = sorted(indices[:cap])
    return tuple(ordered[i] for i in chosen)


def questions_for_meeting(
    questions: Sequence[Any], meeting_id: str, *, meeting_id_of: Any = lambda q: q.meeting_id
) -> tuple[Any, ...]:
    """Filter an already-capped, campaign-wide QA question set (
    :func:`select_capped_qa_questions`'s own output) down to exactly the
    questions attached to ``meeting_id``, preserving the input's own
    relative order. This is the per-meeting routing step
    :func:`build_qa_requests_for_meeting` itself does not perform (that
    function anchors whatever ``questions`` it is handed -- it never
    filters by meeting): a caller (the campaign runner) must call this
    FIRST, so a question about one meeting is never asked over a different
    meeting's audio. ``meeting_id_of`` mirrors :func:`select_capped_qa_questions`'s
    own ``id_of`` seam, so this stays decoupled from any one question
    record's concrete shape."""

    return tuple(q for q in questions if meeting_id_of(q) == meeting_id)


def build_qa_requests_for_meeting(
    arm: str,
    meeting_id: str,
    plan: SlicePlan,
    questions: Sequence[Any],
    *,
    slice_dir_relative: str,
    question_of: Any = lambda q: q.question,
    id_of: Any = lambda q: q.example_id,
) -> tuple[G1RequestSpec, ...]:
    """One ``qa`` :class:`G1RequestSpec` per question in ``questions``
    (already capped by :func:`select_capped_qa_questions`, and already
    routed to THIS meeting by :func:`questions_for_meeting` -- this function
    applies neither the cap nor the routing itself, so a caller can share
    one capped set across both QA-bearing arms without re-sampling), all
    anchored on the SAME first-slice audio window (module docstring).
    ``questions`` may legitimately be empty (a meeting the cap drew zero
    questions for, e.g. ``IS1008a`` in the registered G1-PATH roster): this
    is tolerated, returning zero requests, never an error -- the empty-set
    case is a normal outcome of per-meeting routing, not a caller mistake
    like an unknown arm or a mismatched plan."""

    _assert_arm(arm)
    if arm not in ARMS_WITH_MINUTES_QA:
        raise G1Error(f"{arm} carries no qa head; expected one of {ARMS_WITH_MINUTES_QA}")
    _assert_plan_matches_arm(arm, plan)
    if not questions:
        return ()
    if not plan.slices:
        raise G1Error(f"cannot anchor a qa request for meeting {meeting_id!r}: its slice plan is empty")

    anchor = plan.slices[0]
    audio_relpath = _slice_audio_relpath(meeting_id, anchor.index, slice_dir_relative=slice_dir_relative)
    specs = []
    for q in questions:
        head_request = build_qa_request(question=question_of(q), supply_text="")
        specs.append(
            G1RequestSpec(
                request_id=_request_id(arm, meeting_id, "qa", question_id=id_of(q)),
                arm=arm,
                meeting_id=meeting_id,
                kind="qa",
                slice_index=anchor.index,
                audio_relpath=audio_relpath,
                audio_seconds=anchor.duration,
                head_request=head_request,
                question_id=id_of(q),
            )
        )
    return tuple(specs)


# ---------------------------------------------------------------------------
# Z-nodiar: consume the PRECOMP VAD supplement's manifest, fail-closed
# ---------------------------------------------------------------------------


def _slice_plan_from_dict(document: Mapping[str, Any]) -> SlicePlan:
    """Reconstruct a :class:`SlicePlan` from its own
    :meth:`~meeting_minutes_agent.chunking.slicer.SlicePlan.to_dict` JSON
    shape -- a plain round-trip over ``chunking.slicer``'s pure dataclasses.
    This module never modifies ``chunking/slicer.py`` itself (a separate,
    concurrently-developed mission owns that module's VAD-supplement
    extension); it only reads the shape that module already, stably,
    exports."""

    mode = SlicePlanMode(document["mode"])
    turn_provenance_raw = document.get("turn_provenance")
    turn_provenance = BoundaryProvenance(turn_provenance_raw) if turn_provenance_raw is not None else None
    slices = tuple(
        Slice(
            index=int(s["index"]),
            start=float(s["start"]),
            end=float(s["end"]),
            vad_snap_applied=bool(s["vad_snap_applied"]),
            turns=tuple(
                SliceTurnEntry(
                    speaker=str(t["speaker"]),
                    absolute_start=float(t["absolute_start"]),
                    absolute_end=float(t["absolute_end"]),
                    slice_offset_start=float(t["slice_offset_start"]),
                    slice_offset_end=float(t["slice_offset_end"]),
                )
                for t in s.get("turns", ())
            ),
        )
        for s in document["slices"]
    )
    return SlicePlan(
        meeting_id=str(document["meeting_id"]),
        mode=mode,
        turn_provenance=turn_provenance,
        total_duration_s=float(document["total_duration_s"]),
        slices=slices,
        content_hash=str(document["content_hash"]),
    )


def load_vad_slice_plan(path: Path | str) -> SlicePlan:
    """Load a materialized VAD :class:`SlicePlan` JSON (the shape
    ``SlicePlan.to_dict()`` produces) from ``path``. Fail-closed (module
    docstring): raises :class:`G1VadSupplementMissingError` when ``path``
    does not exist, rather than lazily encoding audio or fabricating a plan
    -- the floors prereg SS3 rule this campaign runs under."""

    resolved = Path(path)
    if not resolved.is_file():
        raise G1VadSupplementMissingError(
            f"Z-nodiar VAD slice-plan manifest not found at {resolved} -- the PRECOMP VAD "
            "supplement (a separate, concurrently-developed extension to precomp/) has not "
            "produced it yet; Z-nodiar refuses to fall back to lazy encode or a fabricated plan "
            "(docs/readiness/2026-08-19-g1-floors-preregistration.md SS3)"
        )
    document = json.loads(resolved.read_text(encoding="utf-8"))
    return _slice_plan_from_dict(document)


__all__ = [
    "SCHEMA_VERSION",
    "ARM_Z_TURN",
    "ARM_Z_ORACLE",
    "ARM_Z_FREE",
    "ARM_Z_NODIAR",
    "ARMS",
    "ARMS_WITH_MINUTES_QA",
    "ARMS_WITH_ATTRIBUTION",
    "ARMS_TRANSCRIBE_ONLY",
    "EXPECTED_PROVENANCE",
    "QA_CAP_N",
    "QA_CAP_SEED",
    "G1Error",
    "G1VadSupplementMissingError",
    "build_transcribe_request_for_arm",
    "assert_t1_a1_form",
    "G1RequestSpec",
    "slice_filename",
    "build_transcribe_requests",
    "build_minutes_request_for_meeting",
    "select_capped_qa_questions",
    "questions_for_meeting",
    "build_qa_requests_for_meeting",
    "load_vad_slice_plan",
]
