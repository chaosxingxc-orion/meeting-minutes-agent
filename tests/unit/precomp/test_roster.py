"""Tests for :mod:`meeting_minutes_agent.precomp.roster`: the two PRECOMP
wave rosters and the fail-closed exposure exclusion gate.

Uses the REAL committed AMI role registry (``configs/corpora/ami-role-
registry.json``) throughout -- these tests exist precisely to check this
module's rosters against that committed data, so a synthetic registry
fixture would defeat the point. ``EN2001b`` is the concrete regression case
motivating the module's double-axis filter (module docstring): role
``held-out-reserve`` (audio-unexposable) but MeetingQA question-usage
policy ``usable-discovery`` -- if wave-2's roster were built from the
question-usage axis alone, this meeting would leak in."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.corpora.roles import (
    FROZEN_DEV_18,
    FROZEN_EVAL_16,
    HeldOutLeakageError,
    UnknownMeetingError,
    load_role_registry,
)
from meeting_minutes_agent.precomp.roster import (
    PrecompRosterError,
    assert_wave_roster_admissible,
    default_wave_meetings,
    dev18_roster,
    usable_discovery_exposable_roster,
    wave2_roster,
)

# The registry file I/O is real but cheap; load it once per test module run
# via a fixture rather than the (equally real) default inside every
# function under test, so a failure in one test doesn't also re-read it.
_REGISTRY = load_role_registry()


# ---------------------------------------------------------------------------
# wave-1: dev-18
# ---------------------------------------------------------------------------


class TestDev18Roster:
    def test_matches_frozen_dev_18_exactly(self):
        assert dev18_roster(_REGISTRY) == tuple(sorted(FROZEN_DEV_18))

    def test_is_sorted(self):
        roster = dev18_roster(_REGISTRY)
        assert roster == tuple(sorted(roster))

    def test_default_registry_argument_works_too(self):
        # No registry passed -- exercises the load_role_registry() default
        # path, not just the pre-loaded fixture.
        assert dev18_roster() == tuple(sorted(FROZEN_DEV_18))


# ---------------------------------------------------------------------------
# wave-2: usable-discovery, exposable, minus dev-18
# ---------------------------------------------------------------------------


class TestWave2Roster:
    def test_disjoint_from_dev_18(self):
        roster = wave2_roster(_REGISTRY)
        assert set(roster).isdisjoint(FROZEN_DEV_18)

    def test_disjoint_from_eval_16(self):
        roster = wave2_roster(_REGISTRY)
        assert set(roster).isdisjoint(FROZEN_EVAL_16)

    def test_every_meeting_is_exposable(self):
        roster = wave2_roster(_REGISTRY)
        for meeting_id in roster:
            _REGISTRY.assert_exposable(meeting_id)  # must not raise

    def test_excludes_en2001b_the_usable_discovery_held_out_reserve_meeting(self):
        # Regression case (module docstring): EN2001b carries MeetingQA
        # question-usage policy usable-discovery but AMI MeetingRole
        # held-out-reserve -- it must NOT appear in the audio-exposure
        # roster even though it appears in the pure question-usage set.
        assert "EN2001b" in _REGISTRY.usable_discovery_questions()
        assert _REGISTRY.role_of("EN2001b").value == "held-out-reserve"
        assert "EN2001b" not in wave2_roster(_REGISTRY)
        assert "EN2001b" not in usable_discovery_exposable_roster(_REGISTRY)

    def test_nonempty_and_reasonably_sized(self):
        # ~83 per the registration's own rough estimate (prereg SS2); the
        # exact figure is a set-difference computation this test pins
        # loosely (a wide, sanity-check band) rather than hard-coding the
        # precise count, which would break on any registry data update.
        roster = wave2_roster(_REGISTRY)
        assert 50 <= len(roster) <= 130

    def test_is_sorted_and_deduplicated(self):
        roster = wave2_roster(_REGISTRY)
        assert roster == tuple(sorted(set(roster)))


class TestUsableDiscoveryExposableRoster:
    def test_every_member_carries_an_active_role(self):
        from meeting_minutes_agent.corpora.roles import ACTIVE_ROLES

        roster = usable_discovery_exposable_roster(_REGISTRY)
        for meeting_id in roster:
            assert _REGISTRY.role_of(meeting_id) in ACTIVE_ROLES

    def test_every_member_is_usable_discovery(self):
        from meeting_minutes_agent.corpora.roles import QuestionUsagePolicy

        roster = usable_discovery_exposable_roster(_REGISTRY)
        for meeting_id in roster:
            assert _REGISTRY.question_usage_policy_of(meeting_id) is QuestionUsagePolicy.USABLE_DISCOVERY


# ---------------------------------------------------------------------------
# default_wave_meetings
# ---------------------------------------------------------------------------


class TestDefaultWaveMeetings:
    def test_wave_1_is_dev18_roster(self):
        assert default_wave_meetings(1, _REGISTRY) == dev18_roster(_REGISTRY)

    def test_wave_2_is_wave2_roster(self):
        assert default_wave_meetings(2, _REGISTRY) == wave2_roster(_REGISTRY)

    def test_unknown_wave_raises(self):
        with pytest.raises(PrecompRosterError):
            default_wave_meetings(3, _REGISTRY)


# ---------------------------------------------------------------------------
# assert_wave_roster_admissible: the fail-closed exclusion gate
# ---------------------------------------------------------------------------


class TestAssertWaveRosterAdmissible:
    def test_passes_for_the_full_dev18_roster(self):
        assert_wave_roster_admissible(dev18_roster(_REGISTRY), _REGISTRY)  # must not raise

    def test_passes_for_the_full_wave2_roster(self):
        assert_wave_roster_admissible(wave2_roster(_REGISTRY), _REGISTRY)  # must not raise

    def test_refuses_a_fixture_wave_containing_an_eval_16_meeting(self):
        with pytest.raises(HeldOutLeakageError):
            assert_wave_roster_admissible(["ES2011a", "ES2004a"], _REGISTRY)  # ES2004a is eval-16

    def test_refuses_every_eval_16_meeting_individually(self):
        for meeting_id in FROZEN_EVAL_16:
            with pytest.raises(HeldOutLeakageError):
                assert_wave_roster_admissible([meeting_id], _REGISTRY)

    def test_refuses_a_held_out_reserve_meeting_even_though_its_questions_are_usable_discovery(self):
        # EN2001b again: this is the "reserved sets EXCLUDED... with a
        # fail-closed check" half of the design -- the gate itself, not
        # just roster construction, refuses it.
        with pytest.raises(HeldOutLeakageError):
            assert_wave_roster_admissible(["EN2001b"], _REGISTRY)

    def test_refuses_an_unknown_meeting_id(self):
        with pytest.raises(UnknownMeetingError):
            assert_wave_roster_admissible(["NOT-A-REAL-MEETING"], _REGISTRY)

    def test_empty_list_is_trivially_admissible(self):
        assert_wave_roster_admissible([], _REGISTRY)  # must not raise
