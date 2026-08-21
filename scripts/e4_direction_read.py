#!/usr/bin/env python3
"""Perform the one-shot read for E4-DISJOINT-DIR."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.e4_disjoint_direction import load_runtime_binding, load_score_binding  # noqa: E402
from meeting_minutes_agent.probes.e4_disjoint_direction_scoring import build_verdict, load_scores, render_report  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-binding", required=True)
    parser.add_argument("--score-binding", required=True)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        parser.error("output directory exists; refusing overwrite")
    runtime = load_runtime_binding(args.runtime_binding)
    score = load_score_binding(args.score_binding)
    responses = Path(args.responses)
    scores = load_scores(runtime, score, responses)
    verdict = build_verdict(runtime, score, scores)
    verdict["inputs"] = {
        "runtime_binding_sha256": _sha(Path(args.runtime_binding)),
        "score_binding_sha256": _sha(Path(args.score_binding)),
        "responses_sha256": _sha(responses),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.txt").write_text(render_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "targets": verdict["targets"], "calls": verdict["calls"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
