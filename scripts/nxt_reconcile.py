#!/usr/bin/env python3
"""Reconcile discovered NXT layer counts against the 2026-08-17 local AMI
audit, and (optionally) resolve every eligible meeting end to end to report
orphan-pointer counts across the whole corpus.

Reads annotation XML from disk only -- no model or network contact.

Usage::

    python scripts/nxt_reconcile.py --root <ami annotations root>
    python scripts/nxt_reconcile.py --root <ami annotations root> --resolve-all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus, layer_counts  # noqa: E402
from meeting_minutes_agent.corpora.nxt.resolver import MeetingResolver  # noqa: E402

AUDIT_2026_08_17 = {
    "words_and_segments": 171,
    "abstractive": 142,
    "extractive_and_summlink": 137,
    # The audit's "139 topics/dialogue acts" is the individual per-layer
    # count for BOTH topics and dialogue_acts (each independently 139 on
    # the real AMI release) -- not their intersection. See
    # NxtCorpus.layer_counts's docstring: topics and dialogue-acts cover
    # different 139-meeting sets (3 meetings differ each way), so the AND
    # (topics_and_dialogue_acts) is 136, not 139.
    "topics": 139,
    "dialogue_acts": 139,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="AMI NXT annotations root")
    parser.add_argument(
        "--resolve-all",
        action="store_true",
        help="resolve every meeting with a words+segments layer end to end and report orphan pointers",
    )
    parser.add_argument(
        "--orphan-examples",
        type=int,
        default=20,
        help="max number of orphan-pointer examples to include in the report (default 20)",
    )
    args = parser.parse_args(argv)

    corpus = NxtCorpus(Path(args.root))
    meetings = corpus.discover_meetings()
    counts = layer_counts(meetings)

    report: dict[str, object] = {
        "root": str(corpus.root),
        "discovered_meeting_count": len(meetings),
        "counts": counts,
        "audit_2026_08_17": AUDIT_2026_08_17,
        "reconciled": {k: counts[k] == AUDIT_2026_08_17[k] for k in AUDIT_2026_08_17},
    }

    if args.resolve_all:
        resolved = 0
        total_orphans = 0
        meetings_with_orphans = 0
        transcript_utterances = 0
        evidence_links = 0
        orphan_examples: list[dict[str, str]] = []

        for meeting_id, layers in sorted(meetings.items()):
            if not (layers.has_words and layers.has_segments):
                continue
            result = MeetingResolver(corpus, meeting_id).resolve()
            resolved += 1
            transcript_utterances += len(result.transcript)
            evidence_links += len(result.evidence_links)
            if result.orphans:
                meetings_with_orphans += 1
                total_orphans += len(result.orphans)
                for o in result.orphans:
                    if len(orphan_examples) < args.orphan_examples:
                        orphan_examples.append(
                            {
                                "meeting_id": meeting_id,
                                "source_file": o.source_file,
                                "source_id": o.source_id,
                                "target_href": o.target_href,
                                "reason": o.reason,
                            }
                        )

        report["resolve_all"] = {
            "resolved_meetings": resolved,
            "total_transcript_utterances": transcript_utterances,
            "total_evidence_links": evidence_links,
            "meetings_with_orphans": meetings_with_orphans,
            "total_orphan_pointers": total_orphans,
            "orphan_examples": orphan_examples,
        }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
