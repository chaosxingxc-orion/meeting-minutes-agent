"""G1 floors campaign machinery: mode rosters, PRECOMP-cache slice-plan
rebuilding, QA question resolution, resumable chunk planning, the campaign
budget guard, per-item/per-chunk receipts, and llama-server child-process
ownership.

Kept separate from :mod:`scripts.run_g1` so the CLI script itself stays
thin -- exactly ``scripts/run_precomp.py``'s own relationship to
``meeting_minutes_agent.precomp.pipeline``/``.budget``/``.receipts``/``.roster``.
This module is NOT a member of the ``precomp`` package and never imports
``meeting_minutes_agent.precomp`` -- a separate, concurrently-developed
mission owns that package's own VAD-turn-source extension; this module only
consumes already-committed, stable seams (``chunking.rttm``,
``chunking.slicer``, ``chunking.diarization.NxtOracleDiarization``,
``corpora.nxt``, ``probes.diar_smoke.require_meeting_audio_path``) to
REBUILD the deterministic slice plans PRECOMP itself already cut to disk,
never to re-run a diarization subprocess or re-decode/re-cut audio bytes.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..chunking.diarization import NxtOracleDiarization
from ..chunking.leakage import BoundaryProvenance
from ..chunking.rttm import parse_rttm_file
from ..chunking.slicer import (
    SlicePlan,
    build_turn_aware_slice_plan,
    detect_energy_pause_transitions,
    read_audio_duration,
)
from ..corpora.meetingqa.loader import MeetingQAExample, load_split
from ..corpora.nxt.corpus import NxtCorpus
from ..corpora.nxt.resolver import resolve_meeting
from ..corpora.roles import FROZEN_DEV_18, AmiRoleRegistry, QuestionUsagePolicy, load_role_registry
from ..probes.diar_smoke import DEFAULT_AMI_AUDIO_ROOT_RELATIVE, require_meeting_audio_path
from .g1 import ARMS, ARMS_WITH_MINUTES_QA

SCHEMA_VERSION = "1.0.0"

__all__ = [
    "SCHEMA_VERSION",
    "PATH_MEETINGS",
    "G1CampaignError",
    "meetings_for_mode",
    "rebuild_tool_slice_plan",
    "rebuild_oracle_slice_plan",
    "load_dev18_usable_discovery_questions",
    "WorkItem",
    "build_work_items",
    "ChunkPlanError",
    "Chunk",
    "DEFAULT_SECONDS_PER_REQUEST",
    "DEFAULT_MAX_CHUNK_WALL_SECONDS",
    "plan_chunks",
    "item_receipt_path",
    "item_already_done",
    "build_item_receipt",
    "write_item_receipt",
    "chunk_receipt_path",
    "build_chunk_receipt",
    "write_chunk_receipt",
    "CAMPAIGN_MAX_CALLS",
    "CAMPAIGN_MAX_GPU_HOURS",
    "CAMPAIGN_MAX_WALL_HOURS",
    "G1BudgetExceeded",
    "G1Budget",
    "usage_from_item_receipts",
    "ServerStartupError",
    "ManagedLlamaServer",
]


class G1CampaignError(ValueError):
    """A fail-closed refusal in this module's own planning/roster logic
    (an unknown mode, an empty roster, ...)."""


# ---------------------------------------------------------------------------
# mode rosters (floors prereg SS5 / task instruction)
# ---------------------------------------------------------------------------

#: G1-PATH's own two meetings (floors prereg SS5): "ES2011a + IS1008a, all
#: arms and heads end-to-end... structural pass/fail only... NO metric
#: conclusions."
PATH_MEETINGS: tuple[str, ...] = ("ES2011a", "IS1008a")


def meetings_for_mode(mode: str, *, dev18: Sequence[str] = FROZEN_DEV_18) -> tuple[str, ...]:
    """The registered meeting roster for ``mode`` ("path" or "floors").
    ``dev18`` defaults to the frozen split constant so a caller need not
    thread the role registry through just to resolve the roster; a caller
    that already holds a loaded :class:`~meeting_minutes_agent.corpora.roles.AmiRoleRegistry`
    may still pass its own ``dev18_roster()`` output for symmetry with
    ``precomp.roster``'s own pattern."""

    if mode == "path":
        return PATH_MEETINGS
    if mode == "floors":
        return tuple(sorted(dev18))
    raise G1CampaignError(f"unknown G1 campaign mode {mode!r}; expected 'path' or 'floors'")


# ---------------------------------------------------------------------------
# rebuild PRECOMP's tool/oracle slice plans from cached, on-disk inputs
# ---------------------------------------------------------------------------


def rebuild_tool_slice_plan(meeting_id: str, rttm_path: Path | str, audio_path: Path | str) -> SlicePlan:
    """Rebuild the SAME deterministic turn-aware :class:`SlicePlan`
    PRECOMP's own ``precomp.pipeline.run_meeting`` built for ``meeting_id``'s
    pinned-diar (tool) turn source, from the RTTM bytes PRECOMP already
    wrote to disk -- never re-running the diar subprocess. ``audio_path`` is
    read only for its duration and VAD pause-transition structure (the same
    two real, CPU-only, model-contact-free inputs PRECOMP itself fed
    :func:`~meeting_minutes_agent.chunking.slicer.build_turn_aware_slice_plan`);
    the already-cut slice-WAV bytes themselves are never touched here.
    Deterministic: given the same RTTM and the same source audio, this
    reproduces PRECOMP's own tool slice plan bit-for-bit, so
    ``Z-turn``/``Z-free`` can resolve their PRECOMP-cached slice audio by
    :func:`~meeting_minutes_agent.probes.g1.slice_filename` alone."""

    turns = parse_rttm_file(rttm_path)
    duration = read_audio_duration(Path(audio_path))
    transitions = detect_energy_pause_transitions(Path(audio_path))
    return build_turn_aware_slice_plan(
        meeting_id,
        turns,
        turn_provenance=BoundaryProvenance.TOOL_DIAR,
        allow_oracle_turns=False,
        total_duration_s=duration,
        fallback_pause_transitions=transitions,
    )


def rebuild_oracle_slice_plan(meeting_id: str, nxt_corpus: NxtCorpus, audio_path: Path | str) -> SlicePlan:
    """The oracle-turn counterpart of :func:`rebuild_tool_slice_plan`: NXT
    gold turns (never a fresh diar contact -- there is none at the oracle
    tier) through the same deterministic turn-aware packing PRECOMP used,
    with ``allow_oracle_turns=True`` (the declared ceiling-arm admission)."""

    resolved = resolve_meeting(nxt_corpus, meeting_id)
    result = NxtOracleDiarization(resolved).diarize(meeting_id)
    duration = read_audio_duration(Path(audio_path))
    transitions = detect_energy_pause_transitions(Path(audio_path))
    return build_turn_aware_slice_plan(
        meeting_id,
        result.turns,
        turn_provenance=result.provenance,
        allow_oracle_turns=True,
        total_duration_s=duration,
        fallback_pause_transitions=transitions,
    )


def rttm_path_for(derived_root: Path | str, meeting_id: str) -> Path:
    """PRECOMP's own RTTM path convention (``precomp.pipeline.rttm_dir`` in
    ``scripts/run_precomp.py``: ``<derived_root>/rttm/<meeting_id>.rttm``)."""

    return Path(derived_root) / "rttm" / f"{meeting_id}.rttm"


def meeting_audio_path(
    meeting_id: str, *, data_dir: Path | str, ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE
) -> Path:
    """The meeting's own Mix-Headset source audio -- the same resolver
    PRECOMP and every prior probe in this repository already use."""

    return require_meeting_audio_path(meeting_id, data_dir=data_dir, ami_audio_root_relative=ami_audio_root_relative)


# ---------------------------------------------------------------------------
# QA question resolution: dev-18's usable-discovery questions
# ---------------------------------------------------------------------------


def load_dev18_usable_discovery_questions(
    *,
    meetingqa_root: Path | str,
    ami_root: Path | str,
    registry: AmiRoleRegistry | None = None,
    require_audio: bool = False,
) -> tuple[MeetingQAExample, ...]:
    """Every MeetingQA train/dev-split question attached to a dev-18 meeting
    (floors prereg SS2: "the usable-discovery questions attached to
    dev-18"). Loads both the ``train`` and ``dev`` splits (usable-discovery
    is defined over their union, ``corpora.roles``'s own
    :attr:`~meeting_minutes_agent.corpora.roles.QuestionUsagePolicy.USABLE_DISCOVERY`
    docstring), filters to dev-18 meeting ids, and asserts -- fail-closed,
    defense in depth -- that every returned question's meeting really does
    carry the ``usable-discovery`` policy on the committed role registry (it
    always should, by construction: dev-18 is disjoint from eval-16 and
    every dev-18 meeting's own MeetingQA split, where present, is
    train/dev). ``require_audio=False`` by default: this function resolves
    QUESTIONS, not audio bytes -- G1's own audio anchor is a PRECOMP-cached
    slice (``probes/g1.py``'s module docstring), never the MeetingQA
    loader's own per-example ``audio_path``."""

    reg = registry if registry is not None else load_role_registry()
    dev18 = set(FROZEN_DEV_18)
    out: list[MeetingQAExample] = []
    for split in ("train", "dev"):
        for example in load_split(
            meetingqa_root=meetingqa_root, ami_root=ami_root, split=split, require_audio=require_audio
        ):
            if example.meeting_id not in dev18:
                continue
            if reg.question_usage_policy_of(example.meeting_id) is not QuestionUsagePolicy.USABLE_DISCOVERY:
                raise G1CampaignError(
                    f"MeetingQA example {example.example_id!r} on dev-18 meeting "
                    f"{example.meeting_id!r} does not carry the usable-discovery policy on the "
                    "committed role registry -- refusing to treat it as a discovery surface"
                )
            out.append(example)
    return tuple(out)


# ---------------------------------------------------------------------------
# resumable work items + chunk planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkItem:
    """One resumable unit of G1 campaign work: one (meeting, arm) pair's
    full workload -- every transcribe-span call for that arm's slice plan,
    plus (Z-turn/Z-oracle only) one minutes call and the capped QA calls.
    ``n_calls``/``estimated_wall_seconds`` are PLANNING-time estimates
    (throughput basis, floors prereg SS6); the campaign runner's own
    per-item receipt records what actually happened."""

    meeting_id: str
    arm: str
    n_transcribe: int
    n_minutes: int = 0
    n_qa: int = 0

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise G1CampaignError(f"unknown G1 arm {self.arm!r}; expected one of {ARMS}")
        if self.n_transcribe < 0 or self.n_minutes < 0 or self.n_qa < 0:
            raise G1CampaignError(f"WorkItem call counts must be non-negative: {self!r}")
        if (self.n_minutes or self.n_qa) and self.arm not in ARMS_WITH_MINUTES_QA:
            raise G1CampaignError(f"{self.arm} carries no minutes/qa head but n_minutes/n_qa is non-zero: {self!r}")

    @property
    def n_calls(self) -> int:
        return self.n_transcribe + self.n_minutes + self.n_qa

    @property
    def item_id(self) -> str:
        return f"{self.meeting_id}:{self.arm}"

    def estimated_wall_seconds(self, *, seconds_per_request: float) -> float:
        return self.n_calls * seconds_per_request

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "arm": self.arm,
            "n_transcribe": self.n_transcribe,
            "n_minutes": self.n_minutes,
            "n_qa": self.n_qa,
            "n_calls": self.n_calls,
        }


def build_work_items(
    meetings: Sequence[str],
    *,
    n_transcribe_by_meeting_arm: Mapping[tuple[str, str], int],
    n_qa_per_meeting: int = 0,
    n_qa_by_meeting: Mapping[str, int] | None = None,
    arms: Sequence[str] = ARMS,
) -> tuple[WorkItem, ...]:
    """Build the campaign's ordered :class:`WorkItem` list: for every
    meeting, in the given order, one item per arm, in :data:`~.g1.ARMS`
    order -- deterministic by construction (a plain nested ``for`` loop,
    never a set or other unordered structure, mirroring
    ``harness/episode.py``'s own stated discipline). ``n_transcribe_by_meeting_arm``
    is the caller's own real slice-count lookup (built from a rebuilt/loaded
    :class:`~meeting_minutes_agent.chunking.slicer.SlicePlan` per
    meeting/arm -- this function performs no I/O of its own); a missing
    ``(meeting_id, arm)`` key raises rather than silently planning zero
    calls for it.

    QA call counts are PER MEETING, never a single campaign-wide scalar
    applied uniformly (the G1-PATH structural NOT-PASS this signature
    repairs: dispatching every capped question to every meeting planned
    ``n_meetings x N x 2`` QA calls instead of ``N x 2``). Pass
    ``n_qa_by_meeting`` -- a ``meeting_id -> count`` mapping, e.g. built from
    :func:`~meeting_minutes_agent.probes.g1.questions_for_meeting` over the
    same capped set :func:`~meeting_minutes_agent.probes.g1.build_qa_requests_for_meeting`
    will later route per meeting -- for the real campaign; a meeting absent
    from the mapping plans zero QA calls (e.g. ``IS1008a``, which the
    registered cap draws zero questions for), never an error.
    ``n_qa_per_meeting`` is kept as the prior uniform-scalar shorthand (still
    applied to every meeting alike) for callers -- tests, mainly -- that
    have no need of per-meeting variation; it is ignored once
    ``n_qa_by_meeting`` is given."""

    items: list[WorkItem] = []
    for meeting_id in meetings:
        for arm in arms:
            key = (meeting_id, arm)
            if key not in n_transcribe_by_meeting_arm:
                raise G1CampaignError(f"build_work_items: no transcribe-slice count supplied for {key!r}")
            n_transcribe = n_transcribe_by_meeting_arm[key]
            has_minutes_qa = arm in ARMS_WITH_MINUTES_QA
            n_qa = (n_qa_by_meeting.get(meeting_id, 0) if n_qa_by_meeting is not None else n_qa_per_meeting)
            items.append(
                WorkItem(
                    meeting_id=meeting_id,
                    arm=arm,
                    n_transcribe=n_transcribe,
                    n_minutes=1 if has_minutes_qa else 0,
                    n_qa=n_qa if has_minutes_qa else 0,
                )
            )
    return tuple(items)


class ChunkPlanError(ValueError):
    """A single :class:`WorkItem`'s own estimated wall time exceeds the
    chunk cap -- a fail-closed refusal (mirrors
    ``chunking.slicer.TransportBoundViolation``'s own discipline): this
    planner never silently ships an oversized chunk the 60-minute
    harness-reap rule would then kill mid-flight."""


#: P-PROMPT measured (floors prereg SS6: "Throughput basis: 3.7 s/request").
DEFAULT_SECONDS_PER_REQUEST = 3.7
#: The registered <=50-minute chunk cap (floors prereg discipline SS7 /
#: task instruction), leaving margin under the 60-minute harness-reap window.
DEFAULT_MAX_CHUNK_WALL_SECONDS = 50 * 60.0


@dataclass(frozen=True)
class Chunk:
    index: int
    items: tuple[WorkItem, ...]

    def estimated_wall_seconds(self, *, seconds_per_request: float = DEFAULT_SECONDS_PER_REQUEST) -> float:
        return sum(item.estimated_wall_seconds(seconds_per_request=seconds_per_request) for item in self.items)

    def to_dict(self, *, seconds_per_request: float = DEFAULT_SECONDS_PER_REQUEST) -> dict[str, Any]:
        return {
            "index": self.index,
            "items": [item.to_dict() for item in self.items],
            "estimated_wall_seconds": self.estimated_wall_seconds(seconds_per_request=seconds_per_request),
        }


def plan_chunks(
    work_items: Sequence[WorkItem],
    *,
    max_chunk_wall_seconds: float = DEFAULT_MAX_CHUNK_WALL_SECONDS,
    seconds_per_request: float = DEFAULT_SECONDS_PER_REQUEST,
) -> tuple[Chunk, ...]:
    """Greedy, ORDER-PRESERVING bin-packing of ``work_items`` into chunks
    whose estimated wall time never exceeds ``max_chunk_wall_seconds``.
    Never reorders items -- determinism by construction. A single item whose
    OWN estimate exceeds the cap raises :class:`ChunkPlanError` rather than
    shipping an oversized chunk (one meeting's one arm workload is at most a
    few dozen calls in this campaign, but the guard is unconditional, not a
    documented assumption)."""

    if max_chunk_wall_seconds <= 0:
        raise ChunkPlanError(f"max_chunk_wall_seconds must be positive, got {max_chunk_wall_seconds!r}")
    if seconds_per_request <= 0:
        raise ChunkPlanError(f"seconds_per_request must be positive, got {seconds_per_request!r}")

    chunks: list[Chunk] = []
    current: list[WorkItem] = []
    current_wall = 0.0
    for item in work_items:
        item_wall = item.estimated_wall_seconds(seconds_per_request=seconds_per_request)
        if item_wall > max_chunk_wall_seconds:
            raise ChunkPlanError(
                f"work item {item.item_id!r} alone is estimated at {item_wall:.1f}s, exceeding the "
                f"{max_chunk_wall_seconds:.1f}s chunk cap -- refusing to plan an oversized chunk"
            )
        if current and current_wall + item_wall > max_chunk_wall_seconds:
            chunks.append(Chunk(index=len(chunks), items=tuple(current)))
            current = []
            current_wall = 0.0
        current.append(item)
        current_wall += item_wall
    if current:
        chunks.append(Chunk(index=len(chunks), items=tuple(current)))
    return tuple(chunks)


# ---------------------------------------------------------------------------
# per-item / per-chunk receipts (fsynced, resume-checked)
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fsync_write_json(path: Path | str, payload: Mapping[str, Any]) -> Path:
    """Write ``payload`` as pretty JSON, fsynced before returning -- the
    same discipline every other receipt writer in this repository uses
    (``precomp.receipts.fsync_write_json``, reimplemented here rather than
    imported so this module never depends on ``precomp``)."""

    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return resolved


def item_receipt_path(out_dir: Path | str, meeting_id: str, arm: str) -> Path:
    return Path(out_dir) / "receipts" / f"{meeting_id}-{arm}-receipt.json"


def item_already_done(out_dir: Path | str, meeting_id: str, arm: str) -> bool:
    """Resume support at (meeting, arm) granularity (task instruction:
    "resumable chunks (meeting x arm granularity)"). A receipt is
    complete+verified when it parses as JSON, declares THIS module's
    :data:`SCHEMA_VERSION`, and records ``ok: true`` -- mirrors
    ``precomp.receipts.already_done`` exactly."""

    path = item_receipt_path(out_dir, meeting_id, arm)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    return data.get("schema_version") == SCHEMA_VERSION and bool(data.get("ok"))


def build_item_receipt(
    *,
    meeting_id: str,
    arm: str,
    ok: bool,
    error: str | None,
    n_calls: int,
    gpu_seconds: float,
    wall_seconds: float,
    contacts: Sequence[Mapping[str, Any]],
    recorded_utc: str | None = None,
) -> dict[str, Any]:
    """One (meeting, arm) work item's receipt: schema-versioned, carrying
    this item's OWN spend deltas (never a cumulative campaign snapshot --
    :func:`usage_from_item_receipts` re-derives the cumulative view by
    summing these, exactly the ``precomp.budget.wave_usage_from_receipts``
    pattern) plus its per-contact log."""

    return {
        "schema_version": SCHEMA_VERSION,
        "meeting_id": meeting_id,
        "arm": arm,
        "ok": ok,
        "error": error,
        "n_calls": n_calls,
        "gpu_seconds": gpu_seconds,
        "wall_seconds": wall_seconds,
        "contacts": [dict(c) for c in contacts],
        "recorded_utc": recorded_utc or _iso_now(),
    }


def write_item_receipt(out_dir: Path | str, receipt: Mapping[str, Any]) -> Path:
    return fsync_write_json(item_receipt_path(out_dir, str(receipt["meeting_id"]), str(receipt["arm"])), receipt)


def chunk_receipt_path(out_dir: Path | str, chunk_index: int) -> Path:
    return Path(out_dir) / "chunks" / f"chunk{chunk_index:04d}-receipt.json"


def build_chunk_receipt(
    *,
    chunk_index: int,
    item_outcomes: Sequence[Mapping[str, Any]],
    budget_after: Mapping[str, Any],
    stopped_reason: str | None,
    recorded_utc: str | None = None,
) -> dict[str, Any]:
    """One chunk invocation's summary receipt -- mirrors
    ``precomp.receipts.build_wave_summary``'s own shape, one level down (one
    chunk, not the whole campaign)."""

    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_index": chunk_index,
        "n_items": len(item_outcomes),
        "n_ok": sum(1 for o in item_outcomes if o.get("ok")),
        "n_error": sum(1 for o in item_outcomes if not o.get("ok")),
        "budget_after": dict(budget_after),
        "stopped_reason": stopped_reason,
        "item_outcomes": [dict(o) for o in item_outcomes],
        "recorded_utc": recorded_utc or _iso_now(),
    }


def write_chunk_receipt(out_dir: Path | str, chunk_index: int, receipt: Mapping[str, Any]) -> Path:
    return fsync_write_json(chunk_receipt_path(out_dir, chunk_index), receipt)


def load_item_receipts(out_dir: Path | str) -> list[dict[str, Any]]:
    """Every per-item receipt already on disk under ``out_dir/receipts/``,
    parsed as JSON -- the campaign's own budget-precharge input (module
    docstring's ``usage_from_item_receipts``), mirroring
    ``scripts/run_precomp.py::load_wave_receipts``."""

    receipts_dir = Path(out_dir) / "receipts"
    if not receipts_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("*-receipt.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


# ---------------------------------------------------------------------------
# campaign budget (call-count / GPU-hour / wall-hour ceilings)
# ---------------------------------------------------------------------------

#: Registered campaign ceilings (floors prereg SS6, verbatim).
CAMPAIGN_MAX_CALLS = 2_900
CAMPAIGN_MAX_GPU_HOURS = 6.0
CAMPAIGN_MAX_WALL_HOURS = 8.0


class G1BudgetExceeded(RuntimeError):
    """Fail-closed refusal: a campaign-level ceiling (call count, GPU-hours,
    or wall-hours) would already be reached before the next work item
    starts. Checked BEFORE every item; raised, never returned as a boolean a
    caller could ignore -- mirrors ``precomp.budget.PrecompBudgetExceeded``."""


def usage_from_item_receipts(receipts: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Re-derive campaign-cumulative usage from a list of already-parsed
    per-item receipt dicts (any shape :func:`build_item_receipt` produces),
    by summing each receipt's OWN delta fields -- never reading a nested
    cumulative snapshot (mirrors ``precomp.budget.wave_usage_from_receipts``
    exactly). A non-mapping entry is skipped rather than raising."""

    used = {"calls_used": 0, "gpu_seconds_used": 0.0, "wall_seconds_used": 0.0}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        used["calls_used"] += int(receipt.get("n_calls") or 0)
        used["gpu_seconds_used"] += float(receipt.get("gpu_seconds") or 0.0)
        used["wall_seconds_used"] += float(receipt.get("wall_seconds") or 0.0)
    return used


@dataclass
class G1Budget:
    """Cumulative campaign usage, checked before every work item against
    the registered ceilings (module constants above). One instance is
    shared across every item a chunk invocation processes; :meth:`precharge`
    folds in usage already spent by receipts from EARLIER chunk invocations,
    so a fresh process (one per chunk, module docstring's server-ownership
    design) never silently resets the campaign-level ceilings."""

    max_calls: int = CAMPAIGN_MAX_CALLS
    max_gpu_hours: float = CAMPAIGN_MAX_GPU_HOURS
    max_wall_hours: float = CAMPAIGN_MAX_WALL_HOURS
    calls_used: int = 0
    gpu_seconds_used: float = 0.0
    wall_seconds_used: float = 0.0

    def check_before_item(self, item: WorkItem, *, seconds_per_request: float = DEFAULT_SECONDS_PER_REQUEST) -> None:
        projected_calls = self.calls_used + item.n_calls
        if projected_calls > self.max_calls:
            raise G1BudgetExceeded(
                f"campaign call ceiling would be exceeded by {item.item_id!r}: "
                f"{self.calls_used} used + {item.n_calls} > {self.max_calls}"
            )
        max_wall_seconds = self.max_wall_hours * 3600.0
        projected_wall = self.wall_seconds_used + item.estimated_wall_seconds(seconds_per_request=seconds_per_request)
        if projected_wall > max_wall_seconds:
            raise G1BudgetExceeded(
                f"campaign wall-hour ceiling would be exceeded by {item.item_id!r}: "
                f"{self.wall_seconds_used:.1f}s used + {item.estimated_wall_seconds(seconds_per_request=seconds_per_request):.1f}s "
                f"estimate > {max_wall_seconds:.1f}s allowed"
            )
        max_gpu_seconds = self.max_gpu_hours * 3600.0
        if self.gpu_seconds_used >= max_gpu_seconds:
            raise G1BudgetExceeded(
                f"campaign GPU-hour ceiling already reached: {self.gpu_seconds_used:.1f}s used of "
                f"{max_gpu_seconds:.1f}s allowed -- refusing to start {item.item_id!r}"
            )

    def record(self, *, n_calls: int, gpu_seconds: float, wall_seconds: float) -> None:
        self.calls_used += max(0, n_calls)
        self.gpu_seconds_used += max(0.0, gpu_seconds)
        self.wall_seconds_used += max(0.0, wall_seconds)

    def precharge(self, receipts: Iterable[Mapping[str, Any]]) -> None:
        """Fold campaign-cumulative usage already spent by ``receipts``
        (:func:`usage_from_item_receipts`) into this budget's own counters --
        additive only, never destructive. Call once, right after
        construction, before the first item of a chunk invocation runs
        (mirrors ``precomp.budget.PrecompBudget.precharge``)."""

        used = usage_from_item_receipts(receipts)
        self.calls_used += int(used["calls_used"])
        self.gpu_seconds_used += used["gpu_seconds_used"]
        self.wall_seconds_used += used["wall_seconds_used"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ceilings": {
                "max_calls": self.max_calls,
                "max_gpu_hours": self.max_gpu_hours,
                "max_wall_hours": self.max_wall_hours,
            },
            "calls_used": self.calls_used,
            "gpu_seconds_used": self.gpu_seconds_used,
            "wall_seconds_used": self.wall_seconds_used,
        }


# ---------------------------------------------------------------------------
# llama-server child-process ownership (the 60-minute harness-reap rule)
# ---------------------------------------------------------------------------

DEFAULT_HEALTH_TIMEOUT_SECONDS = 120.0
DEFAULT_HEALTH_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0


class ServerStartupError(RuntimeError):
    """The managed llama-server subprocess exited, or never reported
    healthy, before ``health_timeout_seconds`` elapsed."""


def _default_health_check(base_url: str) -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


class ManagedLlamaServer:
    """Owns a llama-server subprocess as a CHILD of the calling process for
    exactly the lifetime of one chunk invocation (task instruction: "the
    llama-server owned as a CHILD of the chunk script -- 60-minute
    harness-reap rule"; lesson recorded in
    ``docs/checks/2026-08-19-precomp-wave1/README.md``'s resume-pass
    section: a server started as a SEPARATE background job outlived, and was
    torn down independently of, the work depending on it, producing a
    mid-encode connection reset on ``TS3004d``). A chunk script that
    launches its server through THIS class instead starts it as a direct
    ``subprocess.Popen`` child of the SAME process the harness's 60-minute
    background-job reap applies to: if the harness reaps the whole chunk
    invocation, the child server dies with it (no independently-surviving,
    independently-killed dependency); and on the chunk's own normal exit
    (success OR a caught per-item failure) :meth:`shutdown` (also called by
    ``__exit__``) always tears the server down cleanly before the process
    returns control -- one process, one server, one lifetime.

    ``popen``/``health_check``/``sleep`` are injection seams (mirrors this
    repository's other subprocess seams: ``chunking.diarization``'s
    ``run_subprocess``, ``probes.diar_smoke``'s ``run``): tests supply
    fakes, so this class is fully exercisable without a real llama-server
    binary, matching the repository's zero-model-contact test discipline.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        base_url: str,
        popen: Callable[..., "subprocess.Popen[bytes]"] | None = None,
        health_check: Callable[[str], bool] | None = None,
        health_timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
        health_poll_interval_seconds: float = DEFAULT_HEALTH_POLL_INTERVAL_SECONDS,
        shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._command = list(command)
        self.base_url = base_url
        self._popen = popen or subprocess.Popen
        self._health_check = health_check or _default_health_check
        self._health_timeout_seconds = health_timeout_seconds
        self._health_poll_interval_seconds = health_poll_interval_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._sleep = sleep or time.sleep
        self._process: "subprocess.Popen[bytes] | None" = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("ManagedLlamaServer.start called twice on the same instance")
        self._process = self._popen(self._command)
        deadline = time.monotonic() + self._health_timeout_seconds
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise ServerStartupError(
                    f"llama-server child process exited with code {self._process.returncode} "
                    "before becoming healthy"
                )
            if self._health_check(self.base_url):
                return
            self._sleep(self._health_poll_interval_seconds)
        self.shutdown()
        raise ServerStartupError(
            f"llama-server at {self.base_url!r} did not become healthy within {self._health_timeout_seconds}s"
        )

    def shutdown(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=self._shutdown_timeout_seconds)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=self._shutdown_timeout_seconds)
        self._process = None

    def __enter__(self) -> "ManagedLlamaServer":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown()
