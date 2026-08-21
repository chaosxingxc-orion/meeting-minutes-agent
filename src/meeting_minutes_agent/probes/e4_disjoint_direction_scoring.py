"""Dialogue-clustered scoring for the E4 disjoint direction pilot."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .contextasr_scoring import normalize_english
from .e4_disjoint_direction import ARMS, DirectionRuntimeBinding, DirectionScoreBinding


def _distance(left: Sequence[str], right: Sequence[str]) -> int:
    import editdistance

    return int(editdistance.eval(list(left), list(right)))


def _contains(text: str, term: str) -> bool:
    return f" {normalize_english(term)} " in f" {normalize_english(text)} "


def _entity_error(hypothesis: str, entity: str) -> int:
    target = normalize_english(entity).split()
    tokens = normalize_english(hypothesis).split()
    width = len(target)
    values: list[int] = []
    for start in range(len(tokens)):
        for size in range(max(1, width - 1), width + 2):
            if start + size <= len(tokens):
                values.append(_distance(target, tokens[start : start + size]))
    return min(values, default=width)


@dataclass(frozen=True)
class DirectionScore:
    target_id: str
    uniq_id: str
    arm: str
    wer_errors: int
    wer_tokens: int
    carry_errors: int
    carry_tokens: int
    carry_hits: int
    carry_total: int
    false_hint_target: int
    completion_tokens: int


def load_scores(
    runtime: DirectionRuntimeBinding,
    score: DirectionScoreBinding,
    responses: str | Path,
) -> tuple[DirectionScore, ...]:
    runtime_ids = {target.target_id for target in runtime.targets}
    score_ids = {target.target_id for target in score.targets}
    if runtime_ids != score_ids:
        raise ValueError("runtime/score target ids differ")
    records: dict[tuple[str, str], dict[str, object]] = {}
    for line in Path(responses).read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("outcome") != "ok":
            continue
        key = (str(record["target_id"]), str(record["arm"]))
        if key in records:
            raise ValueError(f"duplicate response cell: {key}")
        records[key] = record
    expected = {(target_id, arm) for target_id in score_ids for arm in ARMS}
    if set(records) != expected:
        raise ValueError(f"direction read incomplete: missing={len(expected - set(records))}, extra={len(set(records) - expected)}")
    score_by = {target.target_id: target for target in score.targets}
    output: list[DirectionScore] = []
    for target_id, arm in sorted(expected):
        target = score_by[target_id]
        record = records[(target_id, arm)]
        hypothesis = str(record["text"])
        reference = normalize_english(target.reference_text).split()
        hypothesis_tokens = normalize_english(hypothesis).split()
        injected = tuple(str(term) for term in record.get("injected_terms", ()))
        false_target = int(any(_contains(hypothesis, term) and not _contains(target.reference_text, term) for term in injected))
        output.append(
            DirectionScore(
                target_id=target_id,
                uniq_id=target.uniq_id,
                arm=arm,
                wer_errors=_distance(reference, hypothesis_tokens),
                wer_tokens=len(reference),
                carry_errors=sum(_entity_error(hypothesis, entity) for entity in target.carry_entities),
                carry_tokens=sum(len(normalize_english(entity).split()) for entity in target.carry_entities),
                carry_hits=sum(_contains(hypothesis, entity) for entity in target.carry_entities),
                carry_total=len(target.carry_entities),
                false_hint_target=false_target,
                completion_tokens=int(dict(record.get("usage", {})).get("completion_tokens", 0)),
            )
        )
    return tuple(output)


def _components(scores: Sequence[DirectionScore]) -> dict[str, int]:
    return {
        "wer_errors": sum(score.wer_errors for score in scores),
        "wer_tokens": sum(score.wer_tokens for score in scores),
        "carry_errors": sum(score.carry_errors for score in scores),
        "carry_tokens": sum(score.carry_tokens for score in scores),
        "carry_hits": sum(score.carry_hits for score in scores),
        "carry_total": sum(score.carry_total for score in scores),
        "false_hint_targets": sum(score.false_hint_target for score in scores),
        "targets": len(scores),
        "truncated": sum(score.completion_tokens >= 512 for score in scores),
    }


def _metrics(components: Mapping[str, int]) -> dict[str, float | int]:
    return {
        **components,
        "wer": components["wer_errors"] / components["wer_tokens"],
        "carry_ne_wer": components["carry_errors"] / components["carry_tokens"],
        "carry_hit_rate": components["carry_hits"] / components["carry_total"],
        "false_hint_target_rate": components["false_hint_targets"] / components["targets"],
    }


def _cluster_interval(scores: Sequence[DirectionScore], metric: str, level: float) -> dict[str, float]:
    grouped: dict[str, dict[str, list[DirectionScore]]] = defaultdict(lambda: defaultdict(list))
    for score in scores:
        grouped[score.uniq_id][score.arm].append(score)
    dialogue_ids = sorted(grouped)
    rng = random.Random(20260821)
    values: list[float] = []
    for _ in range(20_000):
        sample = [dialogue_ids[rng.randrange(len(dialogue_ids))] for _ in dialogue_ids]
        left: dict[str, int] = defaultdict(int)
        right: dict[str, int] = defaultdict(int)
        for uniq_id in sample:
            for key, value in _components(grouped[uniq_id]["D1-speaker"]).items():
                left[key] += value
            for key, value in _components(grouped[uniq_id]["D0-global"]).items():
                right[key] += value
        values.append(float(_metrics(left)[metric]) - float(_metrics(right)[metric]))
    values.sort()
    alpha = (1.0 - level) / 2.0
    low = values[int(alpha * len(values))]
    high = values[min(len(values) - 1, int((1.0 - alpha) * len(values)))]
    return {"low": low, "high": high}


def build_verdict(
    runtime: DirectionRuntimeBinding,
    score: DirectionScoreBinding,
    scores: Sequence[DirectionScore],
) -> dict[str, object]:
    grouped: dict[str, list[DirectionScore]] = defaultdict(list)
    for item in scores:
        grouped[item.arm].append(item)
    aggregate = {arm: _metrics(_components(grouped[arm])) for arm in ARMS}
    contrasts = {
        "speaker_minus_global_carry_hit_rate": aggregate["D1-speaker"]["carry_hit_rate"] - aggregate["D0-global"]["carry_hit_rate"],
        "speaker_minus_global_carry_ne_wer": aggregate["D1-speaker"]["carry_ne_wer"] - aggregate["D0-global"]["carry_ne_wer"],
        "speaker_minus_global_wer": aggregate["D1-speaker"]["wer"] - aggregate["D0-global"]["wer"],
        "speaker_minus_global_false_hint_target_rate": aggregate["D1-speaker"]["false_hint_target_rate"] - aggregate["D0-global"]["false_hint_target_rate"],
    }
    intervals = {
        name: {
            "ci80": _cluster_interval(scores, metric, 0.80),
            "ci95": _cluster_interval(scores, metric, 0.95),
        }
        for name, metric in (
            ("speaker_minus_global_carry_hit_rate", "carry_hit_rate"),
            ("speaker_minus_global_carry_ne_wer", "carry_ne_wer"),
            ("speaker_minus_global_wer", "wer"),
            ("speaker_minus_global_false_hint_target_rate", "false_hint_target_rate"),
        )
    }
    if aggregate["D0-global"]["truncated"] > 0 or aggregate["D1-speaker"]["truncated"] > 0:
        decision = "EXPLORATORY-INVALID-TRUNCATED"
    elif (
        contrasts["speaker_minus_global_wer"] > 0.01
        or contrasts["speaker_minus_global_false_hint_target_rate"] > 0.02
    ):
        decision = "EXPLORATORY-HARMFUL"
    elif (
        contrasts["speaker_minus_global_carry_hit_rate"] > 0
        and contrasts["speaker_minus_global_carry_ne_wer"] < 0
        and contrasts["speaker_minus_global_wer"] <= 0.01
        and contrasts["speaker_minus_global_false_hint_target_rate"] <= 0.02
    ):
        decision = "EXPLORATORY-SPEAKER-DIRECTION"
    elif (
        contrasts["speaker_minus_global_carry_hit_rate"] <= 0
        and contrasts["speaker_minus_global_carry_ne_wer"] >= 0
    ):
        decision = "EXPLORATORY-NO-GAIN"
    else:
        decision = "EXPLORATORY-MIXED"
    return {
        "schema_version": "e4-disjoint-dir-verdict-v1",
        "experiment_id": "E4-DISJOINT-DIR-v1",
        "runtime_binding_hash": runtime.content_hash,
        "score_binding_hash": score.content_hash,
        "dialogue_clusters": len({item.uniq_id for item in scores}),
        "targets": len(runtime.targets),
        "calls": len(scores),
        "aggregate": aggregate,
        "contrasts": contrasts,
        "cluster_bootstrap": intervals,
        "decision": decision,
        "confirmatory": False,
    }


def render_report(verdict: Mapping[str, object]) -> str:
    aggregate = verdict["aggregate"]
    contrasts = verdict["contrasts"]
    lines = [
        f"decision: {verdict['decision']}",
        "confirmatory: false",
        f"dialogue_clusters: {verdict['dialogue_clusters']}",
        f"targets: {verdict['targets']}",
        f"calls: {verdict['calls']}",
        "",
        "arm\tWER\tcarry_NE-WER\tcarry_hit_rate\tfalse_hint_target_rate\ttruncated",
    ]
    for arm in ARMS:
        values = aggregate[arm]
        lines.append(
            f"{arm}\t{values['wer']:.6f}\t{values['carry_ne_wer']:.6f}\t"
            f"{values['carry_hit_rate']:.6f}\t{values['false_hint_target_rate']:.6f}\t{values['truncated']}"
        )
    lines.extend(["", *(f"{name}: {value:.6f}" for name, value in contrasts.items())])
    return "\n".join(lines) + "\n"


__all__ = ["DirectionScore", "build_verdict", "load_scores", "render_report"]
