"""ONE integration test that reproduces, against the REAL MeetingQA/AMI
release, the exact plan-size numbers the G1-PATH structural NOT-PASS flight
(``docs/checks/2026-08-19-g1-path-flight/``) measured for the DEFECT this
mission repairs, and asserts the REPAIRED planner no longer produces them.

Gated behind an env flag -- it is never run by a plain `pytest` invocation,
only when explicitly opted into (mirrors ``test_meetingqa_real_release.py``'s
own gating rationale: the acquired bytes are WSL2-only per program
convention, not present on every machine/CI run, and unit tests must stay on
tiny synthetic fixtures per program policy).

Run explicitly (in WSL2, where SPEECHRL_DATA_DIR is reachable)::

    MMA_RUN_G1_QA_ROUTING_INTEGRATION=1 PYTHONPATH=src pytest tests/integration -v

The expected counts below are exactly what the flight's own zero-call
``run_g1.py --list-chunks`` planning measured
(``docs/checks/2026-08-19-g1-path-flight/README.md`` SS1,
``chunkplan-registered-cap.json``): the registered N=200/seed=20260818 cap
over dev-18's 489 usable-discovery questions routes 7 questions to
``ES2011a`` and 0 to ``IS1008a``; the floors-mode total is exactly the
capped set size (200), never ``n_meetings x 200``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from meeting_minutes_agent.corpora.roles import load_role_registry
from meeting_minutes_agent.probes import g1, g1_campaign

_ENV_FLAG = "MMA_RUN_G1_QA_ROUTING_INTEGRATION"
_DEFAULT_SPEECHRL_DATA_DIR = "/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data"

pytestmark = pytest.mark.skipif(
    os.environ.get(_ENV_FLAG) != "1",
    reason=f"real-G1-QA-routing integration test gated behind {_ENV_FLAG}=1",
)


def _data_dir() -> Path:
    return Path(os.environ.get("SPEECHRL_DATA_DIR", _DEFAULT_SPEECHRL_DATA_DIR))


def _meetingqa_root() -> Path:
    root = _data_dir() / "datasets" / "meetingqa"
    if not root.is_dir():
        pytest.skip(f"MeetingQA release not found: {root}")
    return root


def _ami_root() -> Path:
    root = _data_dir() / "datasets" / "ami"
    if not root.is_dir():
        pytest.skip(f"AMI corpus not found: {root}")
    return root


def _registered_capped_questions():
    registry = load_role_registry()
    all_questions = g1_campaign.load_dev18_usable_discovery_questions(
        meetingqa_root=_meetingqa_root(), ami_root=_ami_root(), registry=registry
    )
    return g1.select_capped_qa_questions(all_questions, cap=g1.QA_CAP_N, seed=g1.QA_CAP_SEED)


def test_registered_cap_over_dev18_is_exactly_200_of_489():
    capped = _registered_capped_questions()
    assert len(capped) == g1.QA_CAP_N == 200


def test_path_mode_routes_exactly_es2011a_7_and_is1008a_0():
    capped = _registered_capped_questions()
    n_qa_by_meeting = {
        meeting_id: len(g1.questions_for_meeting(capped, meeting_id)) for meeting_id in g1_campaign.PATH_MEETINGS
    }
    assert n_qa_by_meeting == {"ES2011a": 7, "IS1008a": 0}

    # The routed counts feed straight into build_work_items -- both
    # QA-bearing arms carry the SAME per-meeting count (one call per
    # question per arm), never the whole 200-question campaign-wide set.
    n_transcribe = {(m, a): 1 for m in g1_campaign.PATH_MEETINGS for a in g1.ARMS}
    work_items = g1_campaign.build_work_items(
        g1_campaign.PATH_MEETINGS, n_transcribe_by_meeting_arm=n_transcribe, n_qa_by_meeting=n_qa_by_meeting
    )
    by_meeting_arm = {(item.meeting_id, item.arm): item for item in work_items}
    assert by_meeting_arm[("ES2011a", g1.ARM_Z_TURN)].n_qa == 7
    assert by_meeting_arm[("ES2011a", g1.ARM_Z_ORACLE)].n_qa == 7
    assert by_meeting_arm[("IS1008a", g1.ARM_Z_TURN)].n_qa == 0
    assert by_meeting_arm[("IS1008a", g1.ARM_Z_ORACLE)].n_qa == 0

    total_qa = sum(item.n_qa for item in work_items)
    assert total_qa == 7 * 2  # == 14, NEVER 200 x 2 x 2 meetings


def test_floors_mode_total_qa_calls_is_capped_n_times_two_arms_never_n_meetings_times_cap():
    capped = _registered_capped_questions()
    meetings = g1_campaign.meetings_for_mode("floors")
    assert len(meetings) == 18

    n_qa_by_meeting = {meeting_id: len(g1.questions_for_meeting(capped, meeting_id)) for meeting_id in meetings}
    # Every capped question is attached to exactly one dev-18 meeting, so
    # the per-meeting counts must sum back to the cap itself.
    assert sum(n_qa_by_meeting.values()) == len(capped) == 200

    n_transcribe = {(m, a): 1 for m in meetings for a in g1.ARMS}
    work_items = g1_campaign.build_work_items(
        meetings, n_transcribe_by_meeting_arm=n_transcribe, n_qa_by_meeting=n_qa_by_meeting
    )
    total_qa_calls = sum(item.n_qa for item in work_items)

    registered_total = len(capped) * len(g1.ARMS_WITH_MINUTES_QA)  # 200 x 2 = 400 (prereg SS6: "QA ~=400")
    busted_total = len(meetings) * len(capped) * len(g1.ARMS_WITH_MINUTES_QA)  # the NOT-PASS arithmetic: 7200

    assert total_qa_calls == registered_total == 400
    assert total_qa_calls != busted_total
