from __future__ import annotations

from meeting_minutes_agent.probes.e4_power import DialoguePowerStats, stable_order


def test_frozen_seed_order_is_independent_of_input_order():
    stats = [DialoguePowerStats(f"D{i}", 10, 100.0, 2, 2, 20.0) for i in range(80)]
    seed = "e4-disjoint-prev-2026-08-21-v1"
    assert stable_order(stats, seed) == stable_order(tuple(reversed(stats)), seed)
    assert len(stable_order(stats, seed)[:60]) == 60
