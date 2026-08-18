"""P-PROMPT template-and-arrangement sweep: the 14-arm request builder.

Pre-registered design (``docs/readiness/2026-08-18-pprompt-preregistration.md``,
binding on the exact grid/metric/rule text this module implements): a
4-template x 3-arrangement grid (12 cells) plus 2 corrupt-context controls
(X1, X2), each flown on the SAME frozen P-ATTR 24-slice manifest
(``configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json``, reused
VERBATIM by reference -- this module never rebuilds it, see
:mod:`meeting_minutes_agent.probes.pattr`) = 336 requests.

This module is a pure request BUILDER, mirroring :mod:`.pattr`'s own scope
("a prompt template builder + a response parser, no transport calls"): it
reads an already-loaded :class:`~.pattr.PattrManifest` and returns
deterministic :class:`PpromptRequestSpec` records. No network call, no audio
decode, zero model contact.

Template axis (4) -- every cell shares the SAME base task instruction, the
transcribe-attribute head's own pinned grammar contract
(:data:`meeting_minutes_agent.heads.transcribe_attribute.
SYSTEM_INSTRUCTION_TEMPLATE`, the ``<speaker>|<text>`` line grammar), never
re-typed here (T1 is that string with nothing else added):

- T1 minimal: the bare instruction + grammar contract, nothing else.
- T2 deployment-baseline: T1 + :func:`render_meeting_context_block` (meeting
  id, the PER-SLICE speaker roster read from the frozen manifest's own turn
  metadata -- ``entry["turns"]``, never a separate corpus lookup -- and a
  one-line task-framing sentence).
- T3 = T2 + an explicitly EMPTY glossary slot, reusing this repository's own
  empty-glossary convention verbatim
  (:data:`meeting_minutes_agent.supply.templates.GLOSSARY_SECTION_HEADER` /
  :data:`~meeting_minutes_agent.supply.templates.GLOSSARY_EMPTY_LINE`).
- T4 = T2 + a reinforced output-grammar section restating the grammar with
  one worked example line.

Arrangement axis (3) -- WHERE a template's own extra block (the part T2/T3/T4
add beyond T1's bare instruction; T1 has none, so all three arrangements of
T1 render an IDENTICAL request, a documented, harmless consequence of
honoring the registered 4x3 grid literally) lands in the wire request:

- A1: appended to the SYSTEM message (``task_instruction``).
- A2: a USER-message text part placed BEFORE the audio part.
- A3: a USER-message text part placed AFTER the audio part -- this needs
  :func:`meeting_minutes_agent.client.transport.build_request_payload`'s
  ``supplied_text_after_audio`` parameter (added alongside this module,
  additive/backward-compatible: every existing caller that never sets it
  gets byte-identical behaviour).

Corrupt-context controls (both built ONLY on the T2/A1 reference cell,
:data:`REFERENCE_CELL`, pre-registered to avoid winner-conditioned
circularity):

- X1 wrong-roster: this repository's AMI/NXT turn layer carries bare,
  MEETING-INVARIANT speaker labels (A/B/C/D on every one of the four P-ATTR
  smoke meetings -- confirmed against the frozen manifest before this module
  was written), so swapping in a different meeting's roster is a byte-for-
  byte no-op. Per the mission's own fallback instruction, X1 instead corrupts
  the TURN-TO-LABEL mapping the per-slice roster is read off: a seeded
  fixed-point-free derangement of the label alphabet
  (:func:`seeded_label_derangement`) is applied to every slice's OWN roster
  before rendering, so the declared "speakers in this excerpt" set is
  actually wrong relative to the audio (a label that never spoke can appear;
  one that did can be missing) -- a real corruption of the attribution
  channel, not a cosmetic relabeling of an anonymous set.
- X2 stale-tail: a rolling text tail (the deployment design's own carried-
  history mechanic, ``docs/readiness/2026-08-18-g1-preregistration-draft.md``
  SS0b(3)), reusing the transcribe-attribute head's existing
  ``CONTEXT_SECTION_HEADER`` "prior spans" block convention, but sourced from
  a DIFFERENT meeting's MODEL-GENERATED text (the P-ATTR smoke's own archived
  A-turn replies -- never gold; the hard legality line this whole repository
  runs under) and presented as if it were this meeting's own history. This
  module never reads that JSONL itself (a request builder stays I/O-free,
  module docstring); it accepts already-resolved, already-hash-verified
  :class:`~meeting_minutes_agent.chunking.models.Segment` tail entries from
  its caller (the launcher / binding-manifest builder), exactly mirroring
  how :meth:`PpromptRequestSpec.to_transport_kwargs` resolves audio bytes
  only when a caller hands it a ``data_dir``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..chunking.models import Segment
from ..heads.transcribe_attribute import CONTEXT_SECTION_HEADER, SYSTEM_INSTRUCTION_TEMPLATE
from ..runreceipt import config_hash
from ..supply.templates import GLOSSARY_EMPTY_LINE, GLOSSARY_SECTION_HEADER
from .pattr import PattrManifest

SCHEMA_VERSION = "1.0.0"

TEMPLATES: tuple[str, ...] = ("T1", "T2", "T3", "T4")
ARRANGEMENTS: tuple[str, ...] = ("A1", "A2", "A3")
GRID_CELLS: tuple[str, ...] = tuple(f"{template}-{arrangement}" for template in TEMPLATES for arrangement in ARRANGEMENTS)

ARM_X1 = "X1"
ARM_X2 = "X2"
CORRUPT_ARMS: tuple[str, ...] = (ARM_X1, ARM_X2)
ARMS: tuple[str, ...] = GRID_CELLS + CORRUPT_ARMS  # 14

#: The fixed reference cell the corrupt-context controls are measured
#: against (prereg SS3: "on the fixed reference cell T2/A1 only").
REFERENCE_CELL = "T2-A1"

#: AMI's own diarization/turn layer alphabet on the frozen P-ATTR manifest's
#: four selected meetings (verified meeting-invariant before this module was
#: written -- module docstring, X1). A derangement over a DIFFERENT alphabet
#: (e.g. a future manifest with more speakers) still works: every function
#: below takes the alphabet from the DATA (the manifest's own turn labels),
#: never hardcodes this tuple as an assumption.
CANONICAL_AMI_LABELS: tuple[str, ...] = ("A", "B", "C", "D")

MEETING_CONTEXT_SECTION_HEADER = "=== MEETING CONTEXT ==="
REINFORCED_GRAMMAR_SECTION_HEADER = "=== OUTPUT FORMAT (reinforced) ==="
REINFORCED_GRAMMAR_EXAMPLE_TEXT = (
    "Follow the <speaker>|<text> grammar exactly, one line per speech segment. "
    "Example of one valid line:\nA|Let's get started with today's agenda.\n"
    "Output nothing else: no headings, no blank lines, no commentary before, "
    "between, or after the lines."
)


class PpromptError(ValueError):
    """A fail-closed refusal in this module: an unknown template/arrangement/
    arm id, or a derangement request this module cannot satisfy."""


# ---------------------------------------------------------------------------
# roster + template-block rendering (pure)
# ---------------------------------------------------------------------------


def roster_for_entry(entry: Mapping[str, Any]) -> tuple[str, ...]:
    """The distinct speaker labels appearing in one slice's OWN turn table
    (``entry["turns"]``, the frozen P-ATTR manifest's per-slice field),
    sorted for a deterministic presentation order. This is "the speaker
    roster from turn metadata" the T2 template's own definition names --
    never a separate corpus lookup, and never assumed identical across
    slices (AMI turn coverage varies slice to slice)."""

    return tuple(sorted({str(t["speaker"]) for t in entry["turns"]}))


def render_meeting_context_block(meeting_id: str, roster: Sequence[str]) -> str:
    """The §0b deployment-baseline context block this repository's corpora
    layer can actually support: AMI/NXT (:mod:`meeting_minutes_agent.corpora.
    nxt`) carries no participant name/role/agenda data reachable from
    ``ResolvedMeeting`` (checked before this module was written -- its fields
    are exactly ``meeting_id``/``transcript``/``dialogue_acts``/``minutes``/
    ``evidence_links``/``topics``/``orphans``), so "title/type" here is the
    meeting id plus the generic, true-for-every-P-ATTR-meeting fact that it
    is an AMI scenario meeting, and "roster with roles" is the bare-label
    roster :func:`roster_for_entry` reads off the turn layer -- an honest,
    recorded scope limit, never a fabricated name/role/agenda."""

    roster_text = ", ".join(roster) if roster else "(no speaker turns observed in this excerpt)"
    return (
        f"{MEETING_CONTEXT_SECTION_HEADER}\n"
        f"Meeting: {meeting_id} (AMI scenario meeting)\n"
        f"Speakers in this excerpt (from turn metadata): {roster_text}\n"
        "Task: you are assisting with meeting-minutes preparation for this "
        "meeting; transcribe and attribute this excerpt accurately using the "
        "speakers listed above."
    )


def render_empty_glossary_block() -> str:
    """T3's "explicitly EMPTY glossary slot" -- the SAME empty-glossary
    convention :mod:`meeting_minutes_agent.supply.render` already uses
    (``GLOSSARY_SECTION_HEADER`` / ``GLOSSARY_EMPTY_LINE``), reused verbatim
    rather than re-typed, so a future change to that convention's wording
    updates this template too."""

    return f"{GLOSSARY_SECTION_HEADER}\n{GLOSSARY_EMPTY_LINE}"


def render_reinforced_grammar_block() -> str:
    """T4's reinforced output-grammar section: the grammar contract restated
    with one worked ``<speaker>|<text>`` example line, per the prereg's own
    T4 definition."""

    return f"{REINFORCED_GRAMMAR_SECTION_HEADER}\n{REINFORCED_GRAMMAR_EXAMPLE_TEXT}"


def template_extra_block(template_id: str, meeting_id: str, roster: Sequence[str]) -> str | None:
    """The FULL content T2/T3/T4 add beyond T1's bare instruction (``None``
    for T1) -- exactly the unit the arrangement axis moves around (module
    docstring)."""

    if template_id == "T1":
        return None
    context = render_meeting_context_block(meeting_id, roster)
    if template_id == "T2":
        return context
    if template_id == "T3":
        return context + "\n\n" + render_empty_glossary_block()
    if template_id == "T4":
        return context + "\n\n" + render_reinforced_grammar_block()
    raise PpromptError(f"unknown template id {template_id!r}; expected one of {TEMPLATES}")


# ---------------------------------------------------------------------------
# rendered prompt content + placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PpromptPromptContent:
    """One arm's fully rendered prompt content: the system-message text plus
    the user-message text parts split around where the audio part goes
    (:attr:`supplied_text_before_audio` / :attr:`supplied_text_after_audio`).
    Deliberately NOT :class:`meeting_minutes_agent.heads.request.HeadRequest`
    -- that shared shape has no "after audio" slot (module docstring); this
    is P-PROMPT's own small, local content type with its own transport-kwargs
    seam, so no other head/probe's pinned shape is touched by this sweep."""

    task_instruction: str
    supplied_text_before_audio: tuple[str, ...] = ()
    supplied_text_after_audio: tuple[str, ...] = ()
    arm: str = ""
    content_sha256: str = ""

    def to_transport_kwargs(self, *, request_id: str, audio_path: Path, audio_seconds: float) -> dict[str, object]:
        return {
            "request_id": request_id,
            "task_instruction": self.task_instruction,
            "audio_path": audio_path,
            "audio_seconds": audio_seconds,
            "supplied_text": self.supplied_text_before_audio,
            "supplied_text_after_audio": self.supplied_text_after_audio,
            "decoding_params": {},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_instruction": self.task_instruction,
            "supplied_text_before_audio": list(self.supplied_text_before_audio),
            "supplied_text_after_audio": list(self.supplied_text_after_audio),
            "arm": self.arm,
            "content_sha256": self.content_sha256,
        }


def content_hash(task_instruction: str, before: Sequence[str], after: Sequence[str]) -> str:
    """The one hashing rule every rendering in this module goes through --
    used both by the request builders below and by
    ``scripts/build_pprompt_binding.py`` to pin renderings into the frozen
    binding manifest, so a binding-manifest hash and a freshly-built
    request's hash are always computed the identical way."""

    return config_hash(
        {
            "task_instruction": task_instruction,
            "supplied_text_before_audio": list(before),
            "supplied_text_after_audio": list(after),
        }
    )


def render_cell_prompt(template_id: str, arrangement_id: str, meeting_id: str, roster: Sequence[str]) -> PpromptPromptContent:
    """One of the 12 grid cells' rendering for one meeting/slice's roster."""

    if arrangement_id not in ARRANGEMENTS:
        raise PpromptError(f"unknown arrangement id {arrangement_id!r}; expected one of {ARRANGEMENTS}")

    extra = template_extra_block(template_id, meeting_id, roster)
    base = SYSTEM_INSTRUCTION_TEMPLATE
    if extra is None:
        task_instruction, before, after = base, (), ()
    elif arrangement_id == "A1":
        task_instruction, before, after = base + "\n\n" + extra, (), ()
    elif arrangement_id == "A2":
        task_instruction, before, after = base, (extra,), ()
    else:  # "A3"
        task_instruction, before, after = base, (), (extra,)

    arm = f"{template_id}-{arrangement_id}"
    return PpromptPromptContent(
        task_instruction=task_instruction,
        supplied_text_before_audio=before,
        supplied_text_after_audio=after,
        arm=arm,
        content_sha256=content_hash(task_instruction, before, after),
    )


def render_x1_prompt(meeting_id: str, roster: Sequence[str], derangement: Mapping[str, str]) -> PpromptPromptContent:
    """X1 wrong-roster: the T2/A1 reference cell's rendering, but with the
    roster passed through ``derangement`` (module docstring) before it is
    rendered into the context block -- every OTHER ingredient (base
    instruction, arrangement, task framing) stays exactly the reference
    cell's own, so the delta this arm measures is attributable to the roster
    alone."""

    missing = [label for label in roster if label not in derangement]
    if missing:
        raise PpromptError(f"derangement is missing an entry for label(s) {missing} seen in meeting {meeting_id!r}")
    corrupted_roster = tuple(sorted({derangement[label] for label in roster}))
    extra = render_meeting_context_block(meeting_id, corrupted_roster)
    task_instruction = SYSTEM_INSTRUCTION_TEMPLATE + "\n\n" + extra
    return PpromptPromptContent(
        task_instruction=task_instruction,
        supplied_text_before_audio=(),
        supplied_text_after_audio=(),
        arm=ARM_X1,
        content_sha256=content_hash(task_instruction, (), ()),
    )


def render_x2_prompt(meeting_id: str, roster: Sequence[str], tail_segments: Sequence[Segment]) -> PpromptPromptContent:
    """X2 stale-tail: the T2/A1 reference cell's rendering (CLEAN roster,
    unchanged), plus a rolling tail block built from ``tail_segments`` --
    the caller's already-resolved donor-meeting text (module docstring) --
    placed as user-turn text BEFORE the audio, reusing the transcribe-
    attribute head's own ``CONTEXT_SECTION_HEADER`` "prior spans" line
    format so a reader familiar with that head recognizes the block shape
    immediately. An empty ``tail_segments`` renders identically to the plain
    reference cell (no tail block at all) -- never a block with an empty
    body, which would not be an honest "stale tail" arm."""

    extra = render_meeting_context_block(meeting_id, roster)
    task_instruction = SYSTEM_INSTRUCTION_TEMPLATE + "\n\n" + extra
    tail_lines = [f"[{segment.speaker}] {segment.text}" for segment in tail_segments]
    before: tuple[str, ...]
    if tail_lines:
        tail_block = CONTEXT_SECTION_HEADER + "\n" + "\n".join(tail_lines)
        before = (tail_block,)
    else:
        before = ()
    return PpromptPromptContent(
        task_instruction=task_instruction,
        supplied_text_before_audio=before,
        supplied_text_after_audio=(),
        arm=ARM_X2,
        content_sha256=content_hash(task_instruction, before, ()),
    )


# ---------------------------------------------------------------------------
# seeded derangements (pure)
# ---------------------------------------------------------------------------


def seeded_derangement(items: Sequence[str], seed: int) -> dict[str, str]:
    """A deterministic, fixed-point-free permutation of ``items`` (every
    item maps to a DIFFERENT item, never itself): rejection-sampling over
    ``random.Random(seed).shuffle`` until a fixed-point-free candidate is
    found. Deterministic for a given ``(items, seed)`` pair -- the SAME
    derangement every time this is called, the property both X1 (label
    derangement) and the binding-manifest builder (X2 donor-meeting
    assignment, a derangement over 4 meeting ids) need."""

    distinct = list(dict.fromkeys(items))  # de-duplicate, preserve first-seen order
    if len(distinct) < 2:
        raise PpromptError(f"seeded_derangement requires at least 2 distinct items, got {distinct}")
    rng = random.Random(seed)
    candidate = list(distinct)
    for _ in range(10_000):
        rng.shuffle(candidate)
        if all(a != b for a, b in zip(distinct, candidate)):
            return dict(zip(distinct, candidate))
    raise PpromptError(f"could not find a derangement of {distinct} for seed {seed} after 10000 attempts")  # pragma: no cover


def seeded_label_derangement(seed: int, *, labels: Sequence[str] = CANONICAL_AMI_LABELS) -> dict[str, str]:
    """X1's own derangement: a seeded fixed-point-free permutation of the
    speaker-label alphabet (module docstring)."""

    return seeded_derangement(labels, seed)


def seeded_meeting_derangement(meetings: Sequence[str], seed: int) -> dict[str, str]:
    """X2's donor-meeting assignment: a seeded fixed-point-free permutation
    over the manifest's own selected meetings, so every target meeting's
    stale tail is donated by a DIFFERENT meeting (never itself) --
    deterministic for a given ``(meetings, seed)`` pair."""

    return seeded_derangement(meetings, seed)


# ---------------------------------------------------------------------------
# request specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PpromptRequestSpec:
    request_id: str
    arm: str
    meeting_id: str
    slice_index: int
    audio_relpath: str
    audio_seconds: float
    roster: tuple[str, ...]
    prompt: PpromptPromptContent

    def to_transport_kwargs(self, *, data_dir: Path | str) -> dict[str, object]:
        return self.prompt.to_transport_kwargs(
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
            "audio_relpath": self.audio_relpath,
            "audio_seconds": self.audio_seconds,
            "roster": list(self.roster),
            "content_sha256": self.prompt.content_sha256,
        }


def _request_id(arm: str, meeting_id: str, slice_index: int) -> str:
    return f"pprompt-{arm}-{meeting_id}-slice{slice_index:04d}"


def _meetings_or_all(manifest: PattrManifest, meetings: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(meetings) if meetings is not None else manifest.selected_meetings


def _spec_from_prompt(
    manifest: PattrManifest, meeting_id: str, entry: Mapping[str, Any], roster: tuple[str, ...], prompt: PpromptPromptContent
) -> PpromptRequestSpec:
    return PpromptRequestSpec(
        request_id=_request_id(prompt.arm, meeting_id, entry["index"]),
        arm=prompt.arm,
        meeting_id=meeting_id,
        slice_index=entry["index"],
        audio_relpath=manifest.slice_audio_relpath(meeting_id, entry["filename"]),
        audio_seconds=float(entry["end"]) - float(entry["start"]),
        roster=roster,
        prompt=prompt,
    )


def build_cell_requests(manifest: PattrManifest, cell: str, *, meetings: Sequence[str] | None = None) -> tuple[PpromptRequestSpec, ...]:
    """One grid cell (e.g. ``"T2-A1"``) x 24 slices = 24 requests -- never
    the whole grid. The single-arm-at-a-time unit the flight launcher
    dispatches (module docstring)."""

    if cell not in GRID_CELLS:
        raise PpromptError(f"unknown grid cell {cell!r}; expected one of {GRID_CELLS}")
    template_id, arrangement_id = cell.split("-", 1)
    specs: list[PpromptRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        for entry in manifest.slice_entries(meeting_id):
            roster = roster_for_entry(entry)
            prompt = render_cell_prompt(template_id, arrangement_id, meeting_id, roster)
            specs.append(_spec_from_prompt(manifest, meeting_id, entry, roster, prompt))
    return tuple(specs)


def build_grid_requests(manifest: PattrManifest, *, meetings: Sequence[str] | None = None) -> tuple[PpromptRequestSpec, ...]:
    """The 12 grid cells x 24 slices = 288 requests."""

    specs: list[PpromptRequestSpec] = []
    for cell in GRID_CELLS:
        specs.extend(build_cell_requests(manifest, cell, meetings=meetings))
    return tuple(specs)


def build_x1_requests(
    manifest: PattrManifest, derangement: Mapping[str, str], *, meetings: Sequence[str] | None = None
) -> tuple[PpromptRequestSpec, ...]:
    """X1 wrong-roster x 24 slices = 24 requests."""

    specs: list[PpromptRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        for entry in manifest.slice_entries(meeting_id):
            roster = roster_for_entry(entry)
            prompt = render_x1_prompt(meeting_id, roster, derangement)
            specs.append(_spec_from_prompt(manifest, meeting_id, entry, roster, prompt))
    return tuple(specs)


def build_x2_requests(
    manifest: PattrManifest,
    tail_segments_by_meeting: Mapping[str, Sequence[Segment]],
    *,
    meetings: Sequence[str] | None = None,
) -> tuple[PpromptRequestSpec, ...]:
    """X2 stale-tail x 24 slices = 24 requests. ``tail_segments_by_meeting``
    maps a TARGET meeting id to its already-resolved donor tail (module
    docstring) -- a meeting absent from this mapping (or mapped to an empty
    sequence) renders with no tail block at all, never an error, so a test
    can exercise a subset of meetings without wiring every one."""

    specs: list[PpromptRequestSpec] = []
    for meeting_id in _meetings_or_all(manifest, meetings):
        tail = tuple(tail_segments_by_meeting.get(meeting_id, ()))
        for entry in manifest.slice_entries(meeting_id):
            roster = roster_for_entry(entry)
            prompt = render_x2_prompt(meeting_id, roster, tail)
            specs.append(_spec_from_prompt(manifest, meeting_id, entry, roster, prompt))
    return tuple(specs)


def build_arm_requests(
    manifest: PattrManifest,
    arm: str,
    *,
    derangement: Mapping[str, str] | None = None,
    tail_segments_by_meeting: Mapping[str, Sequence[Segment]] | None = None,
    meetings: Sequence[str] | None = None,
) -> tuple[PpromptRequestSpec, ...]:
    """Dispatch to the arm-specific builder by name (one of :data:`ARMS`) --
    mirrors :func:`meeting_minutes_agent.probes.pattr.build_arm_requests`'s
    own single-arm-at-a-time entry point, the shape the flight launcher
    uses. Unknown arm names raise; there is no silent fall-through."""

    if arm in GRID_CELLS:
        return build_cell_requests(manifest, arm, meetings=meetings)
    if arm == ARM_X1:
        if derangement is None:
            raise PpromptError("build_arm_requests(arm='X1', ...) requires a derangement mapping")
        return build_x1_requests(manifest, derangement, meetings=meetings)
    if arm == ARM_X2:
        return build_x2_requests(manifest, tail_segments_by_meeting or {}, meetings=meetings)
    raise PpromptError(f"unknown P-PROMPT arm {arm!r}; expected one of {ARMS}")


def build_all_requests(
    manifest: PattrManifest,
    *,
    derangement: Mapping[str, str],
    tail_segments_by_meeting: Mapping[str, Sequence[Segment]],
    meetings: Sequence[str] | None = None,
) -> tuple[PpromptRequestSpec, ...]:
    """The full 336-request sweep: the 12 grid cells, then X1, then X2, in
    that fixed order -- the same order :data:`ARMS` lists them in."""

    return (
        build_grid_requests(manifest, meetings=meetings)
        + build_x1_requests(manifest, derangement, meetings=meetings)
        + build_x2_requests(manifest, tail_segments_by_meeting, meetings=meetings)
    )


# ---------------------------------------------------------------------------
# per-arm summaries
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


def summarize_arm(arm: str, requests: Sequence[PpromptRequestSpec]) -> ArmSummary:
    return ArmSummary(
        arm=arm,
        n_requests=len(requests),
        n_meetings=len({r.meeting_id for r in requests}),
        total_audio_seconds=sum(r.audio_seconds for r in requests),
    )


def summarize_all_requests(requests: Sequence[PpromptRequestSpec]) -> dict[str, ArmSummary]:
    """One :class:`ArmSummary` per arm actually present in ``requests``, in
    :data:`ARMS` order -- the launcher's ``--summary-only`` deliverable,
    computed purely from already-built request specs, no model contact."""

    by_arm: dict[str, list[PpromptRequestSpec]] = {}
    for spec in requests:
        by_arm.setdefault(spec.arm, []).append(spec)
    return {arm: summarize_arm(arm, by_arm[arm]) for arm in ARMS if arm in by_arm}


__all__ = [
    "SCHEMA_VERSION",
    "TEMPLATES",
    "ARRANGEMENTS",
    "GRID_CELLS",
    "ARM_X1",
    "ARM_X2",
    "CORRUPT_ARMS",
    "ARMS",
    "REFERENCE_CELL",
    "CANONICAL_AMI_LABELS",
    "MEETING_CONTEXT_SECTION_HEADER",
    "REINFORCED_GRAMMAR_SECTION_HEADER",
    "REINFORCED_GRAMMAR_EXAMPLE_TEXT",
    "PpromptError",
    "roster_for_entry",
    "render_meeting_context_block",
    "render_empty_glossary_block",
    "render_reinforced_grammar_block",
    "template_extra_block",
    "PpromptPromptContent",
    "content_hash",
    "render_cell_prompt",
    "render_x1_prompt",
    "render_x2_prompt",
    "seeded_derangement",
    "seeded_label_derangement",
    "seeded_meeting_derangement",
    "PpromptRequestSpec",
    "build_cell_requests",
    "build_grid_requests",
    "build_x1_requests",
    "build_x2_requests",
    "build_arm_requests",
    "build_all_requests",
    "ArmSummary",
    "summarize_arm",
    "summarize_all_requests",
]
