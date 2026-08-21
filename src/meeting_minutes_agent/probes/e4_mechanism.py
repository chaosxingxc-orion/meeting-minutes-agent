"""Post-hoc, zero-model mechanism audit for the frozen E4-CF flight."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import editdistance

from ..glossary.arms import gated_arm
from ..glossary.gate import GateConfig
from .contextasr_scoring import normalize_english
from .e4_confirmatory import (
    ARMS,
    Pass0RuntimeManifest,
    RuntimeBinding,
    RuntimeTarget,
    ScoreBinding,
)

SEMANTIC_ARMS = ("CF1-global", "CF2-speaker", "CF3-wrong")
CANDIDATE_ORDER = (
    "all_terms_repeated",
    "recent_support_le_3",
    "inventory_le_4",
    "speaker_wrong_disjoint",
)


def load_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines())


def _contains(text: str, term: str) -> bool:
    return f" {normalize_english(term)} " in f" {normalize_english(text)} "


def _word_error(reference: str, hypothesis: str) -> tuple[int, int]:
    ref = normalize_english(reference).split()
    hyp = normalize_english(hypothesis).split()
    return int(editdistance.eval(ref, hyp)), len(ref)


def _bucket_evidence(value: int) -> str:
    return "1" if value == 1 else "2" if value == 2 else "3+"


def _bucket_gap(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    return "6+"


def classify_transition(bare_hit: bool, arm_hit: bool) -> str:
    if not bare_hit and arm_hit:
        return "repair"
    if bare_hit and not arm_hit:
        return "break"
    return "retained" if bare_hit else "missed"


def classify_false_association(net_carry_gain: int, wer_delta: int) -> str:
    gain = "net-carry-gain" if net_carry_gain > 0 else "no-net-carry-gain"
    harm = "wer-harm" if wer_delta > 0 else "no-wer-harm"
    return f"{gain}/{harm}"


@dataclass(frozen=True)
class TermFeature:
    evidence_count: int
    support_turn_count: int
    last_mention_gap: int | None


@dataclass(frozen=True)
class TargetFeatures:
    inventory_size: int
    all_terms_repeated: bool
    recent_support_le_3: bool
    inventory_le_4: bool
    speaker_wrong_disjoint: bool
    by_arm: Mapping[str, tuple[TermFeature, ...]]


@dataclass(frozen=True)
class ArmObservation:
    wer_errors: int
    wer_tokens: int
    carry_hits: tuple[bool, ...]
    false_hint_ranks: tuple[int, ...]


def _ok_records(records: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], Mapping[str, Any]]:
    out: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for record in records:
        if record.get("outcome") != "ok":
            continue
        key = tuple(record[name] for name in keys)
        if key in out:
            raise ValueError(f"duplicate response key: {key}")
        out[key] = record
    return out


def _history_terms(
    target: RuntimeTarget,
    turns: Sequence[Any],
    hypotheses: Mapping[int, str],
    arm: str,
) -> tuple[tuple[str, ...], tuple[TermFeature, ...]]:
    prior = tuple(turn for turn in turns if turn.index < target.turn_index)
    if arm == "CF2-speaker":
        history = tuple(turn for turn in prior if turn.speaker_id == target.speaker_id)
    elif arm == "CF3-wrong":
        history = tuple(turn for turn in prior if turn.speaker_id != target.speaker_id)
    elif arm == "CF1-global":
        history = prior
    else:
        raise ValueError(f"unsupported history arm: {arm}")
    text = " ".join(hypotheses[turn.index] for turn in history)
    entries = gated_arm(
        text,
        chunk_index=0,
        gate_config=GateConfig(min_evidence=1, inventory_cap=8),
    ).entries
    width = len(target.speaker_terms)
    selected = tuple(entries[:width])
    terms = tuple(entry.canonical_surface for entry in selected)
    features: list[TermFeature] = []
    for entry in selected:
        supporting = tuple(turn.index for turn in history if _contains(hypotheses[turn.index], entry.canonical_surface))
        gap = target.turn_index - max(supporting) if supporting else None
        features.append(TermFeature(entry.evidence_count, len(supporting), gap))
    return terms, tuple(features)


def reconstruct_target_features(
    runtime_manifest: Pass0RuntimeManifest,
    runtime_binding: RuntimeBinding,
    pass0_records: Iterable[Mapping[str, Any]],
) -> dict[str, TargetFeatures]:
    dialogues = {entry.uniq_id: entry for entry in runtime_manifest.entries}
    records = _ok_records(pass0_records, ("uniq_id", "turn_index"))
    hypotheses: dict[str, dict[int, str]] = {}
    for (uniq_id, turn_index), record in records.items():
        hypotheses.setdefault(str(uniq_id), {})[int(turn_index)] = str(record["text"])
    out: dict[str, TargetFeatures] = {}
    for target in runtime_binding.targets:
        dialogue = dialogues[target.uniq_id]
        hyp = hypotheses[target.uniq_id]
        by_arm: dict[str, tuple[TermFeature, ...]] = {}
        frozen = {
            "CF1-global": target.global_terms,
            "CF2-speaker": target.speaker_terms,
            "CF3-wrong": target.wrong_terms,
        }
        for arm in SEMANTIC_ARMS:
            terms, features = _history_terms(target, dialogue.turns, hyp, arm)
            if terms != frozen[arm]:
                raise ValueError(f"reconstructed state mismatch at {target.target_id}/{arm}")
            by_arm[arm] = features
        speaker = by_arm["CF2-speaker"]
        speaker_norm = {normalize_english(term) for term in target.speaker_terms}
        wrong_norm = {normalize_english(term) for term in target.wrong_terms}
        out[target.target_id] = TargetFeatures(
            inventory_size=len(target.speaker_terms),
            all_terms_repeated=all(item.evidence_count >= 2 for item in speaker),
            recent_support_le_3=all(item.last_mention_gap is not None and item.last_mention_gap <= 3 for item in speaker),
            inventory_le_4=len(target.speaker_terms) <= 4,
            speaker_wrong_disjoint=not bool(speaker_norm & wrong_norm),
            by_arm=by_arm,
        )
    return out


def _observations(
    runtime_binding: RuntimeBinding,
    score_binding: ScoreBinding,
    records: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, ArmObservation]]:
    response_by = _ok_records(records, ("target_id", "arm"))
    runtime_by = {target.target_id: target for target in runtime_binding.targets}
    out: dict[str, dict[str, ArmObservation]] = {}
    for score_target in score_binding.targets:
        runtime_target = runtime_by[score_target.target_id]
        arm_out: dict[str, ArmObservation] = {}
        frozen_terms = {
            "CF0-bare": (),
            "CF1-global": runtime_target.global_terms,
            "CF2-speaker": runtime_target.speaker_terms,
            "CF3-wrong": runtime_target.wrong_terms,
        }
        for arm in ARMS:
            record = response_by[(score_target.target_id, arm)]
            injected = tuple(str(term) for term in record.get("injected_terms", ()))
            if injected != frozen_terms[arm]:
                raise ValueError(f"injected terms mismatch at {score_target.target_id}/{arm}")
            hypothesis = str(record["text"])
            errors, tokens = _word_error(score_target.reference_text, hypothesis)
            hits = tuple(_contains(hypothesis, entity) for entity in score_target.carry_entities)
            false_ranks = tuple(
                rank
                for rank, term in enumerate(injected, start=1)
                if _contains(hypothesis, term) and not _contains(score_target.reference_text, term)
            )
            arm_out[arm] = ArmObservation(errors, tokens, hits, false_ranks)
        out[score_target.target_id] = arm_out
    return out


def _subset_metrics(
    target_ids: Sequence[str],
    uniq_by_target: Mapping[str, str],
    observations: Mapping[str, Mapping[str, ArmObservation]],
) -> dict[str, Any]:
    totals: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    for target_id in target_ids:
        for arm in ARMS:
            obs = observations[target_id][arm]
            totals[arm].update(
                wer_errors=obs.wer_errors,
                wer_tokens=obs.wer_tokens,
                carry_hits=sum(obs.carry_hits),
                carry_total=len(obs.carry_hits),
                false_hint_targets=bool(obs.false_hint_ranks),
                false_hint_activations=len(obs.false_hint_ranks),
            )
    metrics: dict[str, dict[str, float | int]] = {}
    for arm in ARMS:
        value = totals[arm]
        metrics[arm] = {
            **value,
            "wer": value["wer_errors"] / value["wer_tokens"],
            "carry_hit_rate": value["carry_hits"] / value["carry_total"],
            "false_hint_target_rate": value["false_hint_targets"] / len(target_ids),
        }
    contrasts = {
        "speaker_global_carry_hit_rate": metrics["CF2-speaker"]["carry_hit_rate"] - metrics["CF1-global"]["carry_hit_rate"],
        "speaker_wrong_carry_hit_rate": metrics["CF2-speaker"]["carry_hit_rate"] - metrics["CF3-wrong"]["carry_hit_rate"],
        "speaker_global_wer": metrics["CF2-speaker"]["wer"] - metrics["CF1-global"]["wer"],
        "speaker_bare_wer": metrics["CF2-speaker"]["wer"] - metrics["CF0-bare"]["wer"],
        "speaker_global_false_hint_target_rate": metrics["CF2-speaker"]["false_hint_target_rate"] - metrics["CF1-global"]["false_hint_target_rate"],
    }
    return {
        "targets": len(target_ids),
        "dialogues": len({uniq_by_target[target_id] for target_id in target_ids}),
        "arms": metrics,
        "contrasts": contrasts,
    }


def choose_decision(overall: Mapping[str, Any], candidates: Mapping[str, Mapping[str, Any]]) -> tuple[str, str | None]:
    contrasts = overall["contrasts"]
    safety = contrasts["speaker_bare_wer"] > 0.01 or (
        contrasts["speaker_global_false_hint_target_rate"] >= 0.05
        and contrasts["speaker_global_carry_hit_rate"] <= 0
    )
    if safety:
        return "SAFETY-RISK-DOMINATES", None
    for name in CANDIDATE_ORDER:
        if candidates[name]["qualifies"]:
            return "PREREGISTER-ONE-FIXED-POLICY", name
    return "NO-ACTIONABLE-MECHANISM", None


def build_mechanism_verdict(
    runtime_manifest: Pass0RuntimeManifest,
    runtime_binding: RuntimeBinding,
    score_binding: ScoreBinding,
    pass0_records: Iterable[Mapping[str, Any]],
    secondpass_records: Iterable[Mapping[str, Any]],
    official_verdict: Mapping[str, Any],
) -> dict[str, Any]:
    if official_verdict.get("decision") != "DIRECTIONAL-NOT-CONFIRMED":
        raise ValueError("unexpected official E4-CF verdict")
    if official_verdict.get("runtime_binding_hash") != runtime_binding.content_hash:
        raise ValueError("official/runtime binding hash mismatch")
    if official_verdict.get("score_binding_hash") != score_binding.content_hash:
        raise ValueError("official/score binding hash mismatch")
    features = reconstruct_target_features(runtime_manifest, runtime_binding, pass0_records)
    observations = _observations(runtime_binding, score_binding, secondpass_records)
    runtime_by = {target.target_id: target for target in runtime_binding.targets}
    target_ids = tuple(sorted(observations))
    uniq_by_target = {target_id: runtime_by[target_id].uniq_id for target_id in target_ids}
    overall = _subset_metrics(target_ids, uniq_by_target, observations)

    transitions = {arm: Counter() for arm in SEMANTIC_ARMS}
    pairwise = {
        "speaker_vs_global": Counter(),
        "speaker_vs_wrong": Counter(),
    }
    false_association = {arm: Counter() for arm in SEMANTIC_ARMS}
    false_rank = {arm: Counter() for arm in SEMANTIC_ARMS}
    false_feature = {
        arm: {"evidence": Counter(), "gap": Counter()} for arm in SEMANTIC_ARMS
    }
    inventory_distribution: Counter[int] = Counter()

    for target_id in target_ids:
        target_obs = observations[target_id]
        bare = target_obs["CF0-bare"]
        inventory_distribution[features[target_id].inventory_size] += 1
        for arm in SEMANTIC_ARMS:
            obs = target_obs[arm]
            for bare_hit, arm_hit in zip(bare.carry_hits, obs.carry_hits, strict=True):
                transitions[arm][classify_transition(bare_hit, arm_hit)] += 1
            net_gain = sum(obs.carry_hits) - sum(bare.carry_hits)
            association = classify_false_association(net_gain, obs.wer_errors - bare.wer_errors)
            false_association[arm][association] += len(obs.false_hint_ranks)
            term_features = features[target_id].by_arm[arm]
            for rank in obs.false_hint_ranks:
                false_rank[arm][str(rank)] += 1
                term = term_features[rank - 1]
                false_feature[arm]["evidence"][_bucket_evidence(term.evidence_count)] += 1
                false_feature[arm]["gap"][_bucket_gap(term.last_mention_gap)] += 1
        for name, other_arm in (("speaker_vs_global", "CF1-global"), ("speaker_vs_wrong", "CF3-wrong")):
            for speaker_hit, other_hit in zip(
                target_obs["CF2-speaker"].carry_hits,
                target_obs[other_arm].carry_hits,
                strict=True,
            ):
                key = "both" if speaker_hit and other_hit else "speaker_only" if speaker_hit else "other_only" if other_hit else "neither"
                pairwise[name][key] += 1

    candidate_results: dict[str, dict[str, Any]] = {}
    for name in CANDIDATE_ORDER:
        subset = tuple(target_id for target_id in target_ids if getattr(features[target_id], name))
        metrics = _subset_metrics(subset, uniq_by_target, observations) if subset else None
        qualifies = bool(
            metrics
            and metrics["targets"] >= 100
            and metrics["dialogues"] >= 50
            and metrics["contrasts"]["speaker_global_carry_hit_rate"] >= 0.03
            and metrics["contrasts"]["speaker_wrong_carry_hit_rate"] >= 0.03
            and metrics["contrasts"]["speaker_global_wer"] <= 0
            and metrics["contrasts"]["speaker_global_false_hint_target_rate"] <= 0.01
        )
        candidate_results[name] = {"qualifies": qualifies, "metrics": metrics}

    decision, selected = choose_decision(overall, candidate_results)
    return {
        "schema_version": "e4-cf-mechanism-v1",
        "analysis_class": "post-hoc-exploratory-zero-model",
        "official_e4_cf_decision": official_verdict["decision"],
        "official_decision_unchanged": True,
        "runtime_manifest_hash": runtime_manifest.content_hash,
        "runtime_binding_hash": runtime_binding.content_hash,
        "score_binding_hash": score_binding.content_hash,
        "overall": overall,
        "carry_transitions_vs_bare": {arm: dict(transitions[arm]) for arm in SEMANTIC_ARMS},
        "pairwise_carry_hits": {name: dict(value) for name, value in pairwise.items()},
        "false_hint": {
            arm: {
                "activations": overall["arms"][arm]["false_hint_activations"],
                "targets": overall["arms"][arm]["false_hint_targets"],
                "target_rate": overall["arms"][arm]["false_hint_target_rate"],
                "association_with_bare_outcome": dict(false_association[arm]),
                "rank": dict(false_rank[arm]),
                "evidence_bucket": dict(false_feature[arm]["evidence"]),
                "last_mention_gap_bucket": dict(false_feature[arm]["gap"]),
            }
            for arm in SEMANTIC_ARMS
        },
        "runtime_feature_distribution": {
            "inventory_size": {str(key): value for key, value in sorted(inventory_distribution.items())},
            **{name: sum(getattr(features[target_id], name) for target_id in target_ids) for name in CANDIDATE_ORDER},
        },
        "candidate_predicates": candidate_results,
        "decision": decision,
        "selected_predicate": selected,
        "limitations": [
            "Post-hoc exploratory analysis; no confirmatory p-values or confidence claims.",
            "False-hint strata are descriptive associations, not causal effects.",
            "A selected predicate would require an independent preregistered replay and new authorization.",
        ],
    }


def render_mechanism_report(verdict: Mapping[str, Any]) -> str:
    overall = verdict["overall"]
    lines = [
        f"decision: {verdict['decision']}",
        f"selected_predicate: {verdict['selected_predicate'] or 'none'}",
        f"official_e4_cf_decision_unchanged: {str(verdict['official_decision_unchanged']).lower()}",
        f"targets: {overall['targets']}",
        f"dialogues: {overall['dialogues']}",
        "",
        "arm\trepairs\tbreaks\tretained\tmissed\tfalse_hint_activations\tfalse_hint_targets",
    ]
    for arm in SEMANTIC_ARMS:
        transitions = verdict["carry_transitions_vs_bare"][arm]
        false_hint = verdict["false_hint"][arm]
        lines.append(
            f"{arm}\t{transitions.get('repair', 0)}\t{transitions.get('break', 0)}\t"
            f"{transitions.get('retained', 0)}\t{transitions.get('missed', 0)}\t"
            f"{false_hint['activations']}\t{false_hint['targets']}"
        )
    lines.extend(["", "candidate\ttargets\tdialogues\tspk-global-hit\tspk-wrong-hit\tspk-global-WER\tspk-global-false-target\tqualifies"])
    for name in CANDIDATE_ORDER:
        candidate = verdict["candidate_predicates"][name]
        metrics = candidate["metrics"]
        if metrics is None:
            lines.append(f"{name}\t0\t0\tNA\tNA\tNA\tNA\tfalse")
            continue
        contrast = metrics["contrasts"]
        lines.append(
            f"{name}\t{metrics['targets']}\t{metrics['dialogues']}\t"
            f"{contrast['speaker_global_carry_hit_rate']:.4f}\t"
            f"{contrast['speaker_wrong_carry_hit_rate']:.4f}\t"
            f"{contrast['speaker_global_wer']:.4f}\t"
            f"{contrast['speaker_global_false_hint_target_rate']:.4f}\t"
            f"{str(candidate['qualifies']).lower()}"
        )
    lines.extend(["", "This is a post-hoc exploratory, zero-model audit. It does not replace the official E4-CF verdict."])
    return "\n".join(lines) + "\n"


__all__ = [
    "CANDIDATE_ORDER",
    "SEMANTIC_ARMS",
    "build_mechanism_verdict",
    "choose_decision",
    "classify_false_association",
    "classify_transition",
    "load_jsonl",
    "reconstruct_target_features",
    "render_mechanism_report",
]
