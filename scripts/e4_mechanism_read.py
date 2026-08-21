#!/usr/bin/env python3
"""Run the single frozen, zero-model E4-CF mechanism read."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.probes.e4_confirmatory import (  # noqa: E402
    load_pass0_runtime,
    load_runtime_binding,
    load_score_binding,
)
from meeting_minutes_agent.probes.e4_mechanism import (  # noqa: E402
    build_mechanism_verdict,
    load_jsonl,
    render_mechanism_report,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", required=True)
    parser.add_argument("--runtime-binding", required=True)
    parser.add_argument("--score-binding", required=True)
    parser.add_argument("--pass0-responses", required=True)
    parser.add_argument("--secondpass-responses", required=True)
    parser.add_argument("--official-verdict", required=True)
    parser.add_argument("--verdict-out", required=True)
    parser.add_argument("--report-out", required=True)
    args = parser.parse_args(argv)

    inputs = {name: Path(getattr(args, name)) for name in (
        "runtime_manifest",
        "runtime_binding",
        "score_binding",
        "pass0_responses",
        "secondpass_responses",
        "official_verdict",
    )}
    verdict_out = Path(args.verdict_out)
    report_out = Path(args.report_out)
    if verdict_out.exists() or report_out.exists() or verdict_out.parent.exists() or report_out.parent.exists():
        raise FileExistsError("mechanism read output exists; refusing to overwrite")

    verdict = build_mechanism_verdict(
        load_pass0_runtime(inputs["runtime_manifest"]),
        load_runtime_binding(inputs["runtime_binding"]),
        load_score_binding(inputs["score_binding"]),
        load_jsonl(inputs["pass0_responses"]),
        load_jsonl(inputs["secondpass_responses"]),
        json.loads(inputs["official_verdict"].read_text(encoding="utf-8")),
    )
    verdict["input_sha256"] = {name: _sha256(path) for name, path in inputs.items()}
    verdict_out.parent.mkdir(parents=True, exist_ok=False)
    verdict_out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_out.write_text(render_mechanism_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "selected_predicate": verdict["selected_predicate"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
