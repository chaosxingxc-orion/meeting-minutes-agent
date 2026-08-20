#!/usr/bin/env python3
"""G1 floors read -- ARM CONTRASTS for the Z-free / Z-nodiar ablations.

The floors preregistration SS4 binds EVERY comparison to the same
discipline, not only the deployment gap: "no comparison is narrated as real
unless its CI excludes zero". The read CLI bootstraps the Z-turn - Z-oracle
gap alone, so the ablation readings need the same per-meeting-clustered
paired bootstrap applied to their own per-meeting numbers -- computed here
with the SAME committed primitive
(``g1_scoring.compute_deployment_gap``: seed 20260818, 10,000 replicates,
90 % percentile CI, clustered at meeting granularity), over the per-meeting
means ``verdict.json`` already carries. Pure arithmetic on the read's own
output: no reply is re-read and no metric is recomputed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from meeting_minutes_agent.probes import g1_scoring

CONTRASTS = (
    ("Z-free", "Z-turn"),
    ("Z-nodiar", "Z-turn"),
    ("Z-nodiar", "Z-free"),
    ("Z-free", "Z-oracle"),
)
METRICS = (("mean_cp_wer", "cp_wer"), ("mean_secondary_confusion_cost", "secondary_confusion_cost"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--read-verdict", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if (out_dir / "ablations.json").exists():
        raise SystemExit("ablations.json already exists -- one-shot")

    verdict = json.loads(Path(args.read_verdict).read_text(encoding="utf-8"))
    pooled = verdict["pooled_by_arm"]

    results: dict[str, object] = {}
    lines = ["G1 floors read -- ARM CONTRASTS (per-meeting clustered paired bootstrap)", "=" * 78, ""]
    for minuend, subtrahend in CONTRASTS:
        for key, label in METRICS:
            a = {m: v[key] for m, v in pooled[minuend]["per_meeting"].items() if v.get(key) is not None}
            b = {m: v[key] for m, v in pooled[subtrahend]["per_meeting"].items() if v.get(key) is not None}
            common = sorted(set(a) & set(b))
            result = g1_scoring.compute_deployment_gap(
                {m: a[m] for m in common}, {m: b[m] for m in common}, metric=label
            )
            name = f"{minuend} - {subtrahend} :: {label}"
            d = result.to_dict()
            d["n_meetings"] = len(common)
            d["meetings_dropped"] = sorted((set(a) | set(b)) - set(common))
            results[name] = d
            g = d["gap"]
            lines.append(
                f"  {name:44s} point={g['point_estimate']:+.4f} "
                f"CI[{g['ci_low']:+.4f},{g['ci_high']:+.4f}] excludes_zero={g['excludes_zero']} n={d['n_meetings']}"
            )

    (out_dir / "ablations.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "ablations.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
