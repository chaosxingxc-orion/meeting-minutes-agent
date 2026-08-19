"""Tests for :mod:`meeting_minutes_agent.probes.g1_campaign`: mode rosters,
resumable work items, the <=50-minute chunk planner, the campaign budget
guard (with precharge), per-item/per-chunk receipts, and the managed
llama-server child-process owner -- all exercised with injected fakes, zero
real subprocess/network contact (mirrors ``tests/unit/scripts/test_run_precomp.py``'s
own discipline)."""

from __future__ import annotations

import subprocess

import pytest

from meeting_minutes_agent.probes import g1
from meeting_minutes_agent.probes.g1_campaign import (
    CAMPAIGN_MAX_CALLS,
    CAMPAIGN_MAX_GPU_HOURS,
    CAMPAIGN_MAX_WALL_HOURS,
    PATH_MEETINGS,
    Chunk,
    ChunkPlanError,
    G1Budget,
    G1BudgetExceeded,
    G1CampaignError,
    ManagedLlamaServer,
    ServerStartupError,
    WorkItem,
    build_chunk_receipt,
    build_item_receipt,
    build_work_items,
    chunk_receipt_path,
    item_already_done,
    item_receipt_path,
    load_item_receipts,
    meetings_for_mode,
    plan_chunks,
    usage_from_item_receipts,
    write_chunk_receipt,
    write_item_receipt,
)


# ---------------------------------------------------------------------------
# mode rosters
# ---------------------------------------------------------------------------


class TestMeetingsForMode:
    def test_path_mode_is_exactly_the_two_registered_meetings(self):
        assert meetings_for_mode("path") == PATH_MEETINGS == ("ES2011a", "IS1008a")

    def test_floors_mode_defaults_to_the_frozen_dev18(self):
        meetings = meetings_for_mode("floors")
        assert len(meetings) == 18
        assert meetings == tuple(sorted(meetings))

    def test_floors_mode_honours_an_injected_roster(self):
        assert meetings_for_mode("floors", dev18=["B", "A"]) == ("A", "B")

    def test_unknown_mode_raises(self):
        with pytest.raises(G1CampaignError):
            meetings_for_mode("bogus")


# ---------------------------------------------------------------------------
# WorkItem / build_work_items
# ---------------------------------------------------------------------------


class TestWorkItem:
    def test_n_calls_sums_all_three_kinds(self):
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=10, n_minutes=1, n_qa=200)
        assert item.n_calls == 211

    def test_item_id_is_meeting_colon_arm(self):
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=1)
        assert item.item_id == "M1:Z-turn"

    def test_unknown_arm_rejected(self):
        with pytest.raises(G1CampaignError):
            WorkItem(meeting_id="M1", arm="Z-bogus", n_transcribe=1)

    def test_minutes_or_qa_on_a_non_qa_arm_is_rejected(self):
        with pytest.raises(G1CampaignError):
            WorkItem(meeting_id="M1", arm=g1.ARM_Z_FREE, n_transcribe=1, n_minutes=1)
        with pytest.raises(G1CampaignError):
            WorkItem(meeting_id="M1", arm=g1.ARM_Z_NODIAR, n_transcribe=1, n_qa=5)

    def test_negative_counts_rejected(self):
        with pytest.raises(G1CampaignError):
            WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=-1)


class TestBuildWorkItems:
    def test_one_item_per_meeting_per_arm_in_registered_order(self):
        counts = {(m, a): 5 for m in ("M1", "M2") for a in g1.ARMS}
        items = build_work_items(["M1", "M2"], n_transcribe_by_meeting_arm=counts, n_qa_per_meeting=3)
        assert [i.item_id for i in items] == [f"{m}:{a}" for m in ("M1", "M2") for a in g1.ARMS]

    def test_minutes_and_qa_only_wired_on_z_turn_and_z_oracle(self):
        counts = {(m, a): 5 for m in ("M1",) for a in g1.ARMS}
        items = build_work_items(["M1"], n_transcribe_by_meeting_arm=counts, n_qa_per_meeting=200)
        by_arm = {i.arm: i for i in items}
        assert by_arm[g1.ARM_Z_TURN].n_minutes == 1 and by_arm[g1.ARM_Z_TURN].n_qa == 200
        assert by_arm[g1.ARM_Z_ORACLE].n_minutes == 1 and by_arm[g1.ARM_Z_ORACLE].n_qa == 200
        assert by_arm[g1.ARM_Z_FREE].n_minutes == 0 and by_arm[g1.ARM_Z_FREE].n_qa == 0
        assert by_arm[g1.ARM_Z_NODIAR].n_minutes == 0 and by_arm[g1.ARM_Z_NODIAR].n_qa == 0

    def test_missing_count_key_raises(self):
        with pytest.raises(G1CampaignError):
            build_work_items(["M1"], n_transcribe_by_meeting_arm={}, arms=(g1.ARM_Z_TURN,))

    def test_n_qa_by_meeting_routes_a_distinct_count_per_meeting(self):
        # The G1-PATH structural NOT-PASS repair: QA counts are PER MEETING,
        # never one campaign-wide scalar applied uniformly to every meeting.
        counts = {(m, a): 5 for m in ("M1", "M2", "M3") for a in g1.ARMS}
        items = build_work_items(
            ["M1", "M2", "M3"], n_transcribe_by_meeting_arm=counts, n_qa_by_meeting={"M1": 7, "M2": 0}
        )
        by_meeting_arm = {(i.meeting_id, i.arm): i for i in items}
        assert by_meeting_arm[("M1", g1.ARM_Z_TURN)].n_qa == 7
        assert by_meeting_arm[("M1", g1.ARM_Z_ORACLE)].n_qa == 7
        assert by_meeting_arm[("M2", g1.ARM_Z_TURN)].n_qa == 0
        assert by_meeting_arm[("M2", g1.ARM_Z_ORACLE)].n_qa == 0
        # M3 is absent from the mapping -- zero QA, never an error, never a
        # fallback to some other meeting's count.
        assert by_meeting_arm[("M3", g1.ARM_Z_TURN)].n_qa == 0
        # Transcribe-only arms never carry qa regardless of the mapping.
        assert by_meeting_arm[("M1", g1.ARM_Z_FREE)].n_qa == 0
        assert by_meeting_arm[("M1", g1.ARM_Z_NODIAR)].n_qa == 0

    def test_n_qa_by_meeting_total_is_never_n_meetings_times_a_shared_cap(self):
        # Regression guard for the exact NOT-PASS arithmetic: dispatching a
        # campaign-wide capped set to every meeting planned
        # n_meetings x N x n_qa_arms QA calls instead of N x n_qa_arms.
        meetings = [f"M{i}" for i in range(18)]  # dev-18-shaped roster size
        counts = {(m, a): 1 for m in meetings for a in g1.ARMS}
        capped_n = 200
        # Only two meetings actually carry capped questions (mirrors the
        # real dev-18 distribution's sparsity -- most meetings carry zero).
        n_qa_by_meeting = {"M0": 150, "M1": 50}
        items = build_work_items(meetings, n_transcribe_by_meeting_arm=counts, n_qa_by_meeting=n_qa_by_meeting)
        total_qa = sum(i.n_qa for i in items)
        assert total_qa == capped_n * len(g1.ARMS_WITH_MINUTES_QA)  # 400: the registered arithmetic
        assert total_qa != len(meetings) * capped_n * len(g1.ARMS_WITH_MINUTES_QA)  # 7200: the NOT-PASS arithmetic

    def test_n_qa_by_meeting_takes_precedence_over_n_qa_per_meeting(self):
        counts = {(m, a): 1 for m in ("M1",) for a in g1.ARMS}
        items = build_work_items(
            ["M1"], n_transcribe_by_meeting_arm=counts, n_qa_per_meeting=200, n_qa_by_meeting={"M1": 3}
        )
        by_arm = {i.arm: i for i in items}
        assert by_arm[g1.ARM_Z_TURN].n_qa == 3


# ---------------------------------------------------------------------------
# chunk planner: <=50-minute chunks
# ---------------------------------------------------------------------------


class TestPlanChunks:
    def _item(self, meeting: str, arm: str, n: int) -> WorkItem:
        return WorkItem(meeting_id=meeting, arm=arm, n_transcribe=n)

    def test_packs_small_items_into_one_chunk(self):
        items = [self._item("M1", g1.ARM_Z_TURN, 5), self._item("M1", g1.ARM_Z_FREE, 5)]
        chunks = plan_chunks(items, max_chunk_wall_seconds=1000.0, seconds_per_request=3.7)
        assert len(chunks) == 1
        assert chunks[0].items == tuple(items)

    def test_splits_across_chunks_when_the_cap_is_exceeded(self):
        # 3.7s/request * 500 requests = 1850s per item; cap at 2000s admits
        # exactly one item per chunk.
        items = [self._item("M1", g1.ARM_Z_TURN, 500), self._item("M2", g1.ARM_Z_TURN, 500)]
        chunks = plan_chunks(items, max_chunk_wall_seconds=2000.0, seconds_per_request=3.7)
        assert len(chunks) == 2
        assert chunks[0].items == (items[0],)
        assert chunks[1].items == (items[1],)

    def test_never_reorders_items(self):
        items = [self._item(f"M{i}", g1.ARM_Z_TURN, 1) for i in range(20)]
        chunks = plan_chunks(items, max_chunk_wall_seconds=100000.0)
        flat = [i for c in chunks for i in c.items]
        assert flat == items

    def test_every_chunk_stays_within_the_registered_50_minute_cap(self):
        items = [self._item(f"M{i}", a, 30) for i in range(18) for a in g1.ARMS]
        chunks = plan_chunks(items)  # registered defaults: <=50min, 3.7s/request
        for chunk in chunks:
            assert chunk.estimated_wall_seconds(seconds_per_request=3.7) <= 50 * 60.0

    def test_a_single_oversized_item_raises(self):
        huge = self._item("M1", g1.ARM_Z_TURN, 10_000)
        with pytest.raises(ChunkPlanError):
            plan_chunks([huge], max_chunk_wall_seconds=60.0, seconds_per_request=3.7)

    def test_nonpositive_cap_raises(self):
        with pytest.raises(ChunkPlanError):
            plan_chunks([self._item("M1", g1.ARM_Z_TURN, 1)], max_chunk_wall_seconds=0.0)

    def test_chunk_index_is_sequential(self):
        items = [self._item(f"M{i}", g1.ARM_Z_TURN, 500) for i in range(3)]
        chunks = plan_chunks(items, max_chunk_wall_seconds=2000.0, seconds_per_request=3.7)
        assert [c.index for c in chunks] == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# receipts + resume-skip at (meeting, arm) granularity
# ---------------------------------------------------------------------------


class TestItemReceiptsAndResume:
    def test_not_done_when_no_receipt_exists(self, tmp_path):
        assert item_already_done(tmp_path, "M1", g1.ARM_Z_TURN) is False

    def test_done_after_writing_an_ok_receipt(self, tmp_path):
        receipt = build_item_receipt(
            meeting_id="M1", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=5, gpu_seconds=1.0, wall_seconds=2.0,
            contacts=[],
        )
        write_item_receipt(tmp_path, receipt)
        assert item_receipt_path(tmp_path, "M1", g1.ARM_Z_TURN).is_file()
        assert item_already_done(tmp_path, "M1", g1.ARM_Z_TURN) is True

    def test_not_done_when_receipt_is_not_ok(self, tmp_path):
        receipt = build_item_receipt(
            meeting_id="M1", arm=g1.ARM_Z_TURN, ok=False, error="boom", n_calls=0, gpu_seconds=0.0, wall_seconds=0.1,
            contacts=[],
        )
        write_item_receipt(tmp_path, receipt)
        assert item_already_done(tmp_path, "M1", g1.ARM_Z_TURN) is False

    def test_not_done_when_receipt_is_malformed_json(self, tmp_path):
        path = item_receipt_path(tmp_path, "M1", g1.ARM_Z_TURN)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        assert item_already_done(tmp_path, "M1", g1.ARM_Z_TURN) is False

    def test_chunk_receipt_round_trips(self, tmp_path):
        outcomes = [
            build_item_receipt(meeting_id="M1", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=3, gpu_seconds=0.5, wall_seconds=1.0, contacts=[])
        ]
        receipt = build_chunk_receipt(chunk_index=0, item_outcomes=outcomes, budget_after={"calls_used": 3}, stopped_reason=None)
        write_chunk_receipt(tmp_path, 0, receipt)
        assert chunk_receipt_path(tmp_path, 0).is_file()
        assert receipt["n_ok"] == 1 and receipt["n_error"] == 0

    def test_load_item_receipts_returns_empty_list_when_no_receipts_dir(self, tmp_path):
        assert load_item_receipts(tmp_path) == []

    def test_load_item_receipts_reads_every_receipt(self, tmp_path):
        write_item_receipt(tmp_path, build_item_receipt(meeting_id="M1", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=1, gpu_seconds=0.0, wall_seconds=0.0, contacts=[]))
        write_item_receipt(tmp_path, build_item_receipt(meeting_id="M2", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=2, gpu_seconds=0.0, wall_seconds=0.0, contacts=[]))
        receipts = load_item_receipts(tmp_path)
        assert len(receipts) == 2
        assert sum(r["n_calls"] for r in receipts) == 3


# ---------------------------------------------------------------------------
# campaign budget: ceilings + precharge
# ---------------------------------------------------------------------------


class TestG1Budget:
    def test_registered_ceilings(self):
        assert CAMPAIGN_MAX_CALLS == 2900
        assert CAMPAIGN_MAX_GPU_HOURS == 6.0
        assert CAMPAIGN_MAX_WALL_HOURS == 8.0

    def test_default_budget_admits_a_small_item(self):
        budget = G1Budget()
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=10)
        budget.check_before_item(item)  # must not raise

    def test_call_ceiling_refuses_an_over_budget_item(self):
        budget = G1Budget(max_calls=10)
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=11)
        with pytest.raises(G1BudgetExceeded):
            budget.check_before_item(item)

    def test_wall_hour_ceiling_refuses_an_over_budget_item(self):
        budget = G1Budget(max_wall_hours=0.001)  # 3.6s
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=5)  # 18.5s at 3.7s/req
        with pytest.raises(G1BudgetExceeded):
            budget.check_before_item(item, seconds_per_request=3.7)

    def test_gpu_hour_ceiling_already_reached_refuses(self):
        budget = G1Budget(max_gpu_hours=0.0001)
        budget.record(n_calls=0, gpu_seconds=1.0, wall_seconds=0.0)
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=1)
        with pytest.raises(G1BudgetExceeded):
            budget.check_before_item(item)

    def test_record_accumulates(self):
        budget = G1Budget()
        budget.record(n_calls=5, gpu_seconds=1.5, wall_seconds=10.0)
        budget.record(n_calls=3, gpu_seconds=0.5, wall_seconds=5.0)
        assert budget.calls_used == 8
        assert budget.gpu_seconds_used == 2.0
        assert budget.wall_seconds_used == 15.0

    def test_usage_from_item_receipts_sums_deltas(self):
        receipts = [
            build_item_receipt(meeting_id="M1", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=3, gpu_seconds=1.0, wall_seconds=2.0, contacts=[]),
            build_item_receipt(meeting_id="M2", arm=g1.ARM_Z_TURN, ok=False, error="e", n_calls=2, gpu_seconds=0.5, wall_seconds=1.0, contacts=[]),
            "not a mapping",
        ]
        used = usage_from_item_receipts(receipts)
        assert used == {"calls_used": 5, "gpu_seconds_used": 1.5, "wall_seconds_used": 3.0}

    def test_precharge_is_additive_and_fail_closed_afterward(self, tmp_path):
        write_item_receipt(
            tmp_path,
            build_item_receipt(meeting_id="M0", arm=g1.ARM_Z_TURN, ok=True, error=None, n_calls=2895, gpu_seconds=0.0, wall_seconds=0.0, contacts=[]),
        )
        budget = G1Budget(max_calls=2900)
        budget.precharge(load_item_receipts(tmp_path))
        assert budget.calls_used == 2895
        item = WorkItem(meeting_id="M1", arm=g1.ARM_Z_TURN, n_transcribe=10)
        with pytest.raises(G1BudgetExceeded):
            budget.check_before_item(item)

    def test_precharge_never_resets_existing_usage(self):
        budget = G1Budget()
        budget.record(n_calls=10, gpu_seconds=1.0, wall_seconds=1.0)
        budget.precharge([])
        assert budget.calls_used == 10

    def test_to_dict_shape(self):
        budget = G1Budget()
        payload = budget.to_dict()
        assert payload["ceilings"]["max_calls"] == CAMPAIGN_MAX_CALLS
        assert payload["calls_used"] == 0


# ---------------------------------------------------------------------------
# ManagedLlamaServer: child-process ownership, fully faked
# ---------------------------------------------------------------------------


class _FakeProcess:
    def __init__(self, *, exits_immediately: bool = False) -> None:
        self._alive = not exits_immediately
        self.terminated = False
        self.killed = False
        self.returncode = None if not exits_immediately else 1

    def poll(self):
        return None if self._alive else (self.returncode if self.returncode is not None else 0)

    def terminate(self):
        self.terminated = True
        self._alive = False
        self.returncode = 0

    def kill(self):
        self.killed = True
        self._alive = False
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class TestManagedLlamaServer:
    def test_start_waits_for_health_then_returns(self):
        process = _FakeProcess()
        calls = {"health": 0}

        def health_check(base_url):
            calls["health"] += 1
            return calls["health"] >= 2  # unhealthy once, then healthy

        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=health_check,
            sleep=lambda s: None,
        )
        server.start()
        assert server.is_running is True
        assert calls["health"] == 2

    def test_start_raises_if_the_process_exits_before_healthy(self):
        process = _FakeProcess(exits_immediately=True)
        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: False,
            sleep=lambda s: None,
        )
        with pytest.raises(ServerStartupError):
            server.start()

    def test_start_raises_on_health_timeout_and_shuts_down(self):
        process = _FakeProcess()
        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: False,
            sleep=lambda s: None, health_timeout_seconds=0.0,
        )
        with pytest.raises(ServerStartupError):
            server.start()
        assert process.terminated is True

    def test_shutdown_terminates_a_running_process(self):
        process = _FakeProcess()
        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: True,
            sleep=lambda s: None,
        )
        server.start()
        server.shutdown()
        assert process.terminated is True
        assert server.is_running is False

    def test_shutdown_is_a_noop_if_never_started(self):
        server = ManagedLlamaServer(["llama-server"], base_url="http://x")
        server.shutdown()  # must not raise

    def test_shutdown_kills_on_terminate_timeout(self):
        class _StubbornProcess(_FakeProcess):
            def wait(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
                return 0

        process = _StubbornProcess()
        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: True,
            sleep=lambda s: None,
        )
        server.start()
        server.shutdown()
        assert process.killed is True

    def test_context_manager_owns_start_and_shutdown(self):
        process = _FakeProcess()
        with ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: True,
            sleep=lambda s: None,
        ) as server:
            assert server.is_running is True
        assert process.terminated is True

    def test_context_manager_tears_down_the_server_even_on_a_raised_exception(self):
        process = _FakeProcess()
        with pytest.raises(RuntimeError):
            with ManagedLlamaServer(
                ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: True,
                sleep=lambda s: None,
            ):
                raise RuntimeError("simulated per-item failure")
        assert process.terminated is True

    def test_start_twice_raises(self):
        process = _FakeProcess()
        server = ManagedLlamaServer(
            ["llama-server"], base_url="http://x", popen=lambda cmd: process, health_check=lambda url: True,
            sleep=lambda s: None,
        )
        server.start()
        with pytest.raises(RuntimeError):
            server.start()
