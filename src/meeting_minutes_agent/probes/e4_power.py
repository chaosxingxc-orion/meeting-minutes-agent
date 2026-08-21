"""Zero-model power planning for an independent E4 confirmatory surface."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .state_audit import contains_entity


@dataclass(frozen=True)
class DialoguePowerStats:
    uniq_id: str
    turns: int
    duration: float
    carry_mentions: int
    target_turns: int
    target_seconds: float


def dialogue_stats(record: Mapping[str, object]) -> DialoguePowerStats:
    turns = list(record["dialogue"])
    entities = tuple(str(x) for x in record["entity_list"])
    carry_mentions = 0
    target_turns = 0
    target_seconds = 0.0
    for index, target in enumerate(turns):
        hits = 0
        for entity in entities:
            if not contains_entity(str(target["text"]), entity):
                continue
            if any(
                prior["role"] == target["role"] and contains_entity(str(prior["text"]), entity)
                for prior in turns[:index]
            ):
                hits += 1
        if hits:
            carry_mentions += hits
            target_turns += 1
            target_seconds += float(target["end"]) - float(target["start"])
    return DialoguePowerStats(
        uniq_id=str(record["uniq_id"]),
        turns=len(turns),
        duration=float(record["duration"]),
        carry_mentions=carry_mentions,
        target_turns=target_turns,
        target_seconds=target_seconds,
    )


def required_paired_mentions(
    *,
    mde: float,
    discordance_rate: float,
    design_effect: float,
    z_alpha: float = 1.959963984540054,
    z_power: float = 0.8416212335729143,
) -> int:
    """Normal-approximation requirement for a paired binary contrast."""

    if not 0 < mde < 1:
        raise ValueError("mde must lie in (0, 1)")
    if not 0 < discordance_rate <= 1:
        raise ValueError("discordance_rate must lie in (0, 1]")
    if design_effect < 1:
        raise ValueError("design_effect must be >= 1")
    raw = ((z_alpha + z_power) ** 2 * discordance_rate / (mde**2)) * design_effect
    return math.ceil(raw)


def stable_order(stats: Sequence[DialoguePowerStats], seed: str) -> tuple[DialoguePowerStats, ...]:
    return tuple(sorted(stats, key=lambda x: hashlib.sha256(f"{seed}:{x.uniq_id}".encode()).hexdigest()))


def select_roster(
    stats: Sequence[DialoguePowerStats],
    *,
    required_mentions: int,
    usable_fraction: float,
    seed: str,
) -> tuple[DialoguePowerStats, ...]:
    if not 0 < usable_fraction <= 1:
        raise ValueError("usable_fraction must lie in (0, 1]")
    target = math.ceil(required_mentions / usable_fraction)
    selected: list[DialoguePowerStats] = []
    total = 0
    for item in stable_order([x for x in stats if x.carry_mentions >= 2], seed):
        selected.append(item)
        total += item.carry_mentions
        if total >= target:
            return tuple(selected)
    raise ValueError(f"corpus has insufficient carry mass: need {target}, found {total}")


def budget_summary(roster: Sequence[DialoguePowerStats], *, second_pass_arms: int) -> dict[str, float | int]:
    return {
        "dialogues": len(roster),
        "carry_mentions": sum(x.carry_mentions for x in roster),
        "target_turns": sum(x.target_turns for x in roster),
        "pass0_calls": sum(x.turns for x in roster),
        "second_pass_calls": sum(x.target_turns for x in roster) * second_pass_arms,
        "total_calls": sum(x.turns for x in roster) + sum(x.target_turns for x in roster) * second_pass_arms,
        "pass0_audio_seconds": sum(x.duration for x in roster),
        "second_pass_audio_seconds": sum(x.target_seconds for x in roster) * second_pass_arms,
        "total_audio_seconds": sum(x.duration for x in roster) + sum(x.target_seconds for x in roster) * second_pass_arms,
    }


__all__ = ["DialoguePowerStats", "budget_summary", "dialogue_stats", "required_paired_mentions", "select_roster", "stable_order"]
