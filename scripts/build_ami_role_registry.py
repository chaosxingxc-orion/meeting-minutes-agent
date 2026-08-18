#!/usr/bin/env python3
"""Build the AMI role registry and the three-way overlap matrix from shipped bytes.

Reads only local corpus files -- the AMI on-disk meeting roster and manual
annotation tree, the MeetingQA AMI splits, and the QMSum Product splits. No
model contact, no network, CPU only, seconds.

Emits:

* the machine overlap matrix (one row per on-disk AMI meeting x
  {our ASR partition role, MeetingQA split membership, QMSum membership,
  annotation-stack completeness});
* the role registry consumed by
  ``meeting_minutes_agent.corpora.roles.load_role_registry``;
* a readable Markdown table of the same matrix.

Assignment rules, applied in order, first match wins -- so the assignment is
total over the roster and exactly one role lands per meeting:

* **R1** meeting in the frozen ASR dev-18 -> ``asr-eval`` (the G1 flight set).
* **R2** meeting in the frozen ASR eval-16 -> ``held-out-confirmatory``.
  Never a discovery or evaluation role, under any corpus.
* **R3** meeting in the held-out-137 and in MeetingQA's *test* split ->
  ``qa-eval``.
* **R4** meeting in the held-out-137, not R3, with a full annotation stack ->
  ``glossary-discovery``.
* **R5** everything else -> ``held-out-reserve``.

Quarantine rule **Q1**: a MeetingQA question is usable only when its meeting's
role is ``qa-eval``. Every other MeetingQA question straddles roles (its
meeting is spoken for by the ASR flight set, by glossary discovery, or is held
out) and is quarantined -- listed explicitly in the registry.

Usage::

    python scripts/build_ami_role_registry.py --data-root "$SPEECHRL_DATA_DIR/datasets"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.corpora.roles import (  # noqa: E402
    FROZEN_DEV_18,
    FROZEN_EVAL_16,
    MeetingRole,
)

#: Annotation layers that together make a "full stack" for glossary discovery:
#: a meeting we can mine terms from *and* score structure against. Counts
#: reconcile with the 2026-08-17 local audit (142 abstractive, 137
#: extractive+summlink, 139 topics, 139 dialogue acts, 171 words/segments).
FULL_STACK_LAYERS = {
    "abstractive": ("abstractive", ".abssumm.xml"),
    "extractive": ("extractive", ".extsumm.xml"),
    "summlink": ("extractive", ".summlink.xml"),
    "topics": ("topics", ".topic.xml"),
    "dialogue_acts": ("dialogueActs", ".dialog-act.xml"),
    "words": ("words", ".words.xml"),
    "segments": ("segments", ".segments.xml"),
}

#: Recorded for provenance only -- the named-entity layer is not a full-stack
#: requirement (it covers a different 117-meeting subset).
NE_LAYER = ("namedEntities", ".ne.xml")


def ami_roster(ami_root: Path) -> tuple[str, ...]:
    corpus = ami_root / "amicorpus"
    return tuple(sorted(d.name for d in corpus.iterdir() if d.is_dir()))


def annotation_stacks(ami_root: Path, roster: tuple[str, ...]) -> dict[str, dict[str, bool]]:
    manual = ami_root / "annotations" / "manual_1.6.2"
    layers = dict(FULL_STACK_LAYERS)
    layers["named_entities"] = NE_LAYER
    out: dict[str, dict[str, bool]] = {m: {} for m in roster}
    for layer, (subdir, suffix) in layers.items():
        covered = Counter(p.name.split(".")[0] for p in (manual / subdir).glob("*" + suffix))
        for meeting in roster:
            out[meeting][layer] = covered.get(meeting, 0) > 0
    return out


def meetingqa_membership(meetingqa_root: Path) -> dict[str, tuple[str, int]]:
    """meeting id -> (MeetingQA split, question count).

    Source of truth is the shipped question files (``final-AMI-<split>.json``,
    field ``title``); the parallel ``ProcessedTranscripts/Annotated-AMI-QA/<split>/``
    directories agree exactly and are used as a cross-check.
    """

    dataset = meetingqa_root / "AllData" / "Dataset"
    out: dict[str, tuple[str, int]] = {}
    for split in ("train", "dev", "test"):
        payload = json.loads((dataset / f"final-AMI-{split}.json").read_text(encoding="utf-8"))
        counts = Counter(record["title"] for record in payload["data"])
        transcripts = meetingqa_root / "ProcessedTranscripts" / "Annotated-AMI-QA" / split
        if transcripts.is_dir():
            dir_ids = {p.stem for p in transcripts.glob("*.json")}
            if dir_ids != set(counts):
                raise SystemExit(
                    f"MeetingQA {split}: question titles and transcript directory disagree "
                    f"({sorted(set(counts) ^ dir_ids)})"
                )
        for meeting, n in counts.items():
            if meeting in out:
                raise SystemExit(f"MeetingQA meeting {meeting!r} appears in two splits")
            out[meeting] = (split, n)
    return out


def qmsum_membership(qmsum_root: Path) -> dict[str, str]:
    """meeting id -> QMSum Product split. QMSum's AMI material is its Product
    domain only; Academic (ICSI) and Committee (parliamentary) carry no AMI
    ids."""

    out: dict[str, str] = {}
    for split in ("train", "val", "test"):
        for path in (qmsum_root / "data" / "Product" / split).glob("*.json"):
            if path.stem in out:
                raise SystemExit(f"QMSum meeting {path.stem!r} appears in two splits")
            out[path.stem] = split
    return out


def assign_role(
    meeting: str, meetingqa_split: str | None, full_stack: bool
) -> tuple[MeetingRole, str]:
    if meeting in FROZEN_DEV_18:
        return MeetingRole.ASR_EVAL, "R1"
    if meeting in FROZEN_EVAL_16:
        return MeetingRole.HELD_OUT_CONFIRMATORY, "R2"
    if meetingqa_split == "test":
        return MeetingRole.QA_EVAL, "R3"
    if full_stack:
        return MeetingRole.GLOSSARY_DISCOVERY, "R4"
    return MeetingRole.HELD_OUT_RESERVE, "R5"


def build(data_root: Path) -> dict[str, Any]:
    ami_root = data_root / "ami"
    roster = ami_roster(ami_root)
    stacks = annotation_stacks(ami_root, roster)
    mqa = meetingqa_membership(data_root / "meetingqa")
    qmsum = qmsum_membership(data_root / "qmsum")

    off_roster = sorted((set(mqa) | set(qmsum)) - set(roster))
    if off_roster:
        raise SystemExit(f"corpora reference AMI meetings that are not on disk: {off_roster}")

    rows: dict[str, dict[str, Any]] = {}
    for meeting in roster:
        stack = stacks[meeting]
        full_stack = all(stack[layer] for layer in FULL_STACK_LAYERS)
        split, questions = mqa.get(meeting, (None, 0))
        if meeting in FROZEN_DEV_18:
            partition = "dev-18"
        elif meeting in FROZEN_EVAL_16:
            partition = "eval-16"
        else:
            partition = "held-out-137"
        role, rule = assign_role(meeting, split, full_stack)
        rows[meeting] = {
            "role": role.value,
            "rule": rule,
            "asr_partition": partition,
            "meetingqa_split": split,
            "meetingqa_questions": questions,
            "qmsum_split": qmsum.get(meeting),
            "full_annotation_stack": full_stack,
            "annotation_layers": {k: stack[k] for k in sorted(stack)},
        }
    return {"roster": roster, "rows": rows}


def matrix_document(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    partitions = Counter(r["asr_partition"] for r in rows.values())
    mqa_splits = Counter(str(r["meetingqa_split"]) for r in rows.values())
    qmsum_splits = Counter(str(r["qmsum_split"]) for r in rows.values())
    cross = Counter((r["asr_partition"], str(r["meetingqa_split"])) for r in rows.values())
    return {
        "n_meetings": len(rows),
        "asr_partition": dict(sorted(partitions.items())),
        "meetingqa_split": dict(sorted(mqa_splits.items())),
        "meetingqa_questions_total": sum(r["meetingqa_questions"] for r in rows.values()),
        "qmsum_split": dict(sorted(qmsum_splits.items())),
        "full_annotation_stack": sum(1 for r in rows.values() if r["full_annotation_stack"]),
        "asr_partition_x_meetingqa_split": {
            f"{a}|{b}": n for (a, b), n in sorted(cross.items())
        },
        "rows": rows,
    }


def registry_document(rows: dict[str, dict[str, Any]], matrix_relpath: str) -> dict[str, Any]:
    meetings = {
        meeting: {
            "role": row["role"],
            "rule": row["rule"],
            "asr_partition": row["asr_partition"],
            "meetingqa_split": row["meetingqa_split"],
            "meetingqa_questions": row["meetingqa_questions"],
            "qmsum_split": row["qmsum_split"],
            "full_annotation_stack": row["full_annotation_stack"],
        }
        for meeting, row in sorted(rows.items())
    }
    role_counts = {role.value: 0 for role in MeetingRole}
    for row in rows.values():
        role_counts[row["role"]] += 1

    quarantine = [
        {
            "meeting_id": meeting,
            "role": row["role"],
            "meetingqa_split": row["meetingqa_split"],
            "n_questions": row["meetingqa_questions"],
            "reason": (
                "eval-16 confirmatory hold-out"
                if row["role"] == MeetingRole.HELD_OUT_CONFIRMATORY.value
                else f"meeting is spoken for by role {row['role']!r}"
            ),
        }
        for meeting, row in sorted(rows.items())
        if row["meetingqa_questions"] > 0 and row["role"] != MeetingRole.QA_EVAL.value
    ]

    return {
        "schema_version": "1.0.0",
        "registry_id": "ami-role-registry",
        "purpose": (
            "One role per AMI meeting, machine-checked fail-closed. G1 precondition from the "
            "2026-08-17 deep check; loader/validator: meeting_minutes_agent.corpora.roles."
        ),
        "corpus": {
            "name": "ami-meeting-corpus",
            "lock_key": "ami-meeting-corpus",
            "n_meetings": len(rows),
            "roster_source": "on-disk amicorpus/<ID>/ directories",
        },
        "provenance": {
            "asr_partition": (
                "docs/readiness/2026-08-17-ami-split-freeze-proposal.md (Convention A, full-corpus "
                "ASR partition dev 18 / eval 16 / held-out remainder 137). Caveat carried verbatim: "
                "the dev-18 and eval-16 ids are published-standard lists transcribed from knowledge, "
                "partially corroborated by shipped meetings.xml attributes (12/18 and 12/16, zero "
                "contradictions), NOT sourced from a shipped file."
            ),
            "meetingqa": (
                "AllData/Dataset/final-AMI-{train,dev,test}.json, field 'title'; cross-checked "
                "against ProcessedTranscripts/Annotated-AMI-QA/<split>/ (exact agreement)."
            ),
            "qmsum": "data/Product/{train,val,test}/<meeting>.json (QMSum's AMI material).",
            "annotation_stack": (
                "ami_public_manual_1.6.2 per-layer file presence; full stack = abstractive + "
                "extsumm + summlink + topics + dialogue acts + words + segments."
            ),
            "builder": "scripts/build_ami_role_registry.py",
            "matrix": matrix_relpath,
        },
        "roles": {
            MeetingRole.ASR_EVAL.value: "G1 flight set: chunked transcription + attribution scoring.",
            MeetingRole.QA_EVAL.value: "MeetingQA evaluation surface. The only role whose questions are usable.",
            MeetingRole.GLOSSARY_DISCOVERY.value: "Glossary/term-mining discovery surface; never scored as eval.",
            MeetingRole.HELD_OUT_CONFIRMATORY.value: "Frozen eval-16. No exposure, no scoring, no discovery. Ever.",
            MeetingRole.HELD_OUT_RESERVE.value: "Held-out remainder with no assigned role. No exposure.",
        },
        "assignment_rules": {
            "R1": "meeting in frozen ASR dev-18 -> asr-eval",
            "R2": "meeting in frozen ASR eval-16 -> held-out-confirmatory",
            "R3": "meeting in held-out-137 and MeetingQA test split -> qa-eval",
            "R4": "meeting in held-out-137, not R3, with a full annotation stack -> glossary-discovery",
            "R5": "otherwise -> held-out-reserve",
            "order": "first match wins; the assignment is total over the roster",
        },
        "frozen_splits": {
            "dev_18": list(FROZEN_DEV_18),
            "eval_16": list(FROZEN_EVAL_16),
        },
        "role_counts": role_counts,
        "quarantine": {
            "rule": (
                "Q1: a MeetingQA question is usable only when its meeting's registry role is "
                "'qa-eval'. Every other MeetingQA question straddles roles and is quarantined."
            ),
            "n_meetings": len(quarantine),
            "n_questions": sum(entry["n_questions"] for entry in quarantine),
            "meetings": quarantine,
        },
        "meetings": meetings,
    }


def markdown_table(rows: dict[str, dict[str, Any]]) -> str:
    counts = Counter(row["role"] for row in rows.values())
    lines = [
        "# AMI three-way overlap matrix (generated)",
        "",
        "Generated by `scripts/build_ami_role_registry.py` from shipped bytes; do not hand-edit.",
        "Narrative, rules and the quarantine list: `2026-08-18-ami-role-registry.md`.",
        "Machine form: `2026-08-18-ami-overlap-matrix.json`. Registry:",
        "`configs/corpora/ami-role-registry.json`.",
        "",
        f"{len(rows)} meetings; roles "
        + ", ".join(f"{role} {n}" for role, n in sorted(counts.items()))
        + ".",
        "",
        "| meeting | ASR partition | MeetingQA split | MeetingQA Q | QMSum | full stack | role | rule |",
        "|---|---|---|---:|---|:---:|---|---|",
    ]
    for meeting, row in sorted(rows.items()):
        lines.append(
            "| {m} | {p} | {q} | {n} | {s} | {f} | {r} | {rule} |".format(
                m=meeting,
                p=row["asr_partition"],
                q=row["meetingqa_split"] or "-",
                n=row["meetingqa_questions"],
                s=row["qmsum_split"] or "-",
                f="yes" if row["full_annotation_stack"] else "no",
                r=row["role"],
                rule=row["rule"],
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, help="datasets root holding ami/, meetingqa/, qmsum/")
    parser.add_argument("--registry-out", default="configs/corpora/ami-role-registry.json")
    parser.add_argument("--matrix-out", default="docs/readiness/2026-08-18-ami-overlap-matrix.json")
    parser.add_argument("--table-out", default=None, help="optional Markdown table path")
    parser.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = parser.parse_args(argv)

    built = build(Path(args.data_root))
    rows = built["rows"]
    matrix = matrix_document(rows)
    registry = registry_document(rows, args.matrix_out)

    summary = {
        "n_meetings": matrix["n_meetings"],
        "asr_partition": matrix["asr_partition"],
        "meetingqa_split": matrix["meetingqa_split"],
        "meetingqa_questions_total": matrix["meetingqa_questions_total"],
        "qmsum_split": matrix["qmsum_split"],
        "full_annotation_stack": matrix["full_annotation_stack"],
        "role_counts": registry["role_counts"],
        "quarantine": {
            "n_meetings": registry["quarantine"]["n_meetings"],
            "n_questions": registry["quarantine"]["n_questions"],
        },
        "asr_partition_x_meetingqa_split": matrix["asr_partition_x_meetingqa_split"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.dry_run:
        return 0

    for path, document in ((Path(args.registry_out), registry), (Path(args.matrix_out), matrix)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)
    if args.table_out:
        Path(args.table_out).write_text(markdown_table(rows), encoding="utf-8")
        print(f"wrote {args.table_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
