"""Tests for :mod:`meeting_minutes_agent.corpora.roles`.

Two jobs. First, the committed registry
(``configs/corpora/ami-role-registry.json``) is itself machine-checked here:
the hard constraints from the G1 precondition -- one role per meeting, the
assignment total over the roster, nothing in the frozen eval-16 holding an
active role, and (v1.1) the MeetingQA question-usage policy computed
per meeting -- are asserted against the real file, so a bad edit to the data
fails the suite. Second, every fail-closed refusal is exercised on a
tampered copy: the loader must raise rather than degrade.

v1.1 (2026-08-18) note for readers of history: v1.0.0 quarantined a MeetingQA
question the instant its meeting was spoken for by any AMI role other than
``qa-eval``. The tests below that exercised that rule (``test_quarantine_*``,
``test_quarantined_question_ids_*``, and the tamper tests targeting the old
``quarantine.meetings`` list) are retired and replaced by the
``question_usage`` tests in the equivalent sections below; the AMI-role tests
above them are unchanged because meeting roles themselves did not change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from meeting_minutes_agent.corpora.roles import (
    ACTIVE_ROLES,
    FROZEN_DEV_18,
    FROZEN_EVAL_16,
    RESERVED_ROLES,
    AmiRoleRegistry,
    DuplicateRoleError,
    HeldOutLeakageError,
    MeetingRole,
    QuarantinedQuestionError,
    QuestionUsagePolicy,
    RoleRegistryError,
    UnknownMeetingError,
    default_registry_path,
    filter_question_ids_by_policy,
    load_role_registry,
)

# Frozen expectations for the committed registry. These are the numbers the
# G1 preregistration binds against; a change here must be a deliberate,
# documented re-derivation, not a side effect.
EXPECTED_ROLE_COUNTS = {
    "asr-eval": 18,
    "qa-eval": 42,
    "glossary-discovery": 76,
    "held-out-confirmatory": 16,
    "held-out-reserve": 19,
}
EXPECTED_ROSTER = 171
EXPECTED_MEETINGQA_TOTAL = 7735

# v1.1: the question-usage policy tallies (docs/plans/2026-08-17-founding-workplan.md
# §4b; docs/readiness/2026-08-18-ami-role-registry.md §11). Recovers 4,732
# usable-discovery questions, up from v1.0.0's 1,918 qa-eval-only figure.
EXPECTED_QUESTION_USAGE_COUNTS = {
    "usable-discovery": {"n_meetings": 101, "n_questions": 4732},
    "reserved-final-reporting": {"n_meetings": 49, "n_questions": 2235},
    "untouchable": {"n_meetings": 16, "n_questions": 768},
    "no-meetingqa": {"n_meetings": 5, "n_questions": 0},
}

# Concrete regression fixtures pinned to the ruling text: "MeetingQA train+dev
# questions = usable for discovery on any non-eval-16 meeting (including
# dev-18); MeetingQA TEST questions = reserved for final reporting; questions
# on eval-16 meetings = untouchable regardless of their MeetingQA split."
DEV_18_TEST_SPLIT_MEETING = "IB4004"  # dev-18, asr-eval role, MeetingQA test split
DEV_18_TRAIN_OR_DEV_SPLIT_MEETING = "ES2011a"  # dev-18, asr-eval role, MeetingQA dev split
HELD_OUT_RESERVE_DEV_SPLIT_MEETING = "EN2001b"  # held-out-reserve role, MeetingQA dev split
EVAL_16_NON_TEST_SPLIT_MEETING = "EN2002a"  # eval-16, MeetingQA *dev* split, not test
NO_MEETINGQA_MEETING = "IN1005"  # held-out-137, no MeetingQA coverage at all


@pytest.fixture(scope="module")
def registry() -> AmiRoleRegistry:
    return load_role_registry()


@pytest.fixture()
def tamper(tmp_path: Path) -> Callable[[Callable[[dict[str, Any]], None]], Path]:
    """Write a mutated copy of the committed registry to ``tmp_path`` and
    return its path, so refusal tests never touch the real file."""

    source = json.loads(default_registry_path().read_text(encoding="utf-8"))

    def _tamper(mutate: Callable[[dict[str, Any]], None]) -> Path:
        document = json.loads(json.dumps(source))
        mutate(document)
        path = tmp_path / "tampered-registry.json"
        path.write_text(json.dumps(document, indent=1), encoding="utf-8")
        return path

    return _tamper


# ---------------------------------------------------------------------------
# the committed registry: AMI roles (unchanged in v1.1)
# ---------------------------------------------------------------------------


def test_committed_registry_loads_and_covers_the_whole_roster(registry: AmiRoleRegistry):
    assert len(registry) == EXPECTED_ROSTER
    assert registry.source_path == default_registry_path()
    assert len(registry.registry_hash) == 64


def test_role_counts_are_the_frozen_ones(registry: AmiRoleRegistry):
    assert registry.role_counts() == EXPECTED_ROLE_COUNTS
    assert sum(EXPECTED_ROLE_COUNTS.values()) == EXPECTED_ROSTER


def test_no_meeting_carries_two_roles(registry: AmiRoleRegistry):
    """The five role sets partition the roster: pairwise disjoint, union
    total. This is the 'exactly one role' constraint stated as set algebra
    rather than trusted from the file's shape."""

    sets = {role: set(registry.meetings_with_role(role)) for role in MeetingRole}
    union: set[str] = set()
    for role, members in sets.items():
        overlap = union & members
        assert not overlap, f"{role.value} overlaps an earlier role on {sorted(overlap)}"
        union |= members
    assert union == set(registry.meetings)


def test_registry_file_has_no_duplicate_meeting_ids():
    """A duplicated meeting key would be a second role smuggled in past
    ``json.loads``'s last-wins behaviour -- check the raw text, not the
    parsed dict."""

    raw = default_registry_path().read_text(encoding="utf-8")
    document = json.loads(raw)
    keys = [line.split('"')[1] for line in raw.splitlines() if line.startswith("    \"")]
    meeting_keys = [k for k in keys if k in document["meetings"]]
    assert len(meeting_keys) == len(set(meeting_keys)) == EXPECTED_ROSTER


def test_asr_eval_is_exactly_the_frozen_dev_18(registry: AmiRoleRegistry):
    assert set(registry.meetings_with_role(MeetingRole.ASR_EVAL)) == set(FROZEN_DEV_18)


def test_nothing_in_the_frozen_eval_16_holds_an_active_role(registry: AmiRoleRegistry):
    for meeting in FROZEN_EVAL_16:
        record = registry.record(meeting)
        assert record.role is MeetingRole.HELD_OUT_CONFIRMATORY
        assert record.role not in ACTIVE_ROLES
        assert not record.is_exposable


def test_eval_16_meetings_refuse_exposure(registry: AmiRoleRegistry):
    for meeting in FROZEN_EVAL_16:
        with pytest.raises(HeldOutLeakageError, match="reserved role"):
            registry.assert_exposable(meeting)


def test_held_out_reserve_also_refuses_exposure(registry: AmiRoleRegistry):
    reserve = registry.meetings_with_role(MeetingRole.HELD_OUT_RESERVE)
    assert reserve
    for meeting in reserve:
        with pytest.raises(HeldOutLeakageError):
            registry.assert_exposable(meeting)


def test_active_meetings_are_exposable_only_for_their_own_role(registry: AmiRoleRegistry):
    flight = registry.meetings_with_role(MeetingRole.ASR_EVAL)[0]
    registry.assert_exposable(flight)
    registry.assert_exposable(flight, for_role=MeetingRole.ASR_EVAL)
    with pytest.raises(HeldOutLeakageError, match="serves one role only"):
        registry.assert_exposable(flight, for_role=MeetingRole.GLOSSARY_DISCOVERY)


def test_every_reserved_role_is_unexposable_and_every_active_one_is_not(registry: AmiRoleRegistry):
    assert ACTIVE_ROLES.isdisjoint(RESERVED_ROLES)
    assert ACTIVE_ROLES | RESERVED_ROLES == set(MeetingRole)


# ---------------------------------------------------------------------------
# v1.1 question-usage policy
# ---------------------------------------------------------------------------


def test_question_usage_counts_are_the_frozen_ones(registry: AmiRoleRegistry):
    assert registry.question_usage_counts() == EXPECTED_QUESTION_USAGE_COUNTS
    total_meetings = sum(b["n_meetings"] for b in EXPECTED_QUESTION_USAGE_COUNTS.values())
    total_questions = sum(b["n_questions"] for b in EXPECTED_QUESTION_USAGE_COUNTS.values())
    assert total_meetings == EXPECTED_ROSTER
    assert total_questions == EXPECTED_MEETINGQA_TOTAL


def test_no_meeting_carries_two_question_usage_policies(registry: AmiRoleRegistry):
    """The four policy buckets partition the roster, exactly like the five
    role sets above -- but along the independent question-usage axis."""

    buckets = {
        QuestionUsagePolicy.USABLE_DISCOVERY: set(registry.usable_discovery_questions()),
        QuestionUsagePolicy.RESERVED_FINAL_REPORTING: set(registry.reserved_test_questions()),
        QuestionUsagePolicy.UNTOUCHABLE: set(registry.untouchable_questions()),
        QuestionUsagePolicy.NO_MEETINGQA: {
            m for m in registry.meetings
            if registry.question_usage_policy_of(m) is QuestionUsagePolicy.NO_MEETINGQA
        },
    }
    union: set[str] = set()
    for policy, members in buckets.items():
        overlap = union & members
        assert not overlap, f"{policy.value} overlaps an earlier policy on {sorted(overlap)}"
        union |= members
    assert union == set(registry.meetings)


def test_untouchable_questions_is_exactly_eval_16(registry: AmiRoleRegistry):
    """Every eval-16 meeting carries MeetingQA questions in the shipped
    release, so untouchable-questions coincides with the full frozen set."""

    assert set(registry.untouchable_questions()) == set(FROZEN_EVAL_16)


def test_eval_16_meeting_is_untouchable_regardless_of_its_own_meetingqa_split(
    registry: AmiRoleRegistry,
):
    """Direct regression pin for the ruling: 'questions on eval-16 meetings
    = untouchable regardless of their MeetingQA split.' This fixture's own
    MeetingQA split is 'dev', which would be usable-discovery for any
    non-eval-16 meeting -- but eval-16 membership wins first."""

    record = registry.record(EVAL_16_NON_TEST_SPLIT_MEETING)
    assert record.meetingqa_split == "dev"
    assert record.question_usage_policy is QuestionUsagePolicy.UNTOUCHABLE
    assert EVAL_16_NON_TEST_SPLIT_MEETING in registry.untouchable_questions()
    assert EVAL_16_NON_TEST_SPLIT_MEETING not in registry.usable_discovery_questions()


def test_dev_18_test_split_meeting_is_reserved_not_untouchable(registry: AmiRoleRegistry):
    """Direct regression pin: dev-18 (asr-eval role) is not eval-16, so its
    MeetingQA test-split questions are reserved for final reporting, not
    untouchable and not usable for discovery."""

    record = registry.record(DEV_18_TEST_SPLIT_MEETING)
    assert record.role is MeetingRole.ASR_EVAL
    assert record.meetingqa_split == "test"
    assert record.question_usage_policy is QuestionUsagePolicy.RESERVED_FINAL_REPORTING
    assert DEV_18_TEST_SPLIT_MEETING in registry.reserved_test_questions()
    assert DEV_18_TEST_SPLIT_MEETING not in registry.untouchable_questions()
    assert DEV_18_TEST_SPLIT_MEETING not in registry.usable_discovery_questions()


def test_dev_18_train_or_dev_split_meeting_is_usable_for_discovery(registry: AmiRoleRegistry):
    """Direct regression pin: 'MeetingQA train+dev questions = usable for
    discovery on any non-eval-16 meeting (including dev-18)'."""

    record = registry.record(DEV_18_TRAIN_OR_DEV_SPLIT_MEETING)
    assert record.role is MeetingRole.ASR_EVAL
    assert record.meetingqa_split in ("train", "dev")
    assert record.question_usage_policy is QuestionUsagePolicy.USABLE_DISCOVERY
    assert DEV_18_TRAIN_OR_DEV_SPLIT_MEETING in registry.usable_discovery_questions()


def test_held_out_reserve_meeting_can_still_supply_usable_discovery_questions(
    registry: AmiRoleRegistry,
):
    """The two axes are independent: this meeting's AMI role
    (held-out-reserve) keeps its audio/transcript unexposable via
    ``assert_exposable`` -- unchanged from v1.0.0 -- while its MeetingQA
    train/dev-split questions are, under v1.1, a usable discovery surface in
    their own right, per the ruling's 'any meeting except eval-16'."""

    record = registry.record(HELD_OUT_RESERVE_DEV_SPLIT_MEETING)
    assert record.role is MeetingRole.HELD_OUT_RESERVE
    assert record.question_usage_policy is QuestionUsagePolicy.USABLE_DISCOVERY
    assert HELD_OUT_RESERVE_DEV_SPLIT_MEETING in registry.usable_discovery_questions()
    with pytest.raises(HeldOutLeakageError):
        registry.assert_exposable(HELD_OUT_RESERVE_DEV_SPLIT_MEETING)


def test_no_meetingqa_meeting_has_no_policy_bucket_membership(registry: AmiRoleRegistry):
    record = registry.record(NO_MEETINGQA_MEETING)
    assert record.meetingqa_questions == 0
    assert record.question_usage_policy is QuestionUsagePolicy.NO_MEETINGQA
    assert NO_MEETINGQA_MEETING not in registry.usable_discovery_questions()
    assert NO_MEETINGQA_MEETING not in registry.reserved_test_questions()
    assert NO_MEETINGQA_MEETING not in registry.untouchable_questions()


def test_assert_question_usable_admits_usable_discovery_and_refuses_the_rest(
    registry: AmiRoleRegistry,
):
    registry.assert_question_usable(DEV_18_TRAIN_OR_DEV_SPLIT_MEETING)  # no raise

    with pytest.raises(HeldOutLeakageError, match="UNTOUCHABLE"):
        registry.assert_question_usable(EVAL_16_NON_TEST_SPLIT_MEETING)

    with pytest.raises(QuarantinedQuestionError, match="RESERVED"):
        registry.assert_question_usable(DEV_18_TEST_SPLIT_MEETING)

    with pytest.raises(QuarantinedQuestionError, match="no MeetingQA questions"):
        registry.assert_question_usable(NO_MEETINGQA_MEETING)


def test_filter_question_ids_by_policy_filters_a_question_stream(registry: AmiRoleRegistry):
    questions = [
        {"id": "keep-1", "title": DEV_18_TRAIN_OR_DEV_SPLIT_MEETING},
        {"id": "drop-reserved", "title": DEV_18_TEST_SPLIT_MEETING},
        {"id": "drop-untouchable", "title": EVAL_16_NON_TEST_SPLIT_MEETING},
    ]
    assert filter_question_ids_by_policy(
        registry, questions, QuestionUsagePolicy.USABLE_DISCOVERY
    ) == ("keep-1",)
    assert filter_question_ids_by_policy(
        registry, questions, QuestionUsagePolicy.RESERVED_FINAL_REPORTING
    ) == ("drop-reserved",)
    assert filter_question_ids_by_policy(
        registry, questions, QuestionUsagePolicy.UNTOUCHABLE
    ) == ("drop-untouchable",)


def test_filter_question_ids_by_policy_refuses_an_unknown_meeting(registry: AmiRoleRegistry):
    with pytest.raises(UnknownMeetingError):
        filter_question_ids_by_policy(
            registry, [{"id": "q", "title": "NOPE999z"}], QuestionUsagePolicy.USABLE_DISCOVERY
        )


# ---------------------------------------------------------------------------
# fail-closed refusals
# ---------------------------------------------------------------------------


def test_unknown_meeting_raises_everywhere(registry: AmiRoleRegistry):
    for call in (
        registry.record,
        registry.role_of,
        registry.assert_exposable,
        registry.assert_question_usable,
        registry.question_usage_policy_of,
    ):
        with pytest.raises(UnknownMeetingError, match="not on the AMI role registry roster"):
            call("ZZ9999z")
    assert "ZZ9999z" not in registry


def test_duplicate_meeting_id_raises(tmp_path: Path):
    """``json.loads`` keeps the last of duplicated keys; the loader must
    refuse instead, or a meeting could carry a second role."""

    raw = default_registry_path().read_text(encoding="utf-8")
    duplicated = raw.replace(
        '  "meetings": {\n',
        '  "meetings": {\n    "ES2011a": {"role": "qa-eval"},\n',
        1,
    )
    path = tmp_path / "duplicate.json"
    path.write_text(duplicated, encoding="utf-8")
    with pytest.raises(DuplicateRoleError, match="duplicate key 'ES2011a'"):
        load_role_registry(path)


def test_eval_16_meeting_with_an_active_role_raises(tamper):
    def leak(document: dict[str, Any]) -> None:
        document["meetings"]["ES2004a"]["role"] = "glossary-discovery"

    with pytest.raises(HeldOutLeakageError, match="ES2004a"):
        load_role_registry(tamper(leak))


def test_eval_16_meeting_demoted_to_reserve_also_raises(tamper):
    """Even a non-active mislabel is a refusal: the confirmatory set is named
    explicitly so it cannot drift into the anonymous reserve."""

    def demote(document: dict[str, Any]) -> None:
        document["meetings"]["IS1009c"]["role"] = "held-out-reserve"
        document["role_counts"]["held-out-confirmatory"] -= 1
        document["role_counts"]["held-out-reserve"] += 1

    with pytest.raises(HeldOutLeakageError, match="IS1009c"):
        load_role_registry(tamper(demote))


def test_asr_eval_role_outside_the_dev_18_raises(tamper):
    def widen(document: dict[str, Any]) -> None:
        document["meetings"]["ES2002a"]["role"] = "asr-eval"
        document["role_counts"]["asr-eval"] += 1
        document["role_counts"]["glossary-discovery"] -= 1

    with pytest.raises(RoleRegistryError, match="exactly the frozen dev-18"):
        load_role_registry(tamper(widen))


def test_editing_the_frozen_split_lists_raises(tamper):
    def edit(document: dict[str, Any]) -> None:
        document["frozen_splits"]["eval_16"] = document["frozen_splits"]["eval_16"][:-1]

    with pytest.raises(RoleRegistryError, match="does not match FROZEN_EVAL_16"):
        load_role_registry(tamper(edit))


def test_unknown_role_value_raises(tamper):
    def bad_role(document: dict[str, Any]) -> None:
        document["meetings"]["ES2002a"]["role"] = "discovery-ish"

    with pytest.raises(RoleRegistryError, match="unknown role"):
        load_role_registry(tamper(bad_role))


def test_unsupported_schema_version_raises(tamper):
    def bump(document: dict[str, Any]) -> None:
        document["schema_version"] = "2.0.0"

    with pytest.raises(RoleRegistryError, match="unsupported AMI role registry schema_version"):
        load_role_registry(tamper(bump))


def test_missing_record_field_raises(tamper):
    def strip(document: dict[str, Any]) -> None:
        del document["meetings"]["ES2002a"]["qmsum_split"]

    with pytest.raises(RoleRegistryError, match="missing registry fields"):
        load_role_registry(tamper(strip))


def test_roster_size_disagreement_raises(tamper):
    def shrink(document: dict[str, Any]) -> None:
        document["corpus"]["n_meetings"] = 170

    with pytest.raises(RoleRegistryError, match="corpus.n_meetings"):
        load_role_registry(tamper(shrink))


def test_role_count_disagreement_raises(tamper):
    def miscount(document: dict[str, Any]) -> None:
        document["role_counts"]["qa-eval"] += 1

    with pytest.raises(RoleRegistryError, match="role_counts"):
        load_role_registry(tamper(miscount))


def test_qa_eval_meeting_without_questions_raises(tamper):
    def hollow(document: dict[str, Any]) -> None:
        target = next(
            m for m, r in document["meetings"].items() if r["role"] == "qa-eval"
        )
        document["meetings"][target]["meetingqa_questions"] = 0

    with pytest.raises(RoleRegistryError, match="no MeetingQA questions"):
        load_role_registry(tamper(hollow))


def test_missing_question_usage_block_raises(tamper):
    def drop_block(document: dict[str, Any]) -> None:
        del document["question_usage"]

    with pytest.raises(RoleRegistryError, match="question_usage"):
        load_role_registry(tamper(drop_block))


def test_question_usage_counts_disagreement_raises(tamper):
    def miscount(document: dict[str, Any]) -> None:
        document["question_usage"]["counts"]["usable-discovery"]["n_questions"] += 1

    with pytest.raises(RoleRegistryError, match="question_usage.counts"):
        load_role_registry(tamper(miscount))


def test_question_usage_meeting_count_disagreement_raises(tamper):
    def miscount(document: dict[str, Any]) -> None:
        document["question_usage"]["counts"]["untouchable"]["n_meetings"] -= 1

    with pytest.raises(RoleRegistryError, match="question_usage.counts"):
        load_role_registry(tamper(miscount))
