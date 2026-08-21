#!/usr/bin/env python3
"""Run the prebuilt one-shot E3 legal-state read."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.state_audit import load_manifest  # noqa: E402
from meeting_minutes_agent.probes.state_audit_scoring import build_verdict, load_hypotheses, render_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--verdict-out", required=True)
    parser.add_argument("--report-out", required=True)
    args = parser.parse_args(argv)
    verdict_path = Path(args.verdict_out)
    report_path = Path(args.report_out)
    if verdict_path.exists() or report_path.exists():
        parser.error("one-shot outputs already exist; refusing to overwrite")
    manifest = load_manifest(args.manifest)
    verdict = build_verdict(manifest, load_hypotheses(manifest, args.responses))
    verdict_path.parent.mkdir(parents=True, exist_ok=False)
    verdict_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "verdict": str(verdict_path), "report": str(report_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
