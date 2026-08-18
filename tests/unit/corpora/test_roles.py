"""Tests for :mod:`meeting_minutes_agent.corpora.roles`.

Two jobs. First, the committed registry
(``configs/corpora/ami-role-registry.json``) is itself machine-checked here:
the hard constraints from the G1 precondition -- one role per meeting, the
assignment total over the roster, nothing in the frozen eval-16 holding an
active role -- are asserted against the real file, so a bad edit to the data
fails the suite. Second, every fail-closed refusal is exercised on a tampered
copy: the loader must raise rather than degrade.
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
    RoleRegistryError,
    UnknownMeetingError,
    default_registry_path,
    load_role_registry,
    quarantined_question_ids,
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
EXPECTED_QUARANTINED_MEETINGS = 124
EXPECTED_QUARANTINED_QUESTIONS = 5817


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
# the committed registry
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
# quarantine
# ---------------------------------------------------------------------------


def test_quarantine_is_every_meetingqa_question_outside_qa_eval(registry: AmiRoleRegistry):
    assert len(registry.quarantined_meetings) == EXPECTED_QUARANTINED_MEETINGS
    assert registry.quarantined_question_count == EXPECTED_QUARANTINED_QUESTIONS
    for meeting in registry.quarantined_meetings:
        record = registry.record(meeting)
        assert record.meetingqa_questions > 0
        assert record.role is not MeetingRole.QA_EVAL


def test_usable_questions_are_exactly_the_qa_eval_ones(registry: AmiRoleRegistry):
    total = sum(r.meetingqa_questions for r in registry.meetings.values())
    usable = sum(
        r.meetingqa_questions
        for r in registry.meetings.values()
        if r.role is MeetingRole.QA_EVAL
    )
    assert total == EXPECTED_MEETINGQA_TOTAL
    assert usable == EXPECTED_MEETINGQA_TOTAL - EXPECTED_QUARANTINED_QUESTIONS
    assert usable + registry.quarantined_question_count == total


def test_assert_question_usable_admits_qa_eval_and_refuses_the_rest(registry: AmiRoleRegistry):
    qa_meeting = registry.meetings_with_role(MeetingRole.QA_EVAL)[0]
    registry.assert_question_usable(qa_meeting)
    assert not registry.is_quarantined(qa_meeting)

    for role in (MeetingRole.ASR_EVAL, MeetingRole.GLOSSARY_DISCOVERY, MeetingRole.HELD_OUT_CONFIRMATORY):
        straddling = next(
            m
            for m in registry.meetings_with_role(role)
            if registry.record(m).meetingqa_questions > 0
        )
        with pytest.raises(QuarantinedQuestionError, match="QUARANTINED"):
            registry.assert_question_usable(straddling)
        assert registry.is_quarantined(straddling)


def test_quarantined_question_ids_filters_a_question_stream(registry: AmiRoleRegistry):
    qa_meeting = registry.meetings_with_role(MeetingRole.QA_EVAL)[0]
    flight_meeting = registry.meetings_with_role(MeetingRole.ASR_EVAL)[0]
    questions = [
        {"id": "keep-1", "title": qa_meeting},
        {"id": "drop-1", "title": flight_meeting},
        {"id": "drop-2", "title": FROZEN_EVAL_16[0]},
    ]
    assert quarantined_question_ids(registry, questions) == ("drop-1", "drop-2")


def test_quarantined_question_ids_refuses_an_unknown_meeting(registry: AmiRoleRegistry):
    with pytest.raises(UnknownMeetingError):
        quarantined_question_ids(registry, [{"id": "q", "title": "NOPE999z"}])


# ---------------------------------------------------------------------------
# fail-closed refusals
# ---------------------------------------------------------------------------


def test_unknown_meeting_raises_everywhere(registry: AmiRoleRegistry):
    for call in (
        registry.record,
        registry.role_of,
        registry.assert_exposable,
        registry.assert_question_usable,
        registry.is_quarantined,
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
        document["quarantine"]["meetings"] = [
            e for e in document["quarantine"]["meetings"] if e["meeting_id"] != target
        ]

    with pytest.raises(RoleRegistryError, match="no MeetingQA questions"):
        load_role_registry(tamper(hollow))


def test_dropping_a_quarantine_entry_raises(tamper):
    def drop(document: dict[str, Any]) -> None:
        entries = document["quarantine"]["meetings"]
        removed = entries.pop()
        document["quarantine"]["n_questions"] -= removed["n_questions"]
        document["quarantine"]["n_meetings"] -= 1

    with pytest.raises(RoleRegistryError, match="declared quarantine does not match"):
        load_role_registry(tamper(drop))


def test_understating_the_quarantined_question_count_raises(tamper):
    def understate(document: dict[str, Any]) -> None:
        document["quarantine"]["n_questions"] -= 1

    with pytest.raises(RoleRegistryError, match="quarantine.n_questions"):
        load_role_registry(tamper(understate))


def test_quarantine_entry_disagreeing_with_its_record_raises(tamper):
    def skew(document: dict[str, Any]) -> None:
        """Move a question from one quarantine entry to another: the declared
        total still matches, so only the per-entry check can catch it."""

        entries = document["quarantine"]["meetings"]
        entries[0]["n_questions"] += 1
        entries[1]["n_questions"] -= 1

    with pytest.raises(RoleRegistryError, match="disagrees with its record"):
        load_role_registry(tamper(skew))
