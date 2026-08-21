"""One-shot scoring for the E3 legal-state construction audit."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from .state_audit import StateAuditManifest, build_state_views, carry_targets, score_state

STATE_ARMS = (
    "gated-speaker",
    "first-mention-speaker",
    "gated-global",
    "naive-speaker",
    "no-carry-speaker",
    "wrong-speaker",
)


def load_hypotheses(manifest: StateAuditManifest, response_path: str | Path) -> dict[str, dict[int, str]]:
    records: dict[str, dict[int, str]] = defaultdict(dict)
    for line in Path(response_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("outcome") == "ok":
            records[str(record["uniq_id"])][int(record["turn_index"])] = str(record["text"])
    for entry in manifest.entries:
        expected = set(range(len(entry.turns)))
        missing = sorted(expected - records[entry.uniq_id].keys())
        if missing:
            raise ValueError(f"E3 read is incomplete for {entry.uniq_id}: missing turns {missing[:5]}")
    return dict(records)


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def build_verdict(manifest: StateAuditManifest, hypotheses: Mapping[str, Mapping[int, str]]) -> dict[str, object]:
    totals = {arm: defaultdict(int) for arm in STATE_ARMS}
    rows: list[dict[str, object]] = []
    target_turns = 0
    for entry in manifest.entries:
        dialogue_hypotheses = hypotheses[entry.uniq_id]
        for target_index in range(1, len(entry.turns)):
            same = carry_targets(entry, target_index, same_speaker=True)
            global_targets = carry_targets(entry, target_index, same_speaker=False)
            if not same and not global_targets:
                continue
            target_turns += 1
            views = build_state_views(entry, dialogue_hypotheses, target_index)
            for arm in STATE_ARMS:
                score = score_state(entry, target_index, views[arm])
                for key, value in score.items():
                    totals[arm][key] += value
                rows.append(
                    {
                        "uniq_id": entry.uniq_id,
                        "target_index": target_index,
                        "speaker_id": entry.turns[target_index].speaker_id,
                        "arm": arm,
                        "terms": list(views[arm]),
                        **score,
                    }
                )
    aggregate: dict[str, dict[str, float | int | None]] = {}
    for arm in STATE_ARMS:
        values = dict(totals[arm])
        aggregate[arm] = {
            **values,
            "support_precision": _rate(values.get("supported_terms", 0), values.get("terms", 0)),
            "hallucination_rate": _rate(values.get("hallucinated_terms", 0), values.get("terms", 0)),
            "off_speaker_rate": _rate(values.get("off_speaker_terms", 0), values.get("terms", 0)),
            "target_relevance": _rate(values.get("target_relevant_terms", 0), values.get("terms", 0)),
            "same_target_recall": _rate(values.get("same_target_hits", 0), values.get("same_targets", 0)),
            "global_target_recall": _rate(values.get("global_target_hits", 0), values.get("global_targets", 0)),
        }
    gated = aggregate["first-mention-speaker"]
    global_arm = aggregate["gated-global"]
    naive = aggregate["naive-speaker"]
    gated_precision = float(gated["support_precision"] or 0)
    gated_hallucination = float(gated["hallucination_rate"] or 1)
    gated_recall = float(gated["same_target_recall"] or 0)
    gated_off_speaker = float(gated["off_speaker_rate"] or 0)
    global_off_speaker = float(global_arm["off_speaker_rate"] or 0)
    global_recall = float(global_arm["same_target_recall"] or 0)
    routing_off_speaker_gain = global_off_speaker - gated_off_speaker
    routing_recall_loss = global_recall - gated_recall
    if (
        int(gated.get("same_targets", 0)) >= 30
        and gated_precision >= 0.70
        and gated_hallucination <= 0.30
        and gated_recall >= 0.30
        and routing_off_speaker_gain >= 0.10
        and routing_recall_loss <= 0.10
    ):
        decision = "LEGAL-STATE-READY"
    elif float(naive["same_target_recall"] or 0) >= 0.30:
        decision = "STATE-EXTRACTION-BOTTLENECK"
    else:
        decision = "STATE-NOT-RECOVERABLE"
    return {
        "schema_version": "e3-state-audit-verdict-v1",
        "manifest_hash": manifest.content_hash,
        "target_turns": target_turns,
        "aggregate": aggregate,
        "contrasts": {
            "routing_off_speaker_gain": routing_off_speaker_gain,
            "routing_recall_loss": routing_recall_loss,
        },
        "decision": decision,
        "rows": rows,
    }


def render_report(verdict: Mapping[str, object]) -> str:
    lines = [
        f"decision: {verdict['decision']}",
        f"manifest_hash: {verdict['manifest_hash']}",
        f"target_turns: {verdict['target_turns']}",
        "",
        "arm\tterms\tsupport_precision\thallucination\toff_speaker\ttarget_relevance\tsame_recall\tglobal_recall",
    ]
    aggregate = verdict["aggregate"]
    assert isinstance(aggregate, Mapping)
    for arm in STATE_ARMS:
        row = aggregate[arm]
        assert isinstance(row, Mapping)
        fmt = lambda value: "NA" if value is None else f"{float(value):.4f}"  # noqa: E731
        lines.append(
            f"{arm}\t{row.get('terms', 0)}\t{fmt(row.get('support_precision'))}\t"
            f"{fmt(row.get('hallucination_rate'))}\t{fmt(row.get('off_speaker_rate'))}\t"
            f"{fmt(row.get('target_relevance'))}\t{fmt(row.get('same_target_recall'))}\t"
            f"{fmt(row.get('global_target_recall'))}"
        )
    contrasts = verdict["contrasts"]
    assert isinstance(contrasts, Mapping)
    lines.extend(
        [
            "",
            f"routing_off_speaker_gain: {float(contrasts['routing_off_speaker_gain']):.4f}",
            f"routing_recall_loss: {float(contrasts['routing_recall_loss']):.4f}",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["STATE_ARMS", "build_verdict", "load_hypotheses", "render_report"]
