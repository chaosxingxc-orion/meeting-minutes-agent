#!/usr/bin/env python3
"""Run the sole aggregate read for E4-XDOMAIN-SUPPLY-AUDIT."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.corpora.roles import load_role_registry  # noqa: E402
from meeting_minutes_agent.probes.e4_xdomain_supply import (  # noqa: E402
    EXPECTED_QMSUM_COMMIT,
    EXPECTED_ROLE_REGISTRY_SHA256,
    SupplyAuditError,
    assert_manifest_matches,
    build_input_manifest,
    build_verdict,
    render_report,
    select_inputs,
)


def _git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmsum-root", required=True)
    parser.add_argument("--ami-root", required=True)
    parser.add_argument("--icsi-root", required=True)
    parser.add_argument("--role-registry", default=str(ROOT / "configs/corpora/ami-role-registry.json"))
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output_dir)
    if output.exists():
        parser.error("audit output directory exists; refusing overwrite")
    qmsum = Path(args.qmsum_root)
    registry = load_role_registry(args.role_registry)
    if _git_output(qmsum, "rev-parse", "HEAD") != EXPECTED_QMSUM_COMMIT:
        raise SupplyAuditError("QMSum commit mismatch")
    if _git_output(qmsum, "status", "--porcelain"):
        raise SupplyAuditError("QMSum checkout is dirty")
    if registry.registry_hash != EXPECTED_ROLE_REGISTRY_SHA256:
        raise SupplyAuditError("AMI role registry hash mismatch")
    inputs = select_inputs(qmsum, Path(args.ami_root), Path(args.icsi_root), registry)
    expected = json.loads(Path(args.input_manifest).read_text(encoding="utf-8"))
    actual = build_input_manifest(inputs, qmsum)
    assert_manifest_matches(expected, actual)
    verdict = build_verdict(inputs, actual)
    output.mkdir(parents=True, exist_ok=False)
    (output / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.txt").write_text(render_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "model_calls": 0}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SupplyAuditError as exc:
        print(f"INVALID-AUDIT: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
