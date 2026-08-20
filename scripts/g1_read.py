#!/usr/bin/env python3
"""G1 floors campaign -- registered ONE-SHOT scoring read.

Runs the committed scoring path (:mod:`meeting_minutes_agent.probes.g1_scoring`)
over every arm's flown replies and writes ``verdict.json`` + ``report.txt``
to ``--out-dir``, mirroring ``scripts/pprompt_read.py``'s own read pair.
Refuses (fail-closed) to overwrite a prior read's output unless ``--force``
is passed
(:func:`~meeting_minutes_agent.probes.g1_scoring.assert_one_shot_output_dir`).

Real I/O, zero model contact: this script reads already-flown reply JSONLs
(never sends a request) and resolves the AMI gold transcript for every
scored meeting via :mod:`meeting_minutes_agent.corpora.nxt`.

DESCRIPTIVE FLOORS ONLY -- no branch verdicts (task discipline): this
script's ``verdict.json`` carries per-arm x per-meeting tables, pooled
numbers, and the deployment gap's bootstrap CI, never a winner/pass-fail
classification.

Usage::

    python scripts/g1_read.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --responses-dir "$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/<run-id>" \\
        --vad-manifest-dir "$SPEECHRL_DATA_DIR/derived/meeting-minutes/precomp/slices/vad-manifest" \\
        --meetings ES2011a IS1008a \\
        --out-dir docs/checks/<campaign>/<release-id>

``--vad-manifest-dir`` names where the PRECOMP VAD supplement wrote its
per-meeting ``SlicePlan`` JSON -- the SAME directory ``scripts/run_g1.py``
was flown against. Z-nodiar's slice plan exists ONLY in that manifest (it is
never rebuilt from an RTTM or from NXT turns), so a read that omits the flag
fails closed on Z-nodiar with
:class:`~meeting_minutes_agent.probes.g1.G1VadSupplementMissingError` rather
than scoring three of the four registered arms and calling that a floors
table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting  # noqa: E402
from meeting_minutes_agent.metrics.pins import default_metric_pins  # noqa: E402
from meeting_minutes_agent.probes import g1  # noqa: E402
from meeting_minutes_agent.probes import g1_scoring  # noqa: E402
from meeting_minutes_agent.probes.pattr_scoring import extract_gold_streams_for_range  # noqa: E402
from meeting_minutes_agent.runreceipt import read_git_state  # noqa: E402


def load_responses(path: Path) -> list[dict]:
    """Every ``outcome == "ok"`` record in one arm's JSONL, in file order --
    the same rule ``scripts/pprompt_read.py::load_responses`` uses."""

    if not path.is_file():
        raise FileNotFoundError(f"no responses file: {path}")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("outcome") == "ok":
            records.append(record)
    return records


def responses_path(responses_dir: Path, chunk_index: int) -> Path:
    return responses_dir / f"chunk{chunk_index:04d}-responses.jsonl"


def load_all_responses(responses_dir: Path) -> dict[str, dict]:
    """Every ``chunk*-responses.jsonl`` file under ``responses_dir``, merged
    into one ``{request_id: record}`` map -- a real campaign spans many
    chunk invocations (task discipline: resumable chunks), so the read
    consumes however many response files exist rather than a fixed count."""

    by_request_id: dict[str, dict] = {}
    for path in sorted(responses_dir.glob("chunk*-responses.jsonl")):
        for record in load_responses(path):
            by_request_id[record["request_id"]] = record
    return by_request_id


def score_transcribe_arm_meeting(
    arm: str, meeting_id: str, plan, resolved_meeting, responses_by_id: Mapping[str, dict], *, pins=None
) -> g1_scoring.ArmMeetingScore:
    """Score every transcribe-span slice of ``plan`` for ``(arm, meeting_id)``
    against already-flown replies. Raises if a slice's own reply is
    missing -- a partial arm/meeting read is a defect, never silently
    scored short."""

    specs = g1.build_transcribe_requests(arm, meeting_id, plan, slice_dir_relative="unused")
    scores = []
    for spec, sl in zip(specs, plan.slices):
        record = responses_by_id.get(spec.request_id)
        if record is None:
            raise RuntimeError(f"missing flown reply for {spec.request_id!r} under the given --responses-dir")
        reference = extract_gold_streams_for_range(resolved_meeting, start=sl.start, end=sl.end)
        scores.append(
            g1_scoring.score_transcribe_slice(
                arm, meeting_id, sl.index, reference, record["text"], sl.turns,
                slice_start=sl.start, slice_end=sl.end, usage=record.get("usage"),
                request_max_tokens=record.get("max_tokens"),
                pins=pins,
            )
        )
    return g1_scoring.aggregate_arm_meeting(arm, meeting_id, scores)


def build_report_text(*, created_utc: str, study_commit: str, pins_hash: str, meetings, pooled_by_arm, gap) -> str:
    lines = [
        "G1 floors campaign -- descriptive read (NO branch verdicts)",
        "=" * 78,
        f"created_utc  : {created_utc}",
        f"study_commit : {study_commit}",
        f"pins_hash    : {pins_hash}",
        f"meetings     : {', '.join(meetings)}",
        "",
        "POOLED PER-ARM MEAN cpWER",
        "-" * 78,
    ]
    for arm, pooled in pooled_by_arm.items():
        mean_cp_wer = "n/a" if pooled.mean_cp_wer is None else f"{pooled.mean_cp_wer:.4f}"
        lines.append(
            f"  {arm:10s} mean_cpWER={mean_cp_wer} n_meetings={pooled.n_meetings} "
            f"capped_replies={pooled.total_capped_replies}/{pooled.total_slices} "
            f"reference_empty={pooled.total_reference_empty} orc_refused={pooled.total_confusion_refused}"
        )
    lines += [
        "",
        "DEPLOYMENT GAP (Z-turn - Z-oracle, per-meeting-clustered bootstrap CI)",
        "-" * 78,
        f"  point_estimate = {gap.gap.point_estimate:+.4f}",
        f"  {int(gap.gap.ci_level * 100)}% CI = [{gap.gap.ci_low:+.4f}, {gap.gap.ci_high:+.4f}] "
        f"(sigma_hat={gap.gap.sigma_hat:.4f}, n_replicates={gap.gap.n_replicates}, seed={gap.gap.seed})",
        f"  CI excludes zero: {gap.gap.excludes_zero}",
        f"  P-PROMPT single-run noise reference (cpWER): {gap.noise_reference_cp_wer}",
        "",
        "This read is DESCRIPTIVE ONLY -- no branch verdict is computed or implied.",
        "",
    ]
    return "\n".join(lines)


def run_read(
    *,
    data_dir: Path,
    responses_dir: Path,
    meetings: list[str],
    out_dir: Path,
    force: bool,
    vad_manifest_dir: Path | None = None,
    ami_annotations_root_relative: str = "datasets/ami/annotations/manual_1.6.2",
    resolved_meetings: Mapping[str, Any] | None = None,
    slice_plans_by_meeting_arm: Mapping[tuple[str, str], Any] | None = None,
) -> dict[str, Any]:
    """``resolved_meetings``/``slice_plans_by_meeting_arm`` are injection
    seams (default ``None``, meaning "resolve for real"): a test supplies
    small, hand-built mappings so this function's own scoring/aggregation
    wiring is exercisable without real AMI annotation bytes or a real
    PRECOMP cache -- mirrors ``scripts/pprompt_read.py::run_read``'s own
    ``resolved_meetings`` seam."""

    g1_scoring.assert_one_shot_output_dir(out_dir, force=force)

    if resolved_meetings is None:
        corpus = NxtCorpus(Path(data_dir) / ami_annotations_root_relative)
        resolved_meetings = {meeting_id: resolve_meeting(corpus, meeting_id) for meeting_id in meetings}

    if slice_plans_by_meeting_arm is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import run_g1 as runner  # noqa: E402

        nxt_corpus = NxtCorpus(Path(data_dir) / ami_annotations_root_relative)
        slice_plans_by_meeting_arm = runner.resolve_all_slice_plans(
            meetings, g1.ARMS, data_dir=Path(data_dir),
            derived_root=Path(data_dir) / runner.DEFAULT_DERIVED_ROOT_RELATIVE, nxt_corpus=nxt_corpus,
            vad_manifest_dir=Path(vad_manifest_dir) if vad_manifest_dir is not None else None,
        )

    responses_by_id = load_all_responses(responses_dir)
    pins = default_metric_pins()

    per_meeting_by_arm: dict[str, list[g1_scoring.ArmMeetingScore]] = {arm: [] for arm in g1.ARMS}
    for meeting_id in meetings:
        for arm in g1.ARMS:
            plan, _slice_dir = slice_plans_by_meeting_arm[(meeting_id, arm)]
            score = score_transcribe_arm_meeting(
                arm, meeting_id, plan, resolved_meetings[meeting_id], responses_by_id, pins=pins
            )
            per_meeting_by_arm[arm].append(score)

    pooled_by_arm = {arm: g1_scoring.aggregate_pooled(arm, scores) for arm, scores in per_meeting_by_arm.items()}

    # A meeting whose mean is undefined on EITHER arm (every slice's gold
    # reference empty) cannot enter a PAIRED gap; dropped explicitly and
    # disclosed, never silently one-sided.
    z_turn_by_meeting = {
        s.meeting_id: s.mean_cp_wer for s in per_meeting_by_arm[g1.ARM_Z_TURN] if s.mean_cp_wer is not None
    }
    z_oracle_by_meeting = {
        s.meeting_id: s.mean_cp_wer for s in per_meeting_by_arm[g1.ARM_Z_ORACLE] if s.mean_cp_wer is not None
    }
    paired_meetings = sorted(set(z_turn_by_meeting) & set(z_oracle_by_meeting))
    dropped_meetings = sorted(set(meetings) - set(paired_meetings))
    gap = g1_scoring.compute_deployment_gap(
        {m: z_turn_by_meeting[m] for m in paired_meetings},
        {m: z_oracle_by_meeting[m] for m in paired_meetings},
    )

    from datetime import datetime, timezone

    created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    git = read_git_state(Path(__file__).resolve().parent.parent)

    verdict = {
        "created_utc": created_utc,
        "study_commit": git.commit,
        "pins_hash": pins.content_hash(),
        "meetings": list(meetings),
        "pooled_by_arm": {arm: pooled.to_dict() for arm, pooled in pooled_by_arm.items()},
        "deployment_gap": gap.to_dict(),
        "deployment_gap_meetings": paired_meetings,
        "deployment_gap_meetings_dropped": dropped_meetings,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_text = build_report_text(
        created_utc=created_utc, study_commit=git.commit or "<unknown>", pins_hash=pins.content_hash(),
        meetings=meetings, pooled_by_arm=pooled_by_arm, gap=gap,
    )
    (out_dir / "report.txt").write_text(report_text, encoding="utf-8")
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument("--responses-dir", required=True, help="directory holding chunk*-responses.jsonl")
    parser.add_argument(
        "--vad-manifest-dir",
        default=None,
        help="directory of Z-nodiar's per-meeting SlicePlan JSON (the PRECOMP VAD supplement's own "
        "output, the same path scripts/run_g1.py was flown with); omitting it fails closed on Z-nodiar",
    )
    parser.add_argument("--meetings", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    verdict = run_read(
        data_dir=Path(args.data_dir), responses_dir=Path(args.responses_dir), meetings=list(args.meetings),
        out_dir=Path(args.out_dir), force=args.force,
        vad_manifest_dir=Path(args.vad_manifest_dir) if args.vad_manifest_dir is not None else None,
    )
    print(json.dumps({"pooled_by_arm": verdict["pooled_by_arm"], "deployment_gap": verdict["deployment_gap"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
