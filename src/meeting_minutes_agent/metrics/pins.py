"""``MetricPins`` -- the content-hashed pin record for the attribution/WER
metric family.

Per the 2026-08-17 founding workplan (E5 row) and the deep-check registered
changes (umbrella
``wiki/survey/workbench/2026-08-17-meeting-agent-direction/DEEP-CHECK-SYNTHESIS.md``
Section 3, item 4): the meeteval version and every parameter that changes a
WER-family number (collar, pseudo-word timing mode, segment sort order) must
be pinned and content-hashed into every result, not left as ambient library
defaults. Every wrapper in :mod:`.wer` accepts a ``MetricPins`` and stamps
its hash onto the result it returns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

# Deep-check binding: PRIMARY confusion cost = tcpWER - tcORC-WER at collar 5s.
DEFAULT_COLLAR_SECONDS: float = 5.0

# meeteval 0.4.3 defaults for `time_constrained.tcp_word_error_rate` /
# `time_constrained_orc_wer` -- pinned explicitly rather than left implicit,
# so a future meeteval upgrade changing its defaults cannot silently move a
# published number. See docs/readiness/... for the 2026-08-17 probe that
# read these defaults off the installed 0.4.3 signature.
DEFAULT_REFERENCE_PSEUDO_WORD_TIMING: str = "character_based"
DEFAULT_HYPOTHESIS_PSEUDO_WORD_TIMING: str = "character_based_points"
DEFAULT_SEGMENT_SORT: str = "segment"


@dataclass(frozen=True)
class MetricPins:
    """One content-hashable record of the meeteval version and parameters a
    WER-family result was computed with.

    ``collar_seconds``, ``reference_pseudo_word_level_timing``, and
    ``hypothesis_pseudo_word_level_timing`` only affect the time-constrained
    metrics (tcpWER, tcORC-WER); the non-time-constrained metrics (cpWER,
    ORC-WER) ignore them. They still live on the same pins record so a
    single hash covers "how was this whole result set computed" rather than
    forcing every caller to carry two pin objects.
    """

    meeteval_version: str
    collar_seconds: float = DEFAULT_COLLAR_SECONDS
    reference_pseudo_word_level_timing: str = DEFAULT_REFERENCE_PSEUDO_WORD_TIMING
    hypothesis_pseudo_word_level_timing: str = DEFAULT_HYPOTHESIS_PSEUDO_WORD_TIMING
    reference_sort: str = DEFAULT_SEGMENT_SORT
    hypothesis_sort: str = DEFAULT_SEGMENT_SORT

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def content_hash(self) -> str:
        """SHA-256 of the canonical JSON form of this pin record, via the
        same ``config_hash`` helper E1's run receipts use -- one hashing
        convention across this repository."""

        from meeting_minutes_agent.runreceipt import config_hash

        return config_hash(self.to_dict())


def installed_meeteval_version() -> str:
    """Read ``meeteval.__version__`` off the installed package. Raises
    ``ImportError`` if meeteval is not installed -- callers that need a
    pins object without touching meeteval (e.g. building one to hash for a
    receipt before any metric is computed) should catch this and fall back
    to a pinned literal, never silently substitute ``"unknown"``."""

    import meeteval

    return getattr(meeteval, "__version__", "unknown")


def default_metric_pins(*, meeteval_version: str | None = None) -> MetricPins:
    """Build a :class:`MetricPins` using this repository's pinned defaults,
    reading the installed meeteval version unless one is supplied
    explicitly (e.g. to reconstruct a past receipt's pins for comparison
    without needing that meeteval version installed)."""

    version = meeteval_version if meeteval_version is not None else installed_meeteval_version()
    return MetricPins(meeteval_version=version)
