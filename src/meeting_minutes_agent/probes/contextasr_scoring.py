"""Frozen C-CTX scoring path.

English normalization and entity matching follow ContextASR-Bench evaluation
commit 897de87bd4eb430de28dca807fc725958c7ebc85 (MIT, He Wang 2025).
Only the registered English smoke surface is implemented here.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .contextasr import ARMS, ContextAsrEntry, ContextAsrManifest

_PUNCTUATION = r''',;(){}[]"|:!?.#$%&*+/<=>@\\^_`~"，；､、丶｟｠《》（）｢｣［］｛｝「｣『』【】〔〕！？｡。'''


def merge_single_letters(text: str) -> str:
    current: list[str] = []
    result: list[str] = []
    for word in text.split():
        remaining = word[1:] if len(word) > 1 else ""
        if word and word[0].isalpha() and (remaining == "" or remaining in {"s", "'s"}):
            current.append(word[0])
            if remaining:
                current.append(remaining)
        else:
            if current:
                result.append("".join(current))
                current = []
            result.append(word)
    if current:
        result.append("".join(current))
    return " ".join(result)


def normalize_english(text: str) -> str:
    """ContextASR's English normalization, pinned to the upstream scorer."""

    import contractions

    if text.isupper():
        text = text.lower()
    text = re.sub(r"^(O')\s|\s(O')$|\s(O')\s", " O ", text)
    text = re.sub(r"^(o')\s|\s(o')$|\s(o')\s", " o ", text)
    text = contractions.fix(text, leftovers=False, slang=False)
    text = re.sub("[" + re.escape(_PUNCTUATION) + "]", " ", text)
    text = text.replace("-", " ").replace("'", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return merge_single_letters(text).lower()


def extract_entities(text: str, entities: Sequence[str], limits: Mapping[str, int] | None = None) -> tuple[str, ...]:
    tokens = text.split()
    matches: list[tuple[int, int, str]] = []
    counts: Counter[str] = Counter()
    for index in range(len(tokens)):
        for entity in entities:
            entity_tokens = entity.split()
            if tokens[index : index + len(entity_tokens)] != entity_tokens:
                continue
            if limits is not None and counts[entity] >= limits.get(entity, 0):
                continue
            counts[entity] += 1
            matches.append((index, len(entity_tokens), entity))
    matches.sort(key=lambda value: (value[0], value[1]))
    return tuple(entity for _, _, entity in matches)


def extract_entities_fuzzy(text: str, entities: Sequence[str]) -> tuple[str, ...]:
    import editdistance

    tokens = text.split()
    positions: list[tuple[int, str]] = []
    for entity in entities:
        entity_tokens = entity.split()
        n = len(entity_tokens)
        max_distance = math.ceil(n / 2) - 1
        lengths = [n] + list(range(n - 1, max(1, n - max_distance) - 1, -1)) + list(
            range(n + 1, n + max_distance + 1)
        )
        next_start = 0
        for start in range(len(tokens)):
            if start < next_start:
                continue
            for length in lengths:
                end = start + length
                if end > len(tokens):
                    break
                window = tokens[start:end]
                if editdistance.eval(window, entity_tokens) <= max_distance:
                    next_start = end
                    window_text = " ".join(window)
                    match = re.search(re.escape(entity), window_text)
                    matched = entity if match else window_text
                    if match:
                        next_start -= len(window_text[match.end() :].strip().split())
                    positions.append((start, matched))
                    break
    positions.sort(key=lambda value: (value[0], len(value[1].split())))
    seen: set[tuple[int, str]] = set()
    ordered: list[str] = []
    for value in positions:
        if value not in seen:
            seen.add(value)
            ordered.append(value[1])
    return tuple(ordered)


def _distance(hypothesis: Sequence[str], reference: Sequence[str]) -> int:
    import editdistance

    return int(editdistance.eval(list(hypothesis), list(reference)))


@dataclass(frozen=True)
class SampleScore:
    uniq_id: str
    arm: str
    wer_errors: int
    wer_tokens: int
    ne_errors: int
    ne_tokens: int
    ne_hits: int
    ne_targets: int
    injected_activated: int
    injected_total: int
    completion_tokens: int

    @property
    def wer(self) -> float:
        return self.wer_errors / self.wer_tokens

    @property
    def ne_wer(self) -> float:
        return self.ne_errors / self.ne_tokens

    @property
    def ne_fnr(self) -> float:
        return 1 - self.ne_hits / self.ne_targets


def score_response(entry: ContextAsrEntry, arm: str, text: str, injected_terms: Sequence[str], completion_tokens: int) -> SampleScore:
    reference = normalize_english(entry.reference_text)
    hypothesis = normalize_english(text)
    normalized_entities = tuple(normalize_english(entity) for entity in entry.entity_list)
    reference_entities = extract_entities(reference, normalized_entities)
    limits = Counter(reference_entities)
    exact = extract_entities(hypothesis, normalized_entities, limits)
    fuzzy = extract_entities_fuzzy(hypothesis, normalized_entities)
    ref_entity_tokens = " ".join(reference_entities).split()
    hyp_entity_tokens = " ".join(fuzzy).split()
    normalized_injected = tuple(normalize_english(term) for term in injected_terms)
    activated = extract_entities(hypothesis, normalized_injected) if normalized_injected else ()
    return SampleScore(
        uniq_id=entry.uniq_id,
        arm=arm,
        wer_errors=_distance(hypothesis.split(), reference.split()),
        wer_tokens=len(reference.split()),
        ne_errors=_distance(hyp_entity_tokens, ref_entity_tokens),
        ne_tokens=len(ref_entity_tokens),
        ne_hits=len(exact),
        ne_targets=len(reference_entities),
        injected_activated=len(activated),
        injected_total=len(normalized_injected),
        completion_tokens=completion_tokens,
    )


def load_scores(manifest: ContextAsrManifest, response_path: str | Path) -> tuple[SampleScore, ...]:
    records: dict[tuple[str, str], dict[str, object]] = {}
    for line in Path(response_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("outcome") == "ok":
            records[(str(record["uniq_id"]), str(record["arm"]))] = record
    expected = {(entry.uniq_id, arm) for entry in manifest.entries for arm in ARMS}
    missing = sorted(expected - records.keys())
    if missing:
        raise ValueError(f"C-CTX read is incomplete: {len(missing)} missing cells; first={missing[:3]}")
    by_id = {entry.uniq_id: entry for entry in manifest.entries}
    scores: list[SampleScore] = []
    for uniq_id, arm in sorted(expected):
        record = records[(uniq_id, arm)]
        scores.append(
            score_response(
                by_id[uniq_id],
                arm,
                str(record["text"]),
                tuple(str(x) for x in record.get("injected_terms", ())),
                int(dict(record.get("usage", {})).get("completion_tokens", 0)),
            )
        )
    return tuple(scores)


def _aggregate(scores: Sequence[SampleScore]) -> dict[str, float | int]:
    return {
        "wer": sum(x.wer_errors for x in scores) / sum(x.wer_tokens for x in scores),
        "ne_wer": sum(x.ne_errors for x in scores) / sum(x.ne_tokens for x in scores),
        "ne_fnr": 1 - sum(x.ne_hits for x in scores) / sum(x.ne_targets for x in scores),
        "wer_errors": sum(x.wer_errors for x in scores),
        "wer_tokens": sum(x.wer_tokens for x in scores),
        "ne_errors": sum(x.ne_errors for x in scores),
        "ne_tokens": sum(x.ne_tokens for x in scores),
        "ne_hits": sum(x.ne_hits for x in scores),
        "ne_targets": sum(x.ne_targets for x in scores),
        "injected_activated": sum(x.injected_activated for x in scores),
        "injected_total": sum(x.injected_total for x in scores),
        "truncated": sum(x.completion_tokens >= 1024 for x in scores),
    }


def _bootstrap_delta(by_arm: Mapping[str, Mapping[str, SampleScore]], left: str, right: str, metric: str) -> dict[str, float]:
    ids = sorted(by_arm[left])
    rng = random.Random(20260820)
    deltas: list[float] = []
    for _ in range(10_000):
        sampled = [ids[rng.randrange(len(ids))] for _ in ids]
        left_scores = [by_arm[left][uniq_id] for uniq_id in sampled]
        right_scores = [by_arm[right][uniq_id] for uniq_id in sampled]
        deltas.append(float(_aggregate(left_scores)[metric]) - float(_aggregate(right_scores)[metric]))
    deltas.sort()
    return {"low": deltas[249], "high": deltas[9749]}


def build_verdict(manifest: ContextAsrManifest, scores: Sequence[SampleScore]) -> dict[str, object]:
    grouped: dict[str, list[SampleScore]] = defaultdict(list)
    indexed: dict[str, dict[str, SampleScore]] = defaultdict(dict)
    for score in scores:
        grouped[score.arm].append(score)
        indexed[score.arm][score.uniq_id] = score
    aggregate = {arm: _aggregate(grouped[arm]) for arm in ARMS}
    delta_use = float(aggregate["C2-entity"]["ne_wer"]) - float(aggregate["C0-bare"]["ne_wer"])
    delta_route = float(aggregate["C2-entity"]["ne_wer"]) - float(aggregate["C3-deranged"]["ne_wer"])
    delta_wer = float(aggregate["C2-entity"]["wer"]) - float(aggregate["C0-bare"]["wer"])
    ci_use = _bootstrap_delta(indexed, "C2-entity", "C0-bare", "ne_wer")
    ci_route = _bootstrap_delta(indexed, "C2-entity", "C3-deranged", "ne_wer")
    ci_wer = _bootstrap_delta(indexed, "C2-entity", "C0-bare", "wer")
    if ci_wer["high"] > 0.02 or int(aggregate["C2-entity"]["truncated"]) > 0:
        decision = "CONTEXT-HARMFUL"
    elif delta_use <= -0.05 and delta_route <= -0.05 and ci_use["high"] < 0 and ci_route["high"] < 0:
        decision = "ORACLE-CONTEXT-REACHABLE"
    else:
        activation_changed = any(
            int(aggregate[arm]["injected_activated"]) > 0 for arm in ("C2-entity", "C3-deranged", "C4-corrupt")
        )
        decision = "CONTEXT-SENSITIVE-BUT-UNCONTROLLED" if activation_changed else "CORE-CONTEXT-NOT-REACHABLE"
    return {
        "schema_version": "contextasr-smoke-verdict-v1",
        "manifest_hash": manifest.content_hash,
        "official_metric_commit": "897de87bd4eb430de28dca807fc725958c7ebc85",
        "aggregate": aggregate,
        "contrasts": {
            "delta_use": {"value": delta_use, "ci95": ci_use},
            "delta_route": {"value": delta_route, "ci95": ci_route},
            "delta_wer": {"value": delta_wer, "ci95": ci_wer},
        },
        "decision": decision,
        "sample_scores": [score.__dict__ for score in scores],
    }


__all__ = ["SampleScore", "build_verdict", "extract_entities", "extract_entities_fuzzy", "load_scores", "normalize_english", "score_response"]
