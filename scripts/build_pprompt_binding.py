#!/usr/bin/env python3
"""Build the frozen P-PROMPT binding manifest.

Registration this script implements exactly:
``docs/readiness/2026-08-18-pprompt-preregistration.md`` (the grid/metric/
winner-rule design) and ``docs/readiness/2026-08-18-g1-preregistration-
draft.md`` SS0b (the deployment-baseline context block this sweep's T2
template renders).

This is the ONE place in the P-PROMPT machinery that touches real bytes
beyond what :mod:`meeting_minutes_agent.probes.pprompt`'s pure functions
need (mirrors ``scripts/build_pattr_manifest.py``'s own "freeze BEFORE any
arm runs" discipline): it

1. loads the frozen P-ATTR 24-slice manifest by PATH + verifies its own
   sha256 -- this sweep reuses that manifest VERBATIM (never rebuilds it;
   the P-PROMPT preregistration's own instruction) and records the
   reference (path + sha256) other tooling can re-verify against;
2. derives the seeded label derangement (X1) and the seeded donor-meeting
   derangement (X2) from :mod:`meeting_minutes_agent.probes.pprompt`'s pure
   helpers;
3. reads the P-ATTR smoke's archived A-turn reply JSONL (already-flown,
   MODEL-GENERATED text -- never gold; ``$SPEECHRL_DATA_DIR/derived/
   meeting-minutes/pattr-smoke/runs/2026-08-18-pattr-smoke/
   a-turn-responses.jsonl``, per ``docs/checks/2026-08-18-pattr-smoke-
   flight/README.md``'s own handoff note) to select each target meeting's
   donor tail (its assigned donor meeting's last 10 flown turns) and hashes
   the donor text -- the binding manifest pins the HASH, never the raw
   text, so no model-generated trace bytes enter git (this repository's own
   "never commit... raw traces" line; the launcher re-reads and re-verifies
   this same JSONL fresh at flight time, ``scripts/launch_pprompt_sweep.py::
   load_x2_tail_segments``);
4. renders EVERY one of the 336 requests' prompt content once (the same
   pure functions the flight launcher will call later) and pins each
   rendering's sha256, so a rendering built at flight time either matches
   this file byte-for-byte (via the hash) or the flight refuses;
5. writes the frozen, content-hashed binding JSON to ``--out`` -- this file
   DOES go to git, under ``configs/probes/pprompt/``.

Usage (WSL2, where ``$SPEECHRL_DATA_DIR`` is reachable; zero model contact
-- this reads already-licensed AMI annotation metadata (through the P-ATTR
manifest, already materialized) and an already-flown reply JSONL, and
writes small hashes/text; it never decodes or writes audio)::

    python scripts/build_pprompt_binding.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --pattr-manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --out configs/probes/pprompt/2026-08-18-pprompt-binding.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.models import Segment  # noqa: E402
from meeting_minutes_agent.client.receipts import hash_model_file  # noqa: E402
from meeting_minutes_agent.heads.transcribe_attribute import SYSTEM_INSTRUCTION_TEMPLATE  # noqa: E402
from meeting_minutes_agent.probes.pattr import PattrManifest, load_pattr_manifest  # noqa: E402
from meeting_minutes_agent.probes.pprompt import (  # noqa: E402
    ARM_X1,
    ARM_X2,
    ARRANGEMENTS,
    CANONICAL_AMI_LABELS,
    GRID_CELLS,
    TEMPLATES,
    content_hash,
    render_cell_prompt,
    render_empty_glossary_block,
    render_meeting_context_block,
    render_reinforced_grammar_block,
    render_x1_prompt,
    render_x2_prompt,
    roster_for_entry,
    seeded_label_derangement,
    seeded_meeting_derangement,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402

SCHEMA_VERSION = "1.0.0"
DEFAULT_SEED = 20260818
DEFAULT_TAIL_SIZE = 10
DEFAULT_DONOR_SOURCE_RELATIVE = (
    "derived/meeting-minutes/pattr-smoke/runs/2026-08-18-pattr-smoke/a-turn-responses.jsonl"
)

# X1's own recorded resolution rationale (module docstring, mission brief
# item 2): the fallback branch, because the roster turned out to be
# meeting-invariant on the frozen P-ATTR manifest's four meetings.
X1_RESOLUTION_NOTE = (
    "AMI/NXT turn labels are meeting-invariant bare letters (confirmed before this manifest was "
    "built: every one of the four P-ATTR-smoke meetings' turn tables uses exactly the alphabet "
    "{CANONICAL_AMI_LABELS}), so swapping in a DIFFERENT meeting's roster would be a byte-for-byte "
    "no-op text change. Per the mission's own fallback instruction, X1 instead corrupts the "
    "turn-to-speaker-label mapping inside the slice metadata: a seeded fixed-point-free derangement "
    "of the label alphabet is applied to every slice's OWN roster (read off entry['turns']) before "
    "it is rendered into the context block, so the declared 'speakers in this excerpt' set is "
    "actually wrong relative to the audio -- a real corruption of the attribution channel."
).format(CANONICAL_AMI_LABELS=list(CANONICAL_AMI_LABELS))


# ---------------------------------------------------------------------------
# pure-ish helpers (isolated for unit testing on a synthetic manifest)
# ---------------------------------------------------------------------------


def per_slice_roster_table(manifest: PattrManifest) -> dict[str, dict[int, tuple[str, ...]]]:
    """``{meeting_id: {slice_index: roster}}`` read straight off the frozen
    P-ATTR manifest's own per-slice turn tables."""

    return {
        meeting_id: {entry["index"]: roster_for_entry(entry) for entry in manifest.slice_entries(meeting_id)}
        for meeting_id in manifest.selected_meetings
    }


def build_x1_block(manifest: PattrManifest, seed: int) -> dict[str, Any]:
    roster_table = per_slice_roster_table(manifest)
    alphabet = sorted({label for slices in roster_table.values() for roster in slices.values() for label in roster})
    derangement = seeded_label_derangement(seed, labels=alphabet)
    per_slice = {
        meeting_id: {
            str(slice_index): {
                "true_roster": list(roster),
                "corrupted_roster": sorted({derangement[label] for label in roster}),
            }
            for slice_index, roster in slices.items()
        }
        for meeting_id, slices in roster_table.items()
    }
    return {
        "resolution": "label-derangement-within-slice",
        "reason": X1_RESOLUTION_NOTE,
        "seed": seed,
        "label_alphabet": alphabet,
        "label_derangement": derangement,
        "per_slice_roster": per_slice,
    }


def select_donor_tail_entries(
    donor_meeting_id: str, a_turn_records: Sequence[Mapping[str, Any]], *, tail_size: int
) -> list[dict[str, Any]]:
    """The donor meeting's own last ``tail_size`` FLOWN (``outcome == "ok"``)
    A-turn replies, ordered by ``turn_index`` -- the "previous slice's last
    ~8-12 utterances" rolling-tail convention (SS0b(3)) applied to a
    DIFFERENT meeting's already-flown turns, per X2's own definition."""

    donor_records = [
        r for r in a_turn_records if r.get("meeting_id") == donor_meeting_id and r.get("outcome") == "ok"
    ]
    donor_records.sort(key=lambda r: r["turn_index"])
    selected = donor_records[-tail_size:] if tail_size > 0 else []
    entries: list[dict[str, Any]] = []
    for record in selected:
        text = record["text"]
        entries.append(
            {
                "donor_meeting_id": donor_meeting_id,
                "donor_request_id": record["request_id"],
                "donor_turn_index": record["turn_index"],
                "donor_slice_index": record.get("slice_index"),
                "speaker": record["known_speaker"],
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_length_chars": len(text),
            }
        )
    return entries


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def build_x2_block(
    manifest: PattrManifest, data_dir: Path, *, seed: int, tail_size: int, donor_source_relative: str
) -> tuple[dict[str, Any], dict[str, tuple[Segment, ...]]]:
    """Returns ``(binding_block, tail_segments_by_meeting)`` -- the second
    element is used ONLY in-process, to render (and hash) the actual X2
    prompts below; it is never written to the binding manifest (raw
    model-generated text stays out of git, module docstring)."""

    donor_source_path = Path(data_dir) / donor_source_relative
    if not donor_source_path.is_file():
        raise FileNotFoundError(
            f"X2 donor source not found: {donor_source_path} -- see docs/checks/"
            "2026-08-18-pattr-smoke-flight/README.md's handoff note for where this JSONL lives"
        )
    a_turn_records = load_jsonl(donor_source_path)

    donor_assignment = seeded_meeting_derangement(list(manifest.selected_meetings), seed)

    tail_entries: dict[str, list[dict[str, Any]]] = {}
    tail_segments_by_meeting: dict[str, tuple[Segment, ...]] = {}
    for target_meeting, donor_meeting in donor_assignment.items():
        entries = select_donor_tail_entries(donor_meeting, a_turn_records, tail_size=tail_size)
        if len(entries) < tail_size:
            raise RuntimeError(
                f"donor meeting {donor_meeting!r} (assigned to target {target_meeting!r}) only carries "
                f"{len(entries)} flown A-turn replies, fewer than the requested tail_size={tail_size}"
            )
        tail_entries[target_meeting] = entries
        by_request_id = {r["request_id"]: r for r in a_turn_records}
        tail_segments_by_meeting[target_meeting] = tuple(
            Segment(id=e["donor_request_id"], speaker=e["speaker"], start=0.0, end=0.0, text=by_request_id[e["donor_request_id"]]["text"])
            for e in entries
        )

    block = {
        "resolution": "cross-meeting-donor-tail",
        "donor_source_relpath": donor_source_relative,
        "seed": seed,
        "tail_size": tail_size,
        "donor_meeting_assignment": donor_assignment,
        "tail_entries": tail_entries,
    }
    return block, tail_segments_by_meeting


def build_renderings(
    manifest: PattrManifest, x1_derangement: Mapping[str, str], tail_segments_by_meeting: Mapping[str, tuple[Segment, ...]]
) -> dict[str, list[dict[str, Any]]]:
    """Every one of the 336 requests' rendered-content sha256, keyed by arm.
    Recomputed at flight time by the exact same pure functions -- a mismatch
    there means the manifest and the code have drifted."""

    renderings: dict[str, list[dict[str, Any]]] = {}
    for meeting_id in manifest.selected_meetings:
        for entry in manifest.slice_entries(meeting_id):
            roster = roster_for_entry(entry)
            for template_id in TEMPLATES:
                for arrangement_id in ARRANGEMENTS:
                    prompt = render_cell_prompt(template_id, arrangement_id, meeting_id, roster)
                    renderings.setdefault(prompt.arm, []).append(
                        {"meeting_id": meeting_id, "slice_index": entry["index"], "content_sha256": prompt.content_sha256}
                    )
            x1_prompt = render_x1_prompt(meeting_id, roster, x1_derangement)
            renderings.setdefault(ARM_X1, []).append(
                {"meeting_id": meeting_id, "slice_index": entry["index"], "content_sha256": x1_prompt.content_sha256}
            )
            tail = tail_segments_by_meeting.get(meeting_id, ())
            x2_prompt = render_x2_prompt(meeting_id, roster, tail)
            renderings.setdefault(ARM_X2, []).append(
                {"meeting_id": meeting_id, "slice_index": entry["index"], "content_sha256": x2_prompt.content_sha256}
            )
    return renderings


def build_templates_block() -> dict[str, Any]:
    empty_glossary = render_empty_glossary_block()
    reinforced_grammar = render_reinforced_grammar_block()
    return {
        "T1": {
            "description": "bare transcribe-and-attribute instruction + output-grammar contract (control)",
            "task_instruction": SYSTEM_INSTRUCTION_TEMPLATE,
            "task_instruction_sha256": config_hash({"text": SYSTEM_INSTRUCTION_TEMPLATE}),
            "extra_block_kind": None,
        },
        "T2": {
            "description": "T1 + the SS0b deployment context block (meeting id, per-slice speaker roster read "
            "from the frozen manifest's own turn metadata, task framing)",
            "extra_block_kind": "meeting_context",
            "extra_block_rule": "render_meeting_context_block(meeting_id, roster) -- varies per meeting/slice, "
            "see per_meeting_context below",
        },
        "T3": {
            "description": "T2 + an explicitly EMPTY glossary slot (measures the slot's framing cost before any "
            "glossary supply exists)",
            "extra_block_kind": "meeting_context+empty_glossary",
            "empty_glossary_block": empty_glossary,
            "empty_glossary_block_sha256": config_hash({"text": empty_glossary}),
        },
        "T4": {
            "description": "T2 + reinforced output-grammar section restating the grammar with a per-line format "
            "example",
            "extra_block_kind": "meeting_context+reinforced_grammar",
            "reinforced_grammar_block": reinforced_grammar,
            "reinforced_grammar_block_sha256": config_hash({"text": reinforced_grammar}),
        },
    }


def build_arrangements_block() -> dict[str, Any]:
    return {
        "A1": {
            "description": "context in system turn, audio in user turn",
            "rule": "the template's extra block is appended to the SYSTEM message (task_instruction)",
        },
        "A2": {
            "description": "context in the user turn BEFORE the audio",
            "rule": "the template's extra block is a USER-message text part placed before the audio part",
        },
        "A3": {
            "description": "context in the user turn AFTER the audio",
            "rule": "the template's extra block is a USER-message text part placed after the audio part",
        },
        "note": (
            "T1 has no extra block, so all three of its arrangement cells render an IDENTICAL request -- "
            "a documented, harmless consequence of honoring the registered 4x3 grid literally, visible "
            "in 'renderings' below as three identical content_sha256 values per T1 slice."
        ),
    }


def build_per_meeting_context(manifest: PattrManifest) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for meeting_id in manifest.selected_meetings:
        out[meeting_id] = {}
        for entry in manifest.slice_entries(meeting_id):
            roster = roster_for_entry(entry)
            block = render_meeting_context_block(meeting_id, roster)
            out[meeting_id][str(entry["index"])] = {
                "roster": list(roster),
                "context_block": block,
                "context_block_sha256": config_hash({"text": block}),
            }
    return out


def build_binding_manifest(
    manifest: PattrManifest,
    pattr_manifest_path: Path,
    data_dir: Path,
    *,
    seed: int,
    tail_size: int,
    donor_source_relative: str,
) -> dict[str, Any]:
    x1_block = build_x1_block(manifest, seed)
    x2_block, tail_segments_by_meeting = build_x2_block(
        manifest, data_dir, seed=seed, tail_size=tail_size, donor_source_relative=donor_source_relative
    )
    renderings = build_renderings(manifest, x1_block["label_derangement"], tail_segments_by_meeting)

    combined_hashes = {
        arm: config_hash({"renderings": sorted(r["content_sha256"] for r in items)}) for arm, items in renderings.items()
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "P-PROMPT template-and-arrangement sweep (docs/readiness/2026-08-18-pprompt-preregistration.md)",
        "seed": seed,
        "pattr_manifest_reference": {
            "path": str(pattr_manifest_path.as_posix()) if isinstance(pattr_manifest_path, Path) else str(pattr_manifest_path),
            "sha256": hash_model_file(pattr_manifest_path),
        },
        "selected_meetings": list(manifest.selected_meetings),
        "templates": build_templates_block(),
        "arrangements": build_arrangements_block(),
        "per_meeting_context": build_per_meeting_context(manifest),
        "corrupt_arms": {"X1": x1_block, "X2": x2_block},
        "renderings": renderings,
        "renderings_combined_hash": combined_hashes,
        "totals": {
            "n_grid_requests": sum(len(renderings[cell]) for cell in GRID_CELLS),
            "n_x1_requests": len(renderings[ARM_X1]),
            "n_x2_requests": len(renderings[ARM_X2]),
            "n_total_requests": sum(len(v) for v in renderings.values()),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument(
        "--pattr-manifest",
        default="configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json",
        help="frozen P-ATTR manifest JSON (reused verbatim, never rebuilt)",
    )
    parser.add_argument("--out", default="configs/probes/pprompt/2026-08-18-pprompt-binding.json")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--tail-size", type=int, default=DEFAULT_TAIL_SIZE)
    parser.add_argument("--donor-source-relative", default=DEFAULT_DONOR_SOURCE_RELATIVE)
    parser.add_argument("--dry-run", action="store_true", help="print totals, write nothing")
    args = parser.parse_args(argv)

    pattr_manifest_path = Path(args.pattr_manifest)
    manifest = load_pattr_manifest(pattr_manifest_path)
    data_dir = Path(args.data_dir)

    binding = build_binding_manifest(
        manifest,
        pattr_manifest_path,
        data_dir,
        seed=args.seed,
        tail_size=args.tail_size,
        donor_source_relative=args.donor_source_relative,
    )

    print(json.dumps(binding["totals"], indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
