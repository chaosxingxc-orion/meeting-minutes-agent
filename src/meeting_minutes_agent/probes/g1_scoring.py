"""G1 floors campaign -- offline scoring path.

Read-only and OFFLINE, per this repository's established probe-scoring
discipline (:mod:`meeting_minutes_agent.probes.pattr_scoring`,
:mod:`meeting_minutes_agent.probes.pprompt_scoring`): every function here
scores already-collected replies against the AMI gold transcript / MeetingQA
gold answers; nothing performs a model or network call.

Per-slice transcribe scoring reuses
:func:`meeting_minutes_agent.probes.pattr_scoring.score_arm` (cpWER +
secondary confusion cost always; primary tcpWER-tcORC confusion cost only
when the hypothesis stream carries REAL per-segment timing) and the P-PROMPT
read's own ORC state-space guard
(:mod:`meeting_minutes_agent.probes.pprompt_scoring`'s ``orc_dp_bound`` /
``ORC_DP_BOUND_CAP``) verbatim -- never reimplemented.

Real-timing source (the draft prereg's binding timing rule, "take segment
timing from the diar layer... never a synthetic even-split timestamp"):
Z-turn/Z-oracle's transcribe-attribute reply is one ``<speaker>|<text>``
line per parsed segment; :func:`hypothesis_stream_from_slice_reply` aligns
each parsed line POSITIONALLY to the SAME-position entry of the slice's own
diar-layer turn table (``chunking.slicer.Slice.turns`` -- tool-diar for
Z-turn, oracle-diar for Z-oracle), taking that turn's REAL absolute
``(start, end)`` as the segment's timing. A parsed-line count that exceeds
the turn-table length is itself diagnostic (mirrors
``pattr_scoring.boundary_respect_diagnostic``'s own positional-comparison
approach): the first ``min(len(parsed), len(turns))`` lines are real-timed,
any surplus falls back to the whole-slice bounds, untimed -- never dropped.
Z-free/Z-nodiar carry no attribution at all (the transcribe-only head), so
their whole reply is ONE untimed, single-stream hypothesis segment tagged
with a placeholder speaker id -- the "attribution-free baseline" shape the
floors table names.

The deployment gap (Z-turn - Z-oracle) is published with a per-meeting-
CLUSTERED paired bootstrap CI, reimplemented here, stdlib-only, MINIMAL
(module scope: no replicate-diagnostics, no injectable ``statistic``
generality beyond what this one gap needs), because cross-repo imports from
the speech-aware-evidence-acquisition study are prohibited (CLAUDE.md).
The reimplemented core -- resample sample ids with replacement via
``random.Random(seed)``, recompute the statistic per replicate, report
sigma-hat and a percentile CI -- is the SAME primitive that study's own
``analysis/bootstrap.py::paired_cluster_bootstrap`` documents, read as a
pattern reference (path recorded here for audit), never imported.

No branch verdicts anywhere in this module (task discipline: "descriptive
floors"): every function returns numbers and disclosures, never a
winner/pass/fail classification the way ``pprompt_scoring.apply_winner_rule``
does for its own, different (comparison) mission.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..corpora.nxt.models import EvidenceLink
from ..heads.transcribe_attribute import parse_transcribe_attribute_response, parse_transcribe_only_response
from ..metrics.pins import MetricPins
from ..metrics.qa import QAExample
from ..metrics.qa_upstream import UpstreamMeetingQAScoreReport, upstream_meetingqa_score_examples
from ..metrics.saer_m import SaerMReport, SpeakerAttributionPrediction, compute_saer_m
from ..metrics.timestamps import PerSpeakerSegment
from .g1 import ARMS_WITH_ATTRIBUTION
from .pattr_scoring import HypothesisSegment, PattrArmScore, score_arm
from .pprompt_scoring import ORC_DP_BOUND_CAP, orc_dp_bound

__all__ = [
    "UNATTRIBUTED_SPEAKER",
    "hypothesis_stream_from_slice_reply",
    "SliceTranscribeScore",
    "score_transcribe_slice",
    "ArmMeetingScore",
    "aggregate_arm_meeting",
    "PooledArmScore",
    "aggregate_pooled",
    "meeting_saer_m",
    "QAExampleInput",
    "arm_qa_report",
    "PPROMPT_NOISE_REFERENCE_CPWER",
    "BootstrapResult",
    "paired_cluster_bootstrap",
    "DeploymentGapResult",
    "compute_deployment_gap",
    "OneShotOutputExistsError",
    "assert_one_shot_output_dir",
]

UNATTRIBUTED_SPEAKER = "UNATTRIBUTED"


# ---------------------------------------------------------------------------
# hypothesis streams
# ---------------------------------------------------------------------------


def hypothesis_stream_from_slice_reply(
    arm: str,
    raw_reply_text: str,
    slice_turns: Sequence[Any],
    *,
    slice_start: float,
    slice_end: float,
) -> tuple[HypothesisSegment, ...]:
    """One slice's hypothesis stream, dispatched by arm shape (module
    docstring). ``slice_turns`` is the slice's own
    :class:`~meeting_minutes_agent.chunking.slicer.SliceTurnEntry` sequence
    (``()`` is valid -- every parsed line then falls back to whole-slice
    bounds)."""

    if arm in ARMS_WITH_ATTRIBUTION:
        parsed = parse_transcribe_attribute_response(raw_reply_text)
        paired = min(len(parsed.segments), len(slice_turns))
        out = []
        for i, seg in enumerate(parsed.segments):
            if i < paired:
                turn = slice_turns[i]
                out.append(
                    HypothesisSegment(
                        speaker=seg.speaker, text=seg.text, start=turn.absolute_start, end=turn.absolute_end,
                        real_timing=True,
                    )
                )
            else:
                out.append(
                    HypothesisSegment(speaker=seg.speaker, text=seg.text, start=slice_start, end=slice_end, real_timing=False)
                )
        return tuple(out)

    text = parse_transcribe_only_response(raw_reply_text)
    if not text:
        return ()
    return (HypothesisSegment(speaker=UNATTRIBUTED_SPEAKER, text=text, start=slice_start, end=slice_end, real_timing=False),)


# ---------------------------------------------------------------------------
# per-slice scoring (ORC state-space guard, pprompt read's own pattern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SliceTranscribeScore:
    arm: str
    meeting_id: str
    slice_index: int
    cp_wer: float
    secondary_confusion_cost: float | None
    primary_confusion_cost: float | None
    grammar_compliance: float
    n_reference_segments: int
    n_hypothesis_segments: int
    hypothesis_empty: bool
    capped_reply: bool
    orc_refusal: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "meeting_id": self.meeting_id,
            "slice_index": self.slice_index,
            "cp_wer": self.cp_wer,
            "secondary_confusion_cost": self.secondary_confusion_cost,
            "primary_confusion_cost": self.primary_confusion_cost,
            "grammar_compliance": self.grammar_compliance,
            "n_reference_segments": self.n_reference_segments,
            "n_hypothesis_segments": self.n_hypothesis_segments,
            "hypothesis_empty": self.hypothesis_empty,
            "capped_reply": self.capped_reply,
            "orc_refusal": self.orc_refusal,
        }


def _grammar_compliance(arm: str, raw_reply_text: str) -> float:
    """1.0 for a transcribe-only arm (Z-free/Z-nodiar): there is no per-line
    grammar to violate -- the transcribe-only head's own instruction asks
    for plain free text (``heads.transcribe_attribute`` module docstring).
    For an attribution arm, the same "parsed segments / (parsed + malformed)"
    rate ``pprompt_scoring.grammar_compliance`` uses, reimplemented inline
    here (a two-line rule, not worth importing that module's own
    ``grammar_compliance`` just to avoid retyping it -- P-PROMPT's own
    docstring frames it as reusing ``parse_transcribe_attribute_response``
    directly, which this module already imports)."""

    if arm not in ARMS_WITH_ATTRIBUTION:
        return 1.0
    parsed = parse_transcribe_attribute_response(raw_reply_text)
    total_lines = len(parsed.segments) + len(parsed.malformed_lines)
    return (len(parsed.segments) / total_lines) if total_lines else 0.0


def is_capped_reply(usage: Mapping[str, Any], *, max_tokens: int) -> bool:
    """A reply hit the server's generation cap iff its reported
    ``completion_tokens`` equals the request's own ``max_tokens`` -- the
    same signature the P-PROMPT verdict's own capped-reply disclosure used
    (``docs/readiness/2026-08-18-pprompt-verdict.md`` SS4a: "eight replies
    hit the 1,024-token generation cap")."""

    return int(usage.get("completion_tokens", 0) or 0) == max_tokens


def score_transcribe_slice(
    arm: str,
    meeting_id: str,
    slice_index: int,
    reference: Sequence[PerSpeakerSegment],
    raw_reply_text: str,
    slice_turns: Sequence[Any],
    *,
    slice_start: float,
    slice_end: float,
    usage: Mapping[str, Any] | None = None,
    request_max_tokens: int | None = None,
    pins: MetricPins | None = None,
    orc_dp_bound_cap: float = ORC_DP_BOUND_CAP,
) -> SliceTranscribeScore:
    """Score one arm's one slice reply against its already-extracted gold
    reference stream. Never reimplements the WER-family math or the ORC
    feasibility guard -- both are the same committed functions
    ``pattr_scoring.score_arm``/``pprompt_scoring.orc_dp_bound`` this
    module's sibling probes already carry (module docstring)."""

    compliance = _grammar_compliance(arm, raw_reply_text)
    hypothesis = hypothesis_stream_from_slice_reply(
        arm, raw_reply_text, slice_turns, slice_start=slice_start, slice_end=slice_end
    )
    capped = is_capped_reply(usage or {}, max_tokens=request_max_tokens) if request_max_tokens else False

    if not hypothesis:
        return SliceTranscribeScore(
            arm=arm, meeting_id=meeting_id, slice_index=slice_index, cp_wer=1.0,
            secondary_confusion_cost=0.0, primary_confusion_cost=None, grammar_compliance=compliance,
            n_reference_segments=len(reference), n_hypothesis_segments=0, hypothesis_empty=True, capped_reply=capped,
        )

    # Parsed-segment structure for the ORC bound proxy (pprompt_scoring's
    # own proxy signature: a sequence of objects carrying .speaker/.text).
    class _Seg:
        def __init__(self, h: HypothesisSegment) -> None:
            self.speaker = h.speaker
            self.text = h.text

    bound = orc_dp_bound(len(reference), tuple(_Seg(h) for h in hypothesis))

    def _refused(reason: str) -> SliceTranscribeScore:
        from ..metrics.wer import compute_cp_wer

        hyp_psegs = tuple(h.as_per_speaker_segment() for h in hypothesis)
        cp = compute_cp_wer(reference, hyp_psegs, pins=pins)
        return SliceTranscribeScore(
            arm=arm, meeting_id=meeting_id, slice_index=slice_index, cp_wer=cp.error_rate,
            secondary_confusion_cost=None, primary_confusion_cost=None, grammar_compliance=compliance,
            n_reference_segments=len(reference), n_hypothesis_segments=len(hypothesis), hypothesis_empty=False,
            capped_reply=capped, orc_refusal=reason,
        )

    if bound > orc_dp_bound_cap:
        return _refused(
            f"ORC-WER not attempted: orc_dp_bound {bound:.3e} exceeds cap {orc_dp_bound_cap:.1e} "
            "(state-space infeasible; pprompt_scoring's own guard, reused verbatim)"
        )
    try:
        arm_score: PattrArmScore = score_arm(arm, meeting_id, reference, hypothesis, pins=pins)
    except MemoryError:
        return _refused(f"ORC-WER MemoryError at orc_dp_bound {bound:.3e} (host memory pressure at read time)")

    return SliceTranscribeScore(
        arm=arm,
        meeting_id=meeting_id,
        slice_index=slice_index,
        cp_wer=arm_score.cp_wer.error_rate,
        secondary_confusion_cost=arm_score.secondary_confusion_cost.confusion_cost,
        primary_confusion_cost=(
            arm_score.primary_confusion_cost.confusion_cost if arm_score.primary_confusion_cost is not None else None
        ),
        grammar_compliance=compliance,
        n_reference_segments=len(reference),
        n_hypothesis_segments=len(hypothesis),
        hypothesis_empty=False,
        capped_reply=capped,
    )


# ---------------------------------------------------------------------------
# per (arm, meeting) and pooled aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmMeetingScore:
    arm: str
    meeting_id: str
    slices: tuple[SliceTranscribeScore, ...]

    def __post_init__(self) -> None:
        if not self.slices:
            raise ValueError(f"ArmMeetingScore for {self.arm!r}/{self.meeting_id!r} requires at least one slice")
        mismatched = [(s.arm, s.meeting_id) for s in self.slices if s.arm != self.arm or s.meeting_id != self.meeting_id]
        if mismatched:
            raise ValueError(f"ArmMeetingScore for {self.arm!r}/{self.meeting_id!r} received mismatched slice(s)")

    @property
    def n_slices(self) -> int:
        return len(self.slices)

    @property
    def mean_cp_wer(self) -> float:
        return statistics.fmean(s.cp_wer for s in self.slices)

    @property
    def n_confusion_refused(self) -> int:
        return sum(1 for s in self.slices if s.secondary_confusion_cost is None)

    @property
    def mean_secondary_confusion_cost(self) -> float | None:
        values = [s.secondary_confusion_cost for s in self.slices if s.secondary_confusion_cost is not None]
        return statistics.fmean(values) if values else None

    @property
    def n_primary_computable(self) -> int:
        return sum(1 for s in self.slices if s.primary_confusion_cost is not None)

    @property
    def mean_primary_confusion_cost(self) -> float | None:
        values = [s.primary_confusion_cost for s in self.slices if s.primary_confusion_cost is not None]
        return statistics.fmean(values) if values else None

    @property
    def mean_grammar_compliance(self) -> float:
        return statistics.fmean(s.grammar_compliance for s in self.slices)

    @property
    def n_capped_replies(self) -> int:
        return sum(1 for s in self.slices if s.capped_reply)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "meeting_id": self.meeting_id,
            "n_slices": self.n_slices,
            "mean_cp_wer": self.mean_cp_wer,
            "mean_secondary_confusion_cost": self.mean_secondary_confusion_cost,
            "n_confusion_refused": self.n_confusion_refused,
            "mean_primary_confusion_cost": self.mean_primary_confusion_cost,
            "n_primary_computable": self.n_primary_computable,
            "mean_grammar_compliance": self.mean_grammar_compliance,
            "n_capped_replies": self.n_capped_replies,
            "slices": [s.to_dict() for s in self.slices],
        }


def aggregate_arm_meeting(arm: str, meeting_id: str, slice_scores: Sequence[SliceTranscribeScore]) -> ArmMeetingScore:
    return ArmMeetingScore(arm=arm, meeting_id=meeting_id, slices=tuple(slice_scores))


@dataclass(frozen=True)
class PooledArmScore:
    """One arm's pooled numbers over every scored meeting -- a plain,
    equal-weighted mean over the per-meeting means (never a slice-weighted
    mean, so one long meeting cannot dominate the pooled figure)."""

    arm: str
    per_meeting: tuple[ArmMeetingScore, ...]

    @property
    def n_meetings(self) -> int:
        return len(self.per_meeting)

    @property
    def mean_cp_wer(self) -> float:
        return statistics.fmean(m.mean_cp_wer for m in self.per_meeting)

    @property
    def mean_secondary_confusion_cost(self) -> float | None:
        values = [m.mean_secondary_confusion_cost for m in self.per_meeting if m.mean_secondary_confusion_cost is not None]
        return statistics.fmean(values) if values else None

    @property
    def total_capped_replies(self) -> int:
        return sum(m.n_capped_replies for m in self.per_meeting)

    @property
    def total_slices(self) -> int:
        return sum(m.n_slices for m in self.per_meeting)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "n_meetings": self.n_meetings,
            "mean_cp_wer": self.mean_cp_wer,
            "mean_secondary_confusion_cost": self.mean_secondary_confusion_cost,
            "total_capped_replies": self.total_capped_replies,
            "total_slices": self.total_slices,
            "per_meeting": {m.meeting_id: m.to_dict() for m in self.per_meeting},
        }


def aggregate_pooled(arm: str, per_meeting: Sequence[ArmMeetingScore]) -> PooledArmScore:
    mismatched = [m.arm for m in per_meeting if m.arm != arm]
    if mismatched:
        raise ValueError(f"aggregate_pooled({arm!r}, ...) received scores tagged {mismatched}")
    return PooledArmScore(arm=arm, per_meeting=tuple(per_meeting))


# ---------------------------------------------------------------------------
# SAER-M (minutes) -- scoreable only where the meeting carries evidence links
# ---------------------------------------------------------------------------


def meeting_saer_m(
    evidence_links: Sequence[EvidenceLink], predictions: Sequence[SpeakerAttributionPrediction]
) -> SaerMReport | None:
    """SAER-M for one meeting, or ``None`` if the meeting carries no
    evidence links at all (SAER-M is scoreable on 12 of the 18 ASR-eval
    meetings; the un-scoreable six -- the IB meetings -- lack the
    extractive+summlink layer, which is exactly what
    ``resolved.evidence_links`` is empty for -- a structural criterion, not
    a hardcoded meeting-id list)."""

    if not evidence_links:
        return None
    return compute_saer_m(evidence_links, predictions)


# ---------------------------------------------------------------------------
# QA (Z-turn / Z-oracle only) -- the reimplemented upstream scorer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QAExampleInput:
    """One capped QA question's gold + predicted answer, the shared input
    :func:`arm_qa_report` folds into :class:`~meeting_minutes_agent.metrics.qa.QAExample`."""

    example_id: str
    reference_spans: tuple[str, ...]
    prediction_spans: tuple[str, ...]


def arm_qa_report(examples: Sequence[QAExampleInput]) -> UpstreamMeetingQAScoreReport:
    """The registered QA scorer -- the reimplemented upstream scorer
    (max-over-alternatives, ``metrics.qa_upstream``) over one arm's capped
    question set."""

    qa_examples = tuple(
        QAExample(example_id=e.example_id, reference_spans=e.reference_spans, prediction_spans=e.prediction_spans)
        for e in examples
    )
    return upstream_meetingqa_score_examples(qa_examples)


# ---------------------------------------------------------------------------
# the P-PROMPT single-run noise reference
# ---------------------------------------------------------------------------

#: The P-PROMPT server-state spread cited as the single-run noise reference
#: (floors prereg SS4 / pprompt-verdict.md SS4b: "T1-A1 vs T1-A2/A3 -- same
#: request bytes, different server state -- ... mean-cpWER spread of
#: 0.0850"). No comparison in this campaign's read is narrated as real
#: unless its CI excludes zero.
PPROMPT_NOISE_REFERENCE_CPWER = 0.085


# ---------------------------------------------------------------------------
# per-meeting-clustered paired bootstrap (minimal stdlib reimplementation --
# module docstring: pattern reference only, never imported cross-repo)
# ---------------------------------------------------------------------------

DEFAULT_BOOTSTRAP_N_REPLICATES = 10_000
DEFAULT_BOOTSTRAP_SEED = 20260818
DEFAULT_BOOTSTRAP_CI_LEVEL = 0.90


class BootstrapError(RuntimeError):
    """Malformed bootstrap input -- never raised for a legitimate data
    shape."""


@dataclass(frozen=True)
class BootstrapResult:
    point_estimate: float
    replicates: tuple[float, ...]
    sigma_hat: float
    ci_low: float
    ci_high: float
    ci_level: float
    n_replicates: int
    seed: int

    @property
    def ci(self) -> tuple[float, float]:
        return (self.ci_low, self.ci_high)

    @property
    def excludes_zero(self) -> bool:
        """``True`` iff the entire CI lies strictly on one side of zero --
        the floors prereg's own "no comparison is narrated as real unless
        its CI excludes zero" rule, exposed as a plain boolean so a caller
        never has to re-derive it from ``ci_low``/``ci_high`` itself."""

        return self.ci_low > 0.0 or self.ci_high < 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_estimate": self.point_estimate,
            "sigma_hat": self.sigma_hat,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "ci_level": self.ci_level,
            "n_replicates": self.n_replicates,
            "seed": self.seed,
            "excludes_zero": self.excludes_zero,
        }


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        raise BootstrapError("cannot take a percentile of zero values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    if fraction <= 0.0:
        return sorted_values[0]
    if fraction >= 1.0:
        return sorted_values[-1]
    position = fraction * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    return sorted_values[lower_index] * (1.0 - weight) + sorted_values[upper_index] * weight


def paired_cluster_bootstrap(
    *,
    sample_ids: Sequence[str],
    statistic: Any,
    n_replicates: int = DEFAULT_BOOTSTRAP_N_REPLICATES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    ci_level: float = DEFAULT_BOOTSTRAP_CI_LEVEL,
) -> BootstrapResult:
    """A per-sample paired CLUSTER bootstrap: resample ``sample_ids`` WITH
    replacement (a fresh length-``len(sample_ids)`` multiset per replicate),
    recompute ``statistic`` on each resampled id list, and report sigma-hat
    (population stdev of the replicate distribution) plus a percentile
    ``ci_level`` CI. PAIRED: the SAME resampled multiset is handed to
    ``statistic`` once, so a caller whose own ``statistic`` reads per-sample
    data from BOTH arms internally (this module's own
    :func:`compute_deployment_gap`) applies the identical resampled draw to
    both -- a meeting drawn twice contributes twice to EVERY arm's own
    replicate score, preserving the pairing the gap depends on. Deterministic:
    ``random.Random(seed)``, drawn via ``randrange`` once per resampled slot,
    in order."""

    if not sample_ids:
        raise BootstrapError("paired_cluster_bootstrap requires at least one sample id")
    if isinstance(n_replicates, bool) or not isinstance(n_replicates, int) or n_replicates <= 0:
        raise BootstrapError(f"n_replicates must be a positive integer, got {n_replicates!r}")
    if not (0.0 < ci_level < 1.0):
        raise BootstrapError(f"ci_level must be strictly between 0 and 1, got {ci_level!r}")

    ids = tuple(sample_ids)
    point_estimate = float(statistic(ids))

    rng = random.Random(seed)
    n = len(ids)
    replicates: list[float] = []
    for _ in range(n_replicates):
        resampled = tuple(ids[rng.randrange(n)] for _ in range(n))
        replicates.append(float(statistic(resampled)))

    sigma_hat = statistics.pstdev(replicates) if len(replicates) > 1 else 0.0
    ordered = sorted(replicates)
    tail = (1.0 - ci_level) / 2.0
    ci_low = _percentile(ordered, tail)
    ci_high = _percentile(ordered, 1.0 - tail)

    return BootstrapResult(
        point_estimate=point_estimate,
        replicates=tuple(replicates),
        sigma_hat=sigma_hat,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_level=ci_level,
        n_replicates=n_replicates,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# the deployment gap: Z-turn - Z-oracle, per-meeting-clustered bootstrap CI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeploymentGapResult:
    """Z-turn minus Z-oracle on pooled mean cpWER, with a per-meeting-
    clustered bootstrap CI (floors prereg SS4). Descriptive only -- no
    verdict field (module docstring)."""

    metric: str
    gap: BootstrapResult
    noise_reference_cp_wer: float = PPROMPT_NOISE_REFERENCE_CPWER

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "gap": self.gap.to_dict(),
            "noise_reference_cp_wer": self.noise_reference_cp_wer,
        }


def compute_deployment_gap(
    z_turn_by_meeting: Mapping[str, float],
    z_oracle_by_meeting: Mapping[str, float],
    *,
    metric: str = "cp_wer",
    n_replicates: int = DEFAULT_BOOTSTRAP_N_REPLICATES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    ci_level: float = DEFAULT_BOOTSTRAP_CI_LEVEL,
) -> DeploymentGapResult:
    """The deployment gap: mean(Z-turn per-meeting ``metric``) minus
    mean(Z-oracle per-meeting ``metric``), bootstrapped over the meetings
    common to both maps (clustered at meeting granularity -- every slice/
    request inside one meeting resamples together, never independently).
    Raises if the two maps do not share the same meeting-id set: a partial
    gap over a silently-mismatched roster is a defect, not a floor."""

    if set(z_turn_by_meeting) != set(z_oracle_by_meeting):
        raise BootstrapError(
            "compute_deployment_gap requires Z-turn and Z-oracle to cover the SAME meeting set; "
            f"z_turn only={sorted(set(z_turn_by_meeting) - set(z_oracle_by_meeting))}, "
            f"z_oracle only={sorted(set(z_oracle_by_meeting) - set(z_turn_by_meeting))}"
        )
    meeting_ids = sorted(z_turn_by_meeting)

    def _statistic(resampled_ids: Sequence[str]) -> float:
        turn_mean = statistics.fmean(z_turn_by_meeting[m] for m in resampled_ids)
        oracle_mean = statistics.fmean(z_oracle_by_meeting[m] for m in resampled_ids)
        return turn_mean - oracle_mean

    gap = paired_cluster_bootstrap(
        sample_ids=meeting_ids, statistic=_statistic, n_replicates=n_replicates, seed=seed, ci_level=ci_level
    )
    return DeploymentGapResult(metric=metric, gap=gap)


# ---------------------------------------------------------------------------
# one-shot idempotence guard
# ---------------------------------------------------------------------------


class OneShotOutputExistsError(RuntimeError):
    """Raised by :func:`assert_one_shot_output_dir` when the read's output
    directory already carries a prior read's output -- mirrors
    ``pprompt_scoring.assert_one_shot_output_dir``'s own one-shot-read
    discipline, reimplemented here (rather than imported) so this module has
    no import-time dependency on P-PROMPT's own scoring path beyond the ORC
    guard it explicitly documents reusing."""


def assert_one_shot_output_dir(
    out_dir: Path | str, *, filenames: Sequence[str] = ("verdict.json",), force: bool = False
) -> None:
    if force:
        return
    resolved = Path(out_dir)
    existing = [name for name in filenames if (resolved / name).exists()]
    if existing:
        raise OneShotOutputExistsError(
            f"{resolved} already carries prior read output {existing} -- the G1 floors read is "
            "one-shot; pass force=True (--force) only if you intend to replace a committed read"
        )
