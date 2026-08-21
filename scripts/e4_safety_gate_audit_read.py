#!/usr/bin/env python3
"""Run the sole frozen, zero-model E4 safety-gate audit read."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.probes.e4_confirmatory import load_pass0_runtime  # noqa: E402
from meeting_minutes_agent.probes.e4_disjoint_direction import (  # noqa: E402
    load_runtime_binding,
    load_score_binding,
)
from meeting_minutes_agent.probes.e4_disjoint_direction_scoring import load_scores  # noqa: E402
from meeting_minutes_agent.probes.e4_mechanism import load_jsonl  # noqa: E402
from meeting_minutes_agent.probes.e4_safety_gate_audit import (  # noqa: E402
    build_safety_gate_verdict,
    render_safety_gate_report,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", required=True)
    parser.add_argument("--runtime-binding", required=True)
    parser.add_argument("--score-binding", required=True)
    parser.add_argument("--pass0-responses", action="append", required=True)
    parser.add_argument("--secondpass-responses", required=True)
    parser.add_argument("--official-verdict", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        parser.error("audit output directory exists; refusing overwrite")

    runtime_manifest_path = Path(args.runtime_manifest)
    runtime_path = Path(args.runtime_binding)
    score_path = Path(args.score_binding)
    pass0_paths = [Path(path) for path in args.pass0_responses]
    secondpass_path = Path(args.secondpass_responses)
    official_path = Path(args.official_verdict)
    runtime = load_runtime_binding(runtime_path)
    score = load_score_binding(score_path)
    pass0_records = tuple(record for path in pass0_paths for record in load_jsonl(path))
    verdict = build_safety_gate_verdict(
        load_pass0_runtime(runtime_manifest_path),
        runtime,
        score,
        pass0_records,
        load_scores(runtime, score, secondpass_path),
        json.loads(official_path.read_text(encoding="utf-8")),
    )
    verdict["input_sha256"] = {
        "runtime_manifest": _sha(runtime_manifest_path),
        "runtime_binding": _sha(runtime_path),
        "score_binding": _sha(score_path),
        "pass0_responses": {str(path): _sha(path) for path in pass0_paths},
        "secondpass_responses": _sha(secondpass_path),
        "official_verdict": _sha(official_path),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "report.txt").write_text(render_safety_gate_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "selected_candidate": verdict["selected_candidate"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
