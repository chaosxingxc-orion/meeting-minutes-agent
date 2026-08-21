#!/usr/bin/env python3
"""One-shot frozen read for the registered C-CTX smoke."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.contextasr import load_manifest  # noqa: E402
from meeting_minutes_agent.probes.contextasr_scoring import build_verdict, load_scores  # noqa: E402


def _report(verdict: dict[str, object]) -> str:
    lines = [f"decision: {verdict['decision']}", "", "arm\tWER\tNE-WER\tNE-FNR\tactivated"]
    aggregate = verdict["aggregate"]
    for arm, metrics in aggregate.items():
        lines.append(
            f"{arm}\t{metrics['wer']:.4f}\t{metrics['ne_wer']:.4f}\t"
            f"{metrics['ne_fnr']:.4f}\t{metrics['injected_activated']}/{metrics['injected_total']}"
        )
    lines.extend(["", "contrasts"])
    for name, value in verdict["contrasts"].items():
        lines.append(f"{name}: {value['value']:.4f} CI95=[{value['ci95']['low']:.4f}, {value['ci95']['high']:.4f}]")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--verdict-out", required=True)
    parser.add_argument("--report-out", required=True)
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    scores = load_scores(manifest, args.responses)
    verdict = build_verdict(manifest, scores)
    verdict_path = Path(args.verdict_out)
    report_path = Path(args.report_out)
    verdict_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    verdict_path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_report(verdict), encoding="utf-8")
    print(_report(verdict), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
