"""Post-hoc scalability audit for runtime-only E4 safety gates."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

from .e4_confirmatory import Pass0RuntimeManifest
from .e4_disjoint_direction import DirectionRuntimeBinding, DirectionScoreBinding
from .e4_disjoint_direction_scoring import DirectionScore
from .e4_mechanism import TargetFeatures, reconstruct_target_features

CANDIDATE_ORDER = (
    "all_terms_repeated",
    "all_terms_recent_le3",
    "inventory_le2",
    "recent_le3_and_inventory_le4",
)


def dialogue_fold(uniq_id: str) -> int:
    digest = hashlib.sha256(f"e4-safety-gate-fold-v1:{uniq_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % 4


def width_bucket(width: int) -> str:
    if width == 1:
        return "1"
    if width <= 4:
        return "2-4"
    return "5-8"


def candidate_accepts(name: str, feature: TargetFeatures) -> bool:
    if name == "all_terms_repeated":
        return feature.all_terms_repeated
    if name == "all_terms_recent_le3":
        return feature.recent_support_le_3
    if name == "inventory_le2":
        return feature.inventory_size <= 2
    if name == "recent_le3_and_inventory_le4":
        return feature.recent_support_le_3 and feature.inventory_size <= 4
    raise ValueError(f"unknown safety-gate candidate: {name}")


def _components(scores: Sequence[DirectionScore]) -> dict[str, int]:
    return {
        "wer_errors": sum(item.wer_errors for item in scores),
        "wer_tokens": sum(item.wer_tokens for item in scores),
        "carry_errors": sum(item.carry_errors for item in scores),
        "carry_tokens": sum(item.carry_tokens for item in scores),
        "carry_hits": sum(item.carry_hits for item in scores),
        "carry_total": sum(item.carry_total for item in scores),
        "false_hint_targets": sum(item.false_hint_target for item in scores),
        "targets": len(scores),
        "truncated": sum(item.completion_tokens >= 512 for item in scores),
    }


def _metrics(scores: Sequence[DirectionScore]) -> dict[str, float | int]:
    value = _components(scores)
    return {
        **value,
        "wer": value["wer_errors"] / value["wer_tokens"],
        "carry_ne_wer": value["carry_errors"] / value["carry_tokens"],
        "carry_hit_rate": value["carry_hits"] / value["carry_total"],
        "false_hint_target_rate": value["false_hint_targets"] / value["targets"],
    }


def evaluate_policy_slice(
    target_ids: Sequence[str],
    accepted: set[str],
    score_by: Mapping[tuple[str, str], DirectionScore],
) -> dict[str, Any]:
    if not target_ids:
        raise ValueError("policy slice cannot be empty")
    baseline = [score_by[(target_id, "D0-global")] for target_id in target_ids]
    policy = [
        score_by[(target_id, "D1-speaker" if target_id in accepted else "D0-global")]
        for target_id in target_ids
    ]
    baseline_metrics = _metrics(baseline)
    policy_metrics = _metrics(policy)
    contrasts = {
        "carry_hit_rate": policy_metrics["carry_hit_rate"] - baseline_metrics["carry_hit_rate"],
        "carry_ne_wer": policy_metrics["carry_ne_wer"] - baseline_metrics["carry_ne_wer"],
        "wer": policy_metrics["wer"] - baseline_metrics["wer"],
        "false_hint_target_rate": policy_metrics["false_hint_target_rate"]
        - baseline_metrics["false_hint_target_rate"],
    }
    return {
        "targets": len(target_ids),
        "selected_targets": sum(target_id in accepted for target_id in target_ids),
        "baseline": baseline_metrics,
        "policy": policy_metrics,
        "contrasts": contrasts,
    }


def _safe(result: Mapping[str, Any]) -> bool:
    value = result["contrasts"]
    return value["wer"] <= 0.01 and value["false_hint_target_rate"] <= 0.02


def _useful(result: Mapping[str, Any]) -> bool:
    value = result["contrasts"]
    return value["carry_hit_rate"] > 0 and value["carry_ne_wer"] < 0


def choose_audit_decision(candidates: Mapping[str, Mapping[str, Any]]) -> tuple[str, str | None]:
    if not any(value["coverage_pass"] for value in candidates.values()):
        return "NO-USABLE-COVERAGE", None
    if not any(value["overall_pass"] for value in candidates.values()):
        return "NO-SAFE-GATE", None
    for name in CANDIDATE_ORDER:
        if candidates[name]["qualifies"]:
            return "WITHIN-SURFACE-STABLE-CANDIDATE", name
    return "SCENARIO-DEPENDENT", None


def build_safety_gate_verdict(
    runtime_manifest: Pass0RuntimeManifest,
    runtime: DirectionRuntimeBinding,
    score: DirectionScoreBinding,
    pass0_records: Iterable[Mapping[str, Any]],
    scores: Sequence[DirectionScore],
    official_verdict: Mapping[str, Any],
) -> dict[str, Any]:
    if official_verdict.get("decision") != "EXPLORATORY-HARMFUL":
        raise ValueError("unexpected official E4-DISJOINT-DIR verdict")
    if official_verdict.get("runtime_binding_hash") != runtime.content_hash:
        raise ValueError("official/runtime binding hash mismatch")
    if official_verdict.get("score_binding_hash") != score.content_hash:
        raise ValueError("official/score binding hash mismatch")
    features = reconstruct_target_features(runtime_manifest, runtime, pass0_records)
    target_ids = tuple(sorted(features))
    if set(target_ids) != {target.target_id for target in runtime.targets}:
        raise ValueError("runtime feature target set mismatch")
    score_by = {(item.target_id, item.arm): item for item in scores}
    expected = {(target_id, arm) for target_id in target_ids for arm in ("D0-global", "D1-speaker")}
    if set(score_by) != expected:
        raise ValueError("direction score cell set mismatch")
    target_by = {target.target_id: target for target in runtime.targets}
    density = Counter(target.uniq_id for target in runtime.targets)

    candidate_results: dict[str, dict[str, Any]] = {}
    for name in CANDIDATE_ORDER:
        accepted = {target_id for target_id in target_ids if candidate_accepts(name, features[target_id])}
        overall = evaluate_policy_slice(target_ids, accepted, score_by)
        selected_dialogues = len({target_by[target_id].uniq_id for target_id in accepted})
        coverage_pass = len(accepted) / len(target_ids) >= 0.25 and selected_dialogues >= 20
        overall_pass = coverage_pass and _safe(overall) and _useful(overall)

        folds: dict[str, dict[str, Any]] = {}
        for fold in range(4):
            subset = tuple(
                target_id
                for target_id in target_ids
                if dialogue_fold(target_by[target_id].uniq_id) == fold
            )
            result = evaluate_policy_slice(subset, accepted, score_by)
            result["safe"] = _safe(result)
            result["useful"] = _useful(result)
            folds[str(fold)] = result
        fold_pass = (
            all(value["selected_targets"] >= 3 and value["safe"] for value in folds.values())
            and sum(value["useful"] for value in folds.values()) >= 3
        )

        widths: dict[str, dict[str, Any]] = {}
        for bucket in ("1", "2-4", "5-8"):
            subset = tuple(
                target_id
                for target_id in target_ids
                if width_bucket(features[target_id].inventory_size) == bucket
            )
            result = evaluate_policy_slice(subset, accepted, score_by)
            result["eligible"] = result["selected_targets"] >= 8
            result["safe"] = _safe(result)
            result["useful"] = _useful(result)
            widths[bucket] = result
        eligible_widths = [value for value in widths.values() if value["eligible"]]
        width_pass = (
            len(eligible_widths) >= 2
            and all(value["safe"] for value in eligible_widths)
            and sum(value["useful"] for value in eligible_widths) >= 2
        )

        densities: dict[str, dict[str, Any]] = {}
        for label, multiple in (("one-target-dialogue", False), ("multi-target-dialogue", True)):
            subset = tuple(
                target_id
                for target_id in target_ids
                if (density[target_by[target_id].uniq_id] >= 2) == multiple
            )
            densities[label] = evaluate_policy_slice(subset, accepted, score_by)

        candidate_results[name] = {
            "accepted_targets": len(accepted),
            "selected_dialogues": selected_dialogues,
            "coverage": len(accepted) / len(target_ids),
            "coverage_pass": coverage_pass,
            "overall_pass": overall_pass,
            "fold_pass": fold_pass,
            "width_pass": width_pass,
            "qualifies": overall_pass and fold_pass and width_pass,
            "overall": overall,
            "dialogue_folds": folds,
            "width_strata": widths,
            "target_density_strata": densities,
        }

    decision, selected = choose_audit_decision(candidate_results)
    return {
        "schema_version": "e4-safety-gate-audit-v1",
        "analysis_class": "post-hoc-exploratory-zero-model",
        "parent_decision": official_verdict["decision"],
        "parent_decision_unchanged": True,
        "runtime_binding_hash": runtime.content_hash,
        "score_binding_hash": score.content_hash,
        "targets": len(target_ids),
        "dialogues": len({target.uniq_id for target in runtime.targets}),
        "candidate_order": list(CANDIDATE_ORDER),
        "runtime_feature_distribution": {
            "inventory_width": dict(sorted(Counter(feature.inventory_size for feature in features.values()).items())),
            "dialogue_fold": dict(sorted(Counter(dialogue_fold(target.uniq_id) for target in runtime.targets).items())),
        },
        "candidates": candidate_results,
        "decision": decision,
        "selected_candidate": selected,
        "cross_domain_scalability": "not_identified",
        "limitations": [
            "Post-hoc exploratory reuse of a single ContextASR movie-dialogue surface.",
            "Fold and width checks measure internal stability, not transport to meetings or another domain.",
            "No result authorizes model contact, a confirmatory claim, or an agent loop.",
        ],
    }


def render_safety_gate_report(verdict: Mapping[str, Any]) -> str:
    lines = [
        f"decision: {verdict['decision']}",
        f"selected_candidate: {verdict['selected_candidate'] or 'none'}",
        f"cross_domain_scalability: {verdict['cross_domain_scalability']}",
        f"targets: {verdict['targets']}",
        f"dialogues: {verdict['dialogues']}",
        "",
        "candidate\tcoverage\tdialogues\thit_delta\tNE-WER_delta\tWER_delta\tfalse_hint_delta\toverall\tfolds\twidths\tqualifies",
    ]
    for name in CANDIDATE_ORDER:
        candidate = verdict["candidates"][name]
        contrast = candidate["overall"]["contrasts"]
        lines.append(
            f"{name}\t{candidate['coverage']:.4f}\t{candidate['selected_dialogues']}\t"
            f"{contrast['carry_hit_rate']:.4f}\t{contrast['carry_ne_wer']:.4f}\t"
            f"{contrast['wer']:.4f}\t{contrast['false_hint_target_rate']:.4f}\t"
            f"{str(candidate['overall_pass']).lower()}\t{str(candidate['fold_pass']).lower()}\t"
            f"{str(candidate['width_pass']).lower()}\t{str(candidate['qualifies']).lower()}"
        )
    lines.extend([
        "",
        "This is a post-hoc zero-model audit. Cross-domain scalability is not identified.",
    ])
    return "\n".join(lines) + "\n"


__all__ = [
    "CANDIDATE_ORDER",
    "build_safety_gate_verdict",
    "candidate_accepts",
    "choose_audit_decision",
    "dialogue_fold",
    "evaluate_policy_slice",
    "render_safety_gate_report",
    "width_bucket",
]
