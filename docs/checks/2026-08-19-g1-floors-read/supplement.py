#!/usr/bin/env python3
"""G1 floors read -- SUPPLEMENT: the metric surface ``scripts/g1_read.py``
does not itself emit.

The committed read CLI scores the transcribe head only (cpWER, secondary
speaker-confusion, primary tcpWER-tcORC, grammar compliance, per arm x
meeting and pooled) and bootstraps the deployment gap on cpWER alone. The
floors preregistration (SS4) additionally requires the SAER-M reading on the
scoreable subset, the QA reading on the capped question set, and a
deployment gap PER METRIC. This script supplies exactly those, entirely from
COMMITTED scoring functions:

  * QA        -- ``heads.qa.parse_qa_response`` + ``g1_scoring.arm_qa_report``
                 (the reimplemented upstream max-over-alternatives scorer)
                 over the registered N=200/seed=20260818 capped set, rebuilt
                 deterministically by ``g1.select_capped_qa_questions``.
  * SAER-M    -- ``heads.minutes.parse_minutes_response`` +
                 ``g1_scoring.meeting_saer_m`` against each meeting's own
                 resolved ``EvidenceLink`` gold, plus the sentence-id JOIN
                 diagnostic that decides whether the resulting number is a
                 floor or an artefact.
  * gaps      -- ``g1_scoring.compute_deployment_gap`` (the same per-meeting
                 clustered paired bootstrap, same seed/replicates/CI level)
                 re-applied to the OTHER per-meeting metrics the read
                 already emitted into ``verdict.json``.

Zero model contact, zero run-dir mutation: reads the flown reply JSONLs and
the committed read's own ``verdict.json``, writes one JSON + one text report.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent
if (_REPO / "src").is_dir():
    sys.path.insert(0, str(_REPO / "src"))

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import resolve_meeting  # noqa: E402
from meeting_minutes_agent.corpora.roles import load_role_registry  # noqa: E402
from meeting_minutes_agent.heads.minutes import parse_minutes_response  # noqa: E402
from meeting_minutes_agent.heads.qa import parse_qa_response  # noqa: E402
from meeting_minutes_agent.probes import g1, g1_campaign, g1_scoring  # noqa: E402

ARMS_QA = g1.ARMS_WITH_MINUTES_QA


def load_all_responses(responses_dir: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for path in sorted(responses_dir.glob("chunk*-responses.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("outcome") == "ok":
                by_id[record["request_id"]] = record
    return by_id


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--responses-dir", required=True)
    ap.add_argument("--read-verdict", required=True, help="the committed read's verdict.json")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "supplement.json").exists():
        raise SystemExit("supplement.json already exists -- this supplement is one-shot too")

    responses = load_all_responses(Path(args.responses_dir))
    read_verdict = json.loads(Path(args.read_verdict).read_text(encoding="utf-8"))
    meetings = list(read_verdict["meetings"])

    out: dict[str, object] = {"meetings": meetings, "n_ok_responses": len(responses)}

    # ------------------------------------------------------------------
    # 1. QA -- the registered capped set, per arm and per meeting
    # ------------------------------------------------------------------
    registry = load_role_registry()
    all_questions = g1_campaign.load_dev18_usable_discovery_questions(
        meetingqa_root=data_dir / "datasets" / "meetingqa",
        ami_root=data_dir / "datasets" / "ami",
        registry=registry,
    )
    capped = g1.select_capped_qa_questions(all_questions, cap=g1.QA_CAP_N, seed=g1.QA_CAP_SEED)

    qa: dict[str, object] = {
        "n_usable_discovery_questions": len(all_questions),
        "n_capped": len(capped),
        "cap": g1.QA_CAP_N,
        "seed": g1.QA_CAP_SEED,
        "n_unanswerable_in_cap": sum(1 for q in capped if q.unanswerable),
        "by_arm": {},
    }
    qa_f1_by_arm_meeting: dict[str, dict[str, float]] = {}
    for arm in ARMS_QA:
        examples = []
        parse_modes = {"strict": 0, "lenient": 0, "failed": 0}
        n_abstain = 0
        missing = []
        per_meeting_ids: dict[str, list[str]] = {}
        for meeting_id in meetings:
            for q in g1.questions_for_meeting(capped, meeting_id):
                request_id = f"g1-{arm}-{meeting_id}-qa-{q.example_id}"
                record = responses.get(request_id)
                if record is None:
                    missing.append(request_id)
                    continue
                parsed = parse_qa_response(record["text"])
                parse_modes[parsed.parse_mode] += 1
                if parsed.parse_mode != "failed" and not parsed.answer_spans:
                    n_abstain += 1
                examples.append(
                    g1_scoring.QAExampleInput(
                        example_id=q.example_id,
                        reference_spans=tuple(q.answer_spans),
                        prediction_spans=tuple(parsed.answer_spans),
                    )
                )
                per_meeting_ids.setdefault(meeting_id, []).append(q.example_id)
        report = g1_scoring.arm_qa_report(examples)
        by_example = {s.example_id: s for s in report.per_example}
        per_meeting = {}
        for meeting_id, ids in per_meeting_ids.items():
            per_meeting[meeting_id] = {
                "n": len(ids),
                "macro_f1": statistics.fmean(by_example[i].upstream_meetingqa_f1 for i in ids),
                "macro_em": statistics.fmean(by_example[i].upstream_meetingqa_exact_match for i in ids),
            }
        qa_f1_by_arm_meeting[arm] = {m: v["macro_f1"] for m, v in per_meeting.items()}
        qa["by_arm"][arm] = {
            "n_examples": report.n_examples,
            "macro_f1": report.upstream_meetingqa_macro_f1,
            "macro_exact_match": report.upstream_meetingqa_macro_exact_match,
            "parse_modes": parse_modes,
            "n_abstentions": n_abstain,
            "n_missing_replies": len(missing),
            "per_meeting": per_meeting,
        }
    out["qa"] = qa

    # ------------------------------------------------------------------
    # 2. SAER-M -- scoreable subset + the sentence-id join diagnostic
    # ------------------------------------------------------------------
    corpus = NxtCorpus(data_dir / "datasets" / "ami" / "annotations" / "manual_1.6.2")
    saer: dict[str, object] = {"by_arm": {}}
    resolved_by_meeting = {m: resolve_meeting(corpus, m) for m in meetings}
    scoreable: list[str] = [m for m in meetings if resolved_by_meeting[m].evidence_links]
    saer["scoreable_meetings"] = scoreable
    saer["n_scoreable"] = len(scoreable)
    saer["unscoreable_meetings"] = [m for m in meetings if m not in scoreable]

    for arm in ARMS_QA:
        per_meeting = {}
        parse_modes = {"strict": 0, "lenient": 0, "failed": 0}
        for meeting_id in meetings:
            record = responses.get(f"g1-{arm}-{meeting_id}-minutes")
            if record is None:
                per_meeting[meeting_id] = {"error": "missing minutes reply"}
                continue
            parsed = parse_minutes_response(record["text"])
            parse_modes[parsed.parse_mode] += 1
            resolved = resolved_by_meeting[meeting_id]
            predictions = parsed.speaker_attribution_predictions()
            report = g1_scoring.meeting_saer_m(resolved.evidence_links, predictions)
            gold_ids = {link.sentence_id for link in resolved.evidence_links}
            pred_ids = {p.sentence_id for p in predictions}
            entry = {
                "scoreable": report is not None,
                "n_bullets": len(parsed.bullets),
                "parse_mode": parsed.parse_mode,
                "n_missing_sections": len(parsed.missing_sections),
                "n_bullets_with_speaker_claim": sum(1 for b in parsed.bullets if b.claimed_speaker),
                "n_gold_sentence_ids": len(gold_ids),
                "n_predicted_sentence_ids": len(pred_ids),
                "n_sentence_id_join": len(gold_ids & pred_ids),
                "example_gold_sentence_id": sorted(gold_ids)[0] if gold_ids else None,
                "example_predicted_sentence_id": sorted(pred_ids)[0] if pred_ids else None,
            }
            if report is not None:
                entry.update(
                    {
                        "accuracy": report.accuracy,
                        "n_scored": report.n_scored,
                        "n_correct": report.n_correct,
                        "n_wrong_speaker": report.n_wrong_speaker,
                        "n_unattributed": report.n_unattributed,
                        "n_hallucinated_speaker": report.n_hallucinated_speaker,
                    }
                )
            per_meeting[meeting_id] = entry
        saer["by_arm"][arm] = {"parse_modes": parse_modes, "per_meeting": per_meeting}
    out["saer_m"] = saer

    # ------------------------------------------------------------------
    # 3. deployment gap per metric (the read emitted cpWER's own gap)
    # ------------------------------------------------------------------
    pooled = read_verdict["pooled_by_arm"]

    def per_meeting_metric(arm: str, key: str) -> dict[str, float]:
        return {
            m: v[key]
            for m, v in pooled[arm]["per_meeting"].items()
            if v.get(key) is not None
        }

    gaps: dict[str, object] = {"cp_wer_from_read": read_verdict["deployment_gap"]}
    for key, label in (
        ("mean_secondary_confusion_cost", "secondary_confusion_cost"),
        ("mean_primary_confusion_cost", "primary_confusion_cost"),
        ("mean_grammar_compliance", "grammar_compliance"),
    ):
        turn = per_meeting_metric(g1.ARM_Z_TURN, key)
        oracle = per_meeting_metric(g1.ARM_Z_ORACLE, key)
        common = sorted(set(turn) & set(oracle))
        result = g1_scoring.compute_deployment_gap(
            {m: turn[m] for m in common}, {m: oracle[m] for m in common}, metric=label
        )
        d = result.to_dict()
        d["n_meetings"] = len(common)
        d["meetings_dropped"] = sorted((set(turn) | set(oracle)) - set(common))
        gaps[label] = d

    qa_turn = qa_f1_by_arm_meeting[g1.ARM_Z_TURN]
    qa_oracle = qa_f1_by_arm_meeting[g1.ARM_Z_ORACLE]
    common_qa = sorted(set(qa_turn) & set(qa_oracle))
    if common_qa:
        result = g1_scoring.compute_deployment_gap(
            {m: qa_turn[m] for m in common_qa}, {m: qa_oracle[m] for m in common_qa}, metric="qa_macro_f1"
        )
        d = result.to_dict()
        d["n_meetings"] = len(common_qa)
        gaps["qa_macro_f1"] = d
    out["deployment_gaps"] = gaps

    (out_dir / "supplement.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = ["G1 floors read -- SUPPLEMENT (QA, SAER-M, per-metric gaps)", "=" * 78, ""]
    lines.append("QA (registered cap N=%d seed=%d; %d of %d usable-discovery questions)"
                 % (g1.QA_CAP_N, g1.QA_CAP_SEED, len(capped), len(all_questions)))
    for arm in ARMS_QA:
        a = qa["by_arm"][arm]
        lines.append(
            f"  {arm:10s} n={a['n_examples']:3d} macroF1={a['macro_f1']:.4f} EM={a['macro_exact_match']:.4f} "
            f"parse={a['parse_modes']} abstain={a['n_abstentions']}"
        )
    lines += ["", "SAER-M (scoreable n=%d of %d)" % (len(scoreable), len(meetings))]
    for arm in ARMS_QA:
        entries = [e for e in saer["by_arm"][arm]["per_meeting"].values() if e.get("scoreable")]
        joins = sum(e["n_sentence_id_join"] for e in entries)
        acc = [e["accuracy"] for e in entries if e.get("accuracy") is not None]
        lines.append(
            f"  {arm:10s} scoreable={len(entries)} mean_accuracy="
            f"{(statistics.fmean(acc) if acc else float('nan')):.4f} total_sentence_id_join={joins} "
            f"parse={saer['by_arm'][arm]['parse_modes']}"
        )
    lines += ["", "DEPLOYMENT GAPS (Z-turn - Z-oracle, per-meeting clustered paired bootstrap)"]
    for label, d in gaps.items():
        g = d["gap"] if "gap" in d else d
        lines.append(
            f"  {label:26s} point={g['point_estimate']:+.4f} "
            f"CI[{g['ci_low']:+.4f},{g['ci_high']:+.4f}] excludes_zero={g['excludes_zero']} "
            f"n_meetings={d.get('n_meetings', 'read')}"
        )
    (out_dir / "supplement.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
