#!/usr/bin/env python3
"""Build the frozen P-ATTR capability-smoke manifest from real AMI bytes.

Owner ruling (``docs/readiness/2026-08-18-g1-preregistration-draft.md`` SS0):
the P-ATTR smoke PRECEDES the G1 flight and tests, on a small bounded slice
of real audio, whether the frozen core respects a DECLARED per-slice
turn/speaker grid (the A-grid arm) versus attributing freely (A-free) or
being told the answer by construction (A-turn, one request per turn).

This script performs the ONE real-I/O step the smoke needs (mirroring
``meeting_minutes_agent.chunking.slicer``'s own "decode once, freeze BEFORE
any arm runs" discipline): it

1. seeds a deterministic selection of ``n_meetings`` AMI dev-18 meetings from
   the ES/IS/TS scenario candidate pool (``--config``'s ``candidate_pool``,
   defaulting to :data:`CANDIDATE_POOL` -- dev-18 MINUS the six IB meetings,
   which lack a full annotation stack);
2. resolves each selected meeting's gold NXT transcript
   (:mod:`meeting_minutes_agent.corpora.nxt`) and turn-aware-slices it
   (:func:`~meeting_minutes_agent.chunking.slicer.build_turn_aware_slice_plan`,
   ``allow_oracle_turns=True`` -- a declared oracle-ceiling choice, per that
   function's own gate) against the gold AMI diarization/turn layer, then
   truncates each meeting's plan to its first ``max_slices_per_meeting``
   slices -- a SMOKE, not a full-meeting flight (~25 slices total across 3-4
   meetings, per the pre-registration draft);
3. materializes both the transport-slice WAVs (one core request each, the
   A-grid/A-free arms) AND standalone per-turn clip WAVs for every turn
   covered by those slices (one core request each, the A-turn arm) -- both
   are frozen, content-hashed artifacts under ``$SPEECHRL_DATA_DIR/<slice_output_dir_relative|turn_clip_output_dir_relative>/<meeting_id>/``,
   never committed to git;
4. writes the frozen, content-hashed binding JSON (the manifest
   :mod:`meeting_minutes_agent.probes.pattr` reads) to ``--out`` --
   this file DOES go to git, under ``configs/probes/pattr/``.

Spec-ambiguity note (recorded for coordinator review, per this mission's own
final-report instruction): the mission brief describes A-turn as "audio cut
to the turn span" without specifying WHEN that cut happens. This script
resolves the ambiguity by cutting turn clips HERE, at manifest-build time,
alongside the slice WAVs -- never lazily inside a request builder -- so
every arm's audio bytes are frozen and hashed BEFORE any arm runs, exactly
matching the slicer's own established discipline
(``meeting_minutes_agent.chunking.slicer`` module docstring) and this
repository's "a head/probe is a request builder, never a byte-touching I/O
step" scope line.

Usage (WSL2, where ``$SPEECHRL_DATA_DIR`` is reachable; zero model
contact -- this is data preparation only, cutting already-licensed,
already-acquired AMI audio into smaller frozen files)::

    python scripts/build_pattr_manifest.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --config configs/probes/pattr/2026-08-18-build-config.json \\
        --out configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.adapters import (  # noqa: E402
    turn_table_from_resolved_meeting,
    turn_table_provenance,
)
from meeting_minutes_agent.chunking.constants import (  # noqa: E402
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from meeting_minutes_agent.chunking.slicer import (  # noqa: E402
    Slice,
    SlicePlan,
    build_turn_aware_slice_plan,
    detect_energy_pause_transitions,
    materialize_slice_plan,
    read_audio_duration,
)
from meeting_minutes_agent.client.receipts import hash_model_file  # noqa: E402
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting  # noqa: E402
from meeting_minutes_agent.corpora.roles import MeetingRole, load_role_registry  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402

SCHEMA_VERSION = "1.0.0"

#: dev-18 MINUS the six IB scenario meetings (mission brief: "EXCLUDE IB
#: meetings -- they lack layers; prefer ES/IS/TS scenario meetings") -- the
#: candidate pool the seeded selection draws from. All 12 carry
#: ``full_annotation_stack: true`` and role ``asr-eval`` on the committed AMI
#: role registry (configs/corpora/ami-role-registry.json).
CANDIDATE_POOL: tuple[str, ...] = (
    "ES2011a", "ES2011b", "ES2011c", "ES2011d",
    "IS1008a", "IS1008b", "IS1008c", "IS1008d",
    "TS3004a", "TS3004b", "TS3004c", "TS3004d",
)

DEFAULT_SEED = 20260818
DEFAULT_N_MEETINGS = 4
DEFAULT_MAX_SLICES_PER_MEETING = 6

DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE = "datasets/ami/annotations/manual_1.6.2"
DEFAULT_AMI_AUDIO_ROOT_RELATIVE = "datasets/ami/amicorpus"
DEFAULT_SLICE_OUTPUT_DIR_RELATIVE = "derived/meeting-minutes/pattr-smoke/slices"
DEFAULT_TURN_CLIP_OUTPUT_DIR_RELATIVE = "derived/meeting-minutes/pattr-smoke/turn-clips"


@dataclass(frozen=True)
class BuildConfig:
    seed: int = DEFAULT_SEED
    candidate_pool: tuple[str, ...] = CANDIDATE_POOL
    n_meetings: int = DEFAULT_N_MEETINGS
    max_slices_per_meeting: int = DEFAULT_MAX_SLICES_PER_MEETING
    nominal_s: float = TRANSPORT_SLICE_TARGET_S
    min_s: float = TRANSPORT_SLICE_MIN_S
    max_s: float = TRANSPORT_SLICE_MAX_S
    snap_s: float = TRANSPORT_SLICE_SNAP_S
    ami_annotations_root_relative: str = DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE
    ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE
    slice_output_dir_relative: str = DEFAULT_SLICE_OUTPUT_DIR_RELATIVE
    turn_clip_output_dir_relative: str = DEFAULT_TURN_CLIP_OUTPUT_DIR_RELATIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "candidate_pool": list(self.candidate_pool),
            "n_meetings": self.n_meetings,
            "max_slices_per_meeting": self.max_slices_per_meeting,
            "slicer": {
                "nominal_s": self.nominal_s,
                "min_s": self.min_s,
                "max_s": self.max_s,
                "snap_s": self.snap_s,
            },
            "ami_annotations_root_relative": self.ami_annotations_root_relative,
            "ami_audio_root_relative": self.ami_audio_root_relative,
            "slice_output_dir_relative": self.slice_output_dir_relative,
            "turn_clip_output_dir_relative": self.turn_clip_output_dir_relative,
        }


def load_build_config(path: Path | str | None) -> BuildConfig:
    """Load a ``BuildConfig`` from a JSON file (``--config``); every field
    is optional in the file and falls back to :class:`BuildConfig`'s own
    default when absent, so a minimal ``{}`` config is valid. ``path=None``
    returns the pure-default config."""

    if path is None:
        return BuildConfig()
    document: Mapping[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    slicer = document.get("slicer") or {}
    return BuildConfig(
        seed=int(document.get("seed", DEFAULT_SEED)),
        candidate_pool=tuple(document.get("candidate_pool", CANDIDATE_POOL)),
        n_meetings=int(document.get("n_meetings", DEFAULT_N_MEETINGS)),
        max_slices_per_meeting=int(document.get("max_slices_per_meeting", DEFAULT_MAX_SLICES_PER_MEETING)),
        nominal_s=float(slicer.get("nominal_s", TRANSPORT_SLICE_TARGET_S)),
        min_s=float(slicer.get("min_s", TRANSPORT_SLICE_MIN_S)),
        max_s=float(slicer.get("max_s", TRANSPORT_SLICE_MAX_S)),
        snap_s=float(slicer.get("snap_s", TRANSPORT_SLICE_SNAP_S)),
        ami_annotations_root_relative=str(
            document.get("ami_annotations_root_relative", DEFAULT_AMI_ANNOTATIONS_ROOT_RELATIVE)
        ),
        ami_audio_root_relative=str(document.get("ami_audio_root_relative", DEFAULT_AMI_AUDIO_ROOT_RELATIVE)),
        slice_output_dir_relative=str(
            document.get("slice_output_dir_relative", DEFAULT_SLICE_OUTPUT_DIR_RELATIVE)
        ),
        turn_clip_output_dir_relative=str(
            document.get("turn_clip_output_dir_relative", DEFAULT_TURN_CLIP_OUTPUT_DIR_RELATIVE)
        ),
    )


# ---------------------------------------------------------------------------
# pure helpers (unit-tested on synthetic fixtures -- no I/O)
# ---------------------------------------------------------------------------


def select_meetings(candidate_pool: Sequence[str], seed: int, n: int) -> tuple[str, ...]:
    """Deterministic seeded selection: ``random.Random(seed).sample(sorted
    (candidate_pool), n)``. Sorting the pool first means the result depends
    only on ``(candidate_pool as a set, seed, n)``, never on the caller's
    own iteration/insertion order. Pure -- no I/O, so this is exactly what
    "manifest determinism" means for the selection step and is unit-tested
    directly."""

    pool = sorted(set(candidate_pool))
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if n > len(pool):
        raise ValueError(f"cannot select {n} meetings from a candidate pool of {len(pool)}")
    return tuple(random.Random(seed).sample(pool, n))


def truncate_slice_plan(plan: SlicePlan, max_slices: int) -> SlicePlan:
    """The smoke's own bound: the first ``max_slices`` slices of ``plan``
    (already in chronological/index order by construction), as a fresh,
    independently content-hashed :class:`SlicePlan` -- never a full-meeting
    flight. Pure: operates only on ``plan``'s already-in-memory data, no
    audio I/O. A ``max_slices`` at or above ``len(plan.slices)`` is a
    no-op copy."""

    if max_slices <= 0:
        raise ValueError(f"max_slices must be positive, got {max_slices}")
    truncated = plan.slices[:max_slices]
    total_duration_s = truncated[-1].end if truncated else 0.0
    turn_provenance_value = plan.turn_provenance.value if plan.turn_provenance is not None else None
    payload = {
        "meeting_id": plan.meeting_id,
        "mode": plan.mode.value,
        "turn_provenance": turn_provenance_value,
        "total_duration_s": total_duration_s,
        "slices": [s.to_dict() for s in truncated],
    }
    return SlicePlan(
        meeting_id=plan.meeting_id,
        mode=plan.mode,
        turn_provenance=plan.turn_provenance,
        total_duration_s=total_duration_s,
        slices=truncated,
        content_hash=config_hash(payload),
    )


def extract_covered_turns(slices: Sequence[Slice]) -> tuple[dict[str, Any], ...]:
    """The distinct, chronologically ordered turns covered by ``slices``
    (their own per-slice ``.turns`` tables), deduplicated by
    ``(absolute_start, absolute_end, speaker)`` -- turn-aware packing never
    splits an ordinary turn across two slices (only the single
    over-long-turn exception can, an edge case this dedup handles safely
    too), so in the common case every turn appears in exactly one slice.
    Each entry carries the (lowest) slice index it was found under. Pure --
    no I/O."""

    seen: dict[tuple[float, float, str], dict[str, Any]] = {}
    for sl in slices:
        for t in sl.turns:
            key = (t.absolute_start, t.absolute_end, t.speaker)
            if key not in seen:
                seen[key] = {
                    "speaker": t.speaker,
                    "absolute_start": t.absolute_start,
                    "absolute_end": t.absolute_end,
                    "slice_index": sl.index,
                }
    ordered = sorted(seen.values(), key=lambda d: (d["absolute_start"], d["absolute_end"]))
    return tuple(ordered)


# ---------------------------------------------------------------------------
# real I/O: turn-clip materialization (the A-turn arm's own audio artifacts)
# ---------------------------------------------------------------------------


def _load_mono(source_audio_path: Path, sample_rate: int):
    """Same decode -> mono normalization path
    :func:`meeting_minutes_agent.chunking.slicer.materialize_slice_plan`
    uses internally (that helper is module-private there, so this is a
    small, deliberate, deterministic duplicate -- both call the identical
    ``librosa.load(path, sr=sample_rate, mono=True)``, so turn clips and
    slice WAVs are cut from byte-identical decoded samples)."""

    import librosa

    y, sr = librosa.load(str(source_audio_path), sr=sample_rate, mono=True)
    return y, sr


def materialize_turn_clips(
    covered_turns: Sequence[Mapping[str, Any]],
    source_audio_path: Path,
    output_dir: Path,
    *,
    meeting_id: str,
    sample_rate: int = 16000,
) -> tuple[dict[str, Any], ...]:
    """Cut and hash one standalone PCM16 WAV per covered turn -- the A-turn
    arm's own audio artifacts, frozen alongside the transport slices (never
    cut lazily by a request builder; module docstring). Deterministic: the
    same source bytes and the same ``covered_turns`` always produce
    byte-identical clip files."""

    import hashlib

    import soundfile as sf

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    samples, sr = _load_mono(source_audio_path, sample_rate)

    entries: list[dict[str, Any]] = []
    for i, turn in enumerate(covered_turns):
        start_sample = max(0, min(int(round(float(turn["absolute_start"]) * sr)), len(samples)))
        end_sample = max(start_sample, min(int(round(float(turn["absolute_end"]) * sr)), len(samples)))
        clip = samples[start_sample:end_sample]
        filename = f"{meeting_id}-turn{i:04d}.wav"
        out_path = output_dir / filename
        sf.write(str(out_path), clip, sr, subtype="PCM_16")
        digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
        entries.append(
            {
                "turn_index": i,
                "slice_index": turn["slice_index"],
                "speaker": turn["speaker"],
                "absolute_start": turn["absolute_start"],
                "absolute_end": turn["absolute_end"],
                "duration_s": (end_sample - start_sample) / float(sr),
                "filename": filename,
                "sha256": digest,
            }
        )
    return tuple(entries)


# ---------------------------------------------------------------------------
# per-meeting + top-level orchestration (real I/O: reads AMI annotation +
# audio bytes already acquired/licensed under $SPEECHRL_DATA_DIR -- data
# preparation, never a model contact)
# ---------------------------------------------------------------------------


def build_meeting_entry(
    meeting_id: str, *, data_dir: Path, corpus: NxtCorpus, cfg: BuildConfig, role: str
) -> dict[str, Any]:
    audio_relpath = f"{cfg.ami_audio_root_relative}/{meeting_id}/audio/{meeting_id}.Mix-Headset.wav"
    audio_path = data_dir / audio_relpath
    if not audio_path.is_file():
        raise FileNotFoundError(f"AMI audio not found for meeting {meeting_id!r}: {audio_path}")

    resolved = resolve_meeting(corpus, meeting_id)
    turns_all = turn_table_from_resolved_meeting(resolved)
    turn_provenance = turn_table_provenance()

    duration = read_audio_duration(audio_path)
    transitions = detect_energy_pause_transitions(audio_path)
    full_plan = build_turn_aware_slice_plan(
        meeting_id,
        turns_all,
        turn_provenance=turn_provenance,
        allow_oracle_turns=True,
        total_duration_s=duration,
        fallback_pause_transitions=transitions,
        nominal_s=cfg.nominal_s,
        min_s=cfg.min_s,
        max_s=cfg.max_s,
        snap_s=cfg.snap_s,
    )
    plan = truncate_slice_plan(full_plan, cfg.max_slices_per_meeting)

    slice_output_dir = data_dir / cfg.slice_output_dir_relative / meeting_id
    slice_manifest = materialize_slice_plan(plan, audio_path, slice_output_dir, sample_rate=16000)

    covered_turns = extract_covered_turns(plan.slices)
    turn_clip_output_dir = data_dir / cfg.turn_clip_output_dir_relative / meeting_id
    turn_clip_entries = materialize_turn_clips(
        covered_turns, audio_path, turn_clip_output_dir, meeting_id=meeting_id, sample_rate=16000
    )

    return {
        "role": role,
        "audio_relpath": audio_relpath,
        "audio_sha256": hash_model_file(audio_path),
        "meeting_duration_s": duration,
        "n_turns_total": len(turns_all),
        "slice_plan": slice_manifest.to_dict(),
        "turn_clips": [dict(e) for e in turn_clip_entries],
        "covered_duration_s": plan.total_duration_s,
        "n_slices": len(slice_manifest.entries),
        "n_turn_clips": len(turn_clip_entries),
    }


def find_oversized_slices(
    meetings: Mapping[str, Any], max_audio_seconds: float
) -> tuple[dict[str, Any], ...]:
    """Diagnostic, never a silent drop: every materialized slice whose
    duration exceeds ``max_audio_seconds`` -- the transport layer's own
    hard per-request guard
    (:data:`meeting_minutes_agent.chunking.constants.TRANSPORT_SLICE_MAX_S`,
    the default of
    :attr:`meeting_minutes_agent.client.transport.TransportConfig.max_audio_seconds_per_request`).

    Historical note (fixed, kept for provenance): this used to fire on
    every meeting's OWN first slice whenever that meeting had leading
    silence before its first gold turn (the common AMI case).
    :mod:`meeting_minutes_agent.chunking.slicer`'s turn-aware packing
    itself always respected ``max_s`` while grouping turns, but its
    SUBSEQUENT inter-turn-silence gap-tiling step used to pull the first
    slice's start all the way back to ``0.0`` (and the last slice's end
    all the way out to the meeting's full ``total_duration_s``) instead of
    stopping at the first/last turn's own edge -- tiling arbitrary
    leading/trailing non-speech straight into an edge slice and pushing it
    past ``max_s``. That gap-tiling step is now fixed at the source
    (:func:`~meeting_minutes_agent.chunking.slicer.build_turn_aware_slice_plan`
    now anchors an edge slice to its own first/last turn, pulled back/out
    by at most ``snap_s`` and room-capped so it can never itself exceed
    ``max_s``), and :mod:`meeting_minutes_agent.chunking.slicer` additionally
    now raises :class:`~meeting_minutes_agent.chunking.slicer.
    TransportBoundViolation` as a hard post-condition before a plan is ever
    returned, so an oversized slice can no longer reach this diagnostic in
    the first place. This function remains as belt-and-braces: it should
    always return an empty tuple on a real build."""

    violations: list[dict[str, Any]] = []
    for meeting_id, rec in meetings.items():
        for entry in rec["slice_plan"]["entries"]:
            duration = float(entry["end"]) - float(entry["start"])
            if duration > max_audio_seconds:
                violations.append(
                    {
                        "meeting_id": meeting_id,
                        "slice_index": entry["index"],
                        "duration_s": duration,
                        "max_audio_seconds": max_audio_seconds,
                    }
                )
    return tuple(violations)


def build_manifest(data_dir: Path, cfg: BuildConfig) -> dict[str, Any]:
    registry = load_role_registry()
    selected = select_meetings(cfg.candidate_pool, cfg.seed, cfg.n_meetings)
    for meeting_id in selected:
        # Defense in depth (this script's own candidate pool is already
        # exactly the ES/IS/TS dev-18 subset, but the registry is the
        # program's single machine-checked exposure gate -- never bypass it,
        # even when the caller believes the input is already safe).
        registry.assert_exposable(meeting_id, for_role=MeetingRole.ASR_EVAL)

    annotations_root = data_dir / cfg.ami_annotations_root_relative
    corpus = NxtCorpus(annotations_root)

    meetings: dict[str, Any] = {}
    for meeting_id in sorted(selected):
        role = registry.role_of(meeting_id).value
        meetings[meeting_id] = build_meeting_entry(meeting_id, data_dir=data_dir, corpus=corpus, cfg=cfg, role=role)

    totals = {
        "n_meetings": len(meetings),
        "n_slices": sum(m["n_slices"] for m in meetings.values()),
        "n_turn_clips": sum(m["n_turn_clips"] for m in meetings.values()),
        "slice_audio_seconds": sum(
            float(e["end"]) - float(e["start"]) for m in meetings.values() for e in m["slice_plan"]["entries"]
        ),
        "turn_clip_audio_seconds": sum(float(e["duration_s"]) for m in meetings.values() for e in m["turn_clips"]),
    }

    oversized = find_oversized_slices(meetings, TRANSPORT_SLICE_MAX_S)
    if oversized:
        print(
            f"WARNING: {len(oversized)} slice(s) exceed the transport layer's hard "
            f"max_audio_seconds_per_request ({TRANSPORT_SLICE_MAX_S}s) -- see "
            "'transport_bound_violations' in the written manifest; a pre-existing "
            "meeting_minutes_agent.chunking.slicer gap-tiling behavior on real AMI turn "
            "tables, not introduced by this script (find_oversized_slices docstring for detail). "
            "The A-grid/A-free flight arm MUST resolve this (e.g. clip/re-slice, or widen "
            "TransportConfig.max_audio_seconds_per_request for these specific requests) before "
            "sending the affected slice(s), or the transport layer will refuse them.",
            file=sys.stderr,
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "P-ATTR capability smoke (docs/readiness/2026-08-18-g1-preregistration-draft.md SS0)",
        "seed": cfg.seed,
        "candidate_pool": sorted(set(cfg.candidate_pool)),
        "selected_meetings": sorted(selected),
        "selection_rule": "random.Random(seed).sample(sorted(candidate_pool), n_meetings)",
        "n_meetings_requested": cfg.n_meetings,
        "slicer": {
            "mode": "turn_aware",
            "turn_provenance": "oracle-turn",
            "allow_oracle_turns": True,
            "nominal_s": cfg.nominal_s,
            "min_s": cfg.min_s,
            "max_s": cfg.max_s,
            "snap_s": cfg.snap_s,
            "max_slices_per_meeting": cfg.max_slices_per_meeting,
        },
        "ami_annotations_root_relative": cfg.ami_annotations_root_relative,
        "ami_audio_root_relative": cfg.ami_audio_root_relative,
        "ami_role_registry_hash": registry.registry_hash,
        "slice_output_dir_relative": cfg.slice_output_dir_relative,
        "turn_clip_output_dir_relative": cfg.turn_clip_output_dir_relative,
        "meetings": meetings,
        "totals": totals,
        "transport_bound_violations": [dict(v) for v in oversized],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument(
        "--config", default=None, help="optional build-config JSON (configs/probes/pattr/*-build-config.json)"
    )
    parser.add_argument("--out", default="configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="print totals, write nothing (still cuts audio)")
    args = parser.parse_args(argv)

    cfg = load_build_config(args.config)
    manifest = build_manifest(Path(args.data_dir), cfg)

    print(json.dumps(manifest["totals"], indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
