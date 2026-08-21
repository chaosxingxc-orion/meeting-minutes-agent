#!/usr/bin/env python3
"""Freeze the governed QMSum train inputs for E4-XDOMAIN-SUPPLY-AUDIT."""

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
    build_input_manifest,
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
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("manifest output exists; refusing overwrite")
    qmsum = Path(args.qmsum_root)
    if _git_output(qmsum, "rev-parse", "HEAD") != EXPECTED_QMSUM_COMMIT:
        raise SupplyAuditError("QMSum commit mismatch")
    if _git_output(qmsum, "status", "--porcelain"):
        raise SupplyAuditError("QMSum checkout is dirty")
    registry = load_role_registry(args.role_registry)
    if registry.registry_hash != EXPECTED_ROLE_REGISTRY_SHA256:
        raise SupplyAuditError("AMI role registry hash mismatch")
    inputs = select_inputs(qmsum, Path(args.ami_root), Path(args.icsi_root), registry)
    manifest = build_input_manifest(inputs, qmsum)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"inputs": len(inputs), "content_hash": manifest["content_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
