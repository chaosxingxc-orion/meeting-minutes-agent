#!/usr/bin/env python3
"""Post-hoc separator-only diagnostic; never changes the registered verdict."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def compact_alnum(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", value.casefold()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdict", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing overwrite")
    source = json.loads(args.verdict.read_text(encoding="utf-8"))
    wrong = [row for row in source["per_group"] if row["category"] == "stable-wrong"]
    separator_equivalent = [
        row for row in wrong
        if compact_alnum(str(row["surface"])) == compact_alnum(str(row["majority_form"]))
    ]
    result = {
        "schema": "earnings22-stable-error-normalization-posthoc-v1",
        "analysis_class": "post-hoc-descriptive-only",
        "registered_decision_unchanged": source["decision"],
        "strict_stable_wrong_groups": len(wrong),
        "separator_only_equivalent_groups": len(separator_equivalent),
        "non_separator_equivalent_groups": len(wrong) - len(separator_equivalent),
        "separator_only_share": len(separator_equivalent) / len(wrong) if wrong else 0.0,
        "limitation": "Rule was added after inspecting strict error forms; it cannot replace or confirm the registered verdict.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
