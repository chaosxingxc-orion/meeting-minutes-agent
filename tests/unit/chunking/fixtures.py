"""Synthetic meeting fixtures for the chunking engine's tests -- tiny,
hand-checkable, no corpus bytes involved.

Two shapes:

- :func:`short_meeting_segments` -- ~20 minutes of speaker-tagged segments,
  well under the default 40-minute window cap. Exercises ``single_pass``.
- :func:`long_meeting_segments` -- ~70 minutes, deliberately crossing the
  cap twice, with topic marks placed near (but not exactly at) each
  1-hour-mark-ish crossing so boundary snapping has a real decision to
  make; one crossing has NO nearby topic mark at all, to exercise the
  plain-duration fallback.
"""

from __future__ import annotations

from meeting_minutes_agent.chunking.models import Segment

SPEAKER_A = "A"
SPEAKER_B = "B"


def short_meeting_segments() -> tuple[Segment, ...]:
    """~18 minutes, two speakers, five segments -- fits comfortably under
    any window cap >= 1080s."""

    return (
        Segment("s0", SPEAKER_A, 0.0, 300.0, "Welcome everyone to the meeting."),
        Segment("s1", SPEAKER_B, 300.0, 600.0, "Thanks, let's review the agenda."),
        Segment("s2", SPEAKER_A, 600.0, 780.0, "First item is the budget."),
        Segment("s3", SPEAKER_B, 780.0, 960.0, "I agree with the proposal."),
        Segment("s4", SPEAKER_A, 960.0, 1080.0, "Let's move to close the meeting."),
    )


def long_meeting_segments(window_cap_s: float = 2400.0) -> tuple[Segment, ...]:
    """~70 minutes (4200s) of 10-minute segments, crossing a 2400s
    (40-minute) window cap twice: once near a segment whose topic mark
    sits a little before the segment's end (boundary snapping has a real
    choice), and once with topic marks present but far from the crossing
    entirely absent near the SECOND crossing (plain-duration fallback)."""

    segs = []
    t = 0.0
    for i in range(7):
        start = t
        end = t + 600.0
        segs.append(Segment(f"s{i}", SPEAKER_A if i % 2 == 0 else SPEAKER_B, start, end, f"Segment number {i}."))
        t = end
    return tuple(segs)


def long_meeting_topic_marks() -> tuple[float, ...]:
    """Topic marks for :func:`long_meeting_segments`: one mark at 2350s
    (inside segment s3 = [1800, 2400), close to but before the 2400s cap
    crossing caused by s3 ending at 2400 exactly -- wait, the crossing is
    caused by whichever segment's END first reaches/exceeds the cap from
    chunk start 0.0, which is s3 (ends at 2400.0, elapsed==2400==cap).
    A mark at 2350 inside s3 gives boundary snapping something to snap to
    that is closer to the 2400 target than the segment's own end. No marks
    are placed anywhere near the second crossing (chunk 2 starts at 2400
    and would cross again around 4800, but the episode ends at 4200, so
    there IS no second crossing -- the fallback case is exercised by a
    SEPARATE fixture, see :func:`long_meeting_segments_no_marks_at_second_boundary`.
    """

    return (2350.0,)


def long_meeting_segments_two_crossings() -> tuple[Segment, ...]:
    """~100 minutes (6000s) of 10-minute segments -- crosses a 2400s cap
    TWICE, so both a topic-mark snap and a plain-duration fallback can be
    exercised in the same plan."""

    segs = []
    t = 0.0
    for i in range(10):
        start = t
        end = t + 600.0
        segs.append(Segment(f"s{i}", SPEAKER_A if i % 2 == 0 else SPEAKER_B, start, end, f"Segment number {i}."))
        t = end
    return tuple(segs)


def two_crossings_topic_marks() -> tuple[float, ...]:
    """One topic mark near the FIRST crossing (inside s3 = [1800, 2400)),
    at 2350s. NO marks anywhere near the second crossing (which lands
    inside s7 = [4200, 4800), target ~4800) -- so the second boundary must
    fall back to plain-duration (the causing segment's own end)."""

    return (2350.0,)
