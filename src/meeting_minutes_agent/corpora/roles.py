"""AMI role registry: exactly one role per AMI meeting, machine-checked.

The G1 precondition (``docs/readiness/2026-08-18-g1-preregistration-draft.md``
§5, from the 2026-08-17 deep check): *an AMI role registry -- one role per
meeting: glossary-discovery / ASR-eval / QA-eval, machine-checked
fail-closed -- committed BEFORE flight.* This module is the checked half;
``configs/corpora/ami-role-registry.json`` is the data half, and
``scripts/build_ami_role_registry.py`` regenerates it from shipped bytes.

Why a registry at all. Three corpora annotate the *same* 171 AMI meetings
with different, mutually unaware splits: this repository's frozen ASR
partition (dev 18 / eval 16 / held-out 137, see
``docs/readiness/2026-08-17-ami-split-freeze-proposal.md``), MeetingQA's own
meeting-level split, and QMSum's Product split. Overlap is not hypothetical:
every one of our dev-18 and eval-16 meetings also carries MeetingQA
questions, scattered across all three MeetingQA splits. Without a registry a
meeting could serve as the ASR flight set and as QA evaluation material at
once, and confirmatory meetings could be exposed through a side corpus. The
registry closes that by construction: one role per meeting, total over the
roster, with the reserved roles unexposable.

Fail-closed means the loader refuses a registry it cannot vouch for rather
than degrading to a permissive default. The three refusals the deep check
named explicitly -- unknown meeting, duplicate role, eval-16 leakage -- are
:class:`UnknownMeetingError`, :class:`DuplicateRoleError` and
:class:`HeldOutLeakageError`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})

#: Frozen ASR-partition dev set (18 meetings), transcribed from the published
#: standard AMI full-corpus partition and verified present on disk. Provenance
#: caveat carried verbatim from the split freeze §1: these ids are NOT sourced
#: from a shipped file; 12 of the 18 are corroborated by shipped
#: ``seen_type="development"`` and none is contradicted.
FROZEN_DEV_18: tuple[str, ...] = (
    "ES2011a", "ES2011b", "ES2011c", "ES2011d",
    "IS1008a", "IS1008b", "IS1008c", "IS1008d",
    "TS3004a", "TS3004b", "TS3004c", "TS3004d",
    "IB4001", "IB4002", "IB4003", "IB4004", "IB4010", "IB4011",
)

#: Frozen ASR-partition eval set (16 meetings). Held out for confirmatory work
#: only: never a discovery surface, never an evaluation surface in this
#: repository, never exposed to the frozen core. 12 of the 16 are corroborated
#: by shipped ``visibility="unseen"``.
FROZEN_EVAL_16: tuple[str, ...] = (
    "ES2004a", "ES2004b", "ES2004c", "ES2004d",
    "IS1009a", "IS1009b", "IS1009c", "IS1009d",
    "TS3003a", "TS3003b", "TS3003c", "TS3003d",
    "EN2002a", "EN2002b", "EN2002c", "EN2002d",
)


class MeetingRole(str, Enum):
    """The closed role enum. Every meeting on the roster carries exactly one.

    The three *active* roles permit exposure of that meeting to the frozen
    core for their own purpose and no other. The two *reserved* roles permit
    no exposure at all; they exist so the assignment is total over the roster
    (a meeting with "no entry" would be an unchecked hole, not a safe
    default).
    """

    ASR_EVAL = "asr-eval"
    QA_EVAL = "qa-eval"
    GLOSSARY_DISCOVERY = "glossary-discovery"
    HELD_OUT_CONFIRMATORY = "held-out-confirmatory"
    HELD_OUT_RESERVE = "held-out-reserve"


ACTIVE_ROLES: frozenset[MeetingRole] = frozenset(
    {MeetingRole.ASR_EVAL, MeetingRole.QA_EVAL, MeetingRole.GLOSSARY_DISCOVERY}
)
RESERVED_ROLES: frozenset[MeetingRole] = frozenset(
    {MeetingRole.HELD_OUT_CONFIRMATORY, MeetingRole.HELD_OUT_RESERVE}
)


class RoleRegistryError(ValueError):
    """Base class for every registry refusal."""


class UnknownMeetingError(RoleRegistryError):
    """A meeting id that the registry does not carry was asked about."""


class DuplicateRoleError(RoleRegistryError):
    """The same meeting id appears twice in the registry file.

    ``json.loads`` silently keeps the last of duplicated object keys, which
    would let a second role be smuggled in under an id that already has one.
    The loader installs an ``object_pairs_hook`` so a duplicate key is a
    refusal instead of a silent overwrite.
    """


class HeldOutLeakageError(RoleRegistryError):
    """A held-out meeting was assigned an active role, or exposure of one was
    requested. The eval-16 case is the hard constraint from the split freeze
    §4.3: nothing in the confirmatory set may be exposed or scored."""


class QuarantinedQuestionError(RoleRegistryError):
    """A MeetingQA question was requested for a meeting whose registry role is
    not ``qa-eval`` -- i.e. the question straddles roles."""


@dataclass(frozen=True)
class MeetingRecord:
    """One registry row: the role plus the provenance that produced it."""

    meeting_id: str
    role: MeetingRole
    rule: str
    asr_partition: str
    meetingqa_split: str | None
    meetingqa_questions: int
    qmsum_split: str | None
    full_annotation_stack: bool

    @property
    def is_active(self) -> bool:
        return self.role in ACTIVE_ROLES

    @property
    def is_exposable(self) -> bool:
        """Exposure to the frozen core is permitted only under an active
        role. Reserved roles are unexposable by definition."""

        return self.role in ACTIVE_ROLES


_REQUIRED_RECORD_FIELDS = (
    "role",
    "rule",
    "asr_partition",
    "meetingqa_split",
    "meetingqa_questions",
    "qmsum_split",
    "full_annotation_stack",
)


@dataclass(frozen=True)
class AmiRoleRegistry:
    """A validated registry. Construction goes through
    :func:`load_role_registry`, which refuses anything it cannot vouch for."""

    meetings: Mapping[str, MeetingRecord]
    quarantined_meetings: tuple[str, ...]
    quarantined_question_count: int
    source_path: Path | None
    registry_hash: str

    # -- lookups -------------------------------------------------------

    def __len__(self) -> int:
        return len(self.meetings)

    def __contains__(self, meeting_id: object) -> bool:
        return meeting_id in self.meetings

    def record(self, meeting_id: str) -> MeetingRecord:
        try:
            return self.meetings[meeting_id]
        except KeyError:
            raise UnknownMeetingError(
                f"meeting {meeting_id!r} is not on the AMI role registry roster "
                f"({len(self.meetings)} meetings); the registry is the closed roster, "
                "so an unknown id is a defect, not a meeting without a role"
            ) from None

    def role_of(self, meeting_id: str) -> MeetingRole:
        return self.record(meeting_id).role

    def meetings_with_role(self, role: MeetingRole) -> tuple[str, ...]:
        return tuple(sorted(m for m, r in self.meetings.items() if r.role is role))

    def role_counts(self) -> dict[str, int]:
        counts = {role.value: 0 for role in MeetingRole}
        for record in self.meetings.values():
            counts[record.role.value] += 1
        return counts

    # -- gates ---------------------------------------------------------

    def assert_exposable(self, meeting_id: str, *, for_role: MeetingRole | None = None) -> None:
        """Refuse exposure of a reserved meeting, and (when ``for_role`` is
        given) exposure of an active meeting for a purpose that is not its
        own role. Raises; never returns a boolean the caller can ignore."""

        record = self.record(meeting_id)
        if record.role in RESERVED_ROLES:
            raise HeldOutLeakageError(
                f"meeting {meeting_id!r} carries reserved role {record.role.value!r} and may not be "
                "exposed to the frozen core, scored, or used as a discovery surface"
            )
        if for_role is not None and record.role is not for_role:
            raise HeldOutLeakageError(
                f"meeting {meeting_id!r} carries role {record.role.value!r}, not {for_role.value!r}; "
                "a meeting serves one role only"
            )

    def assert_question_usable(self, meeting_id: str) -> None:
        """Gate for MeetingQA questions. Only meetings whose role is
        ``qa-eval`` may contribute questions; every other MeetingQA question
        is quarantined because its meeting is spoken for by another role (or
        is held out)."""

        record = self.record(meeting_id)
        if record.role is not MeetingRole.QA_EVAL:
            raise QuarantinedQuestionError(
                f"MeetingQA questions on meeting {meeting_id!r} are QUARANTINED: its registry role is "
                f"{record.role.value!r}, not 'qa-eval' ({record.meetingqa_questions} questions affected)"
            )

    def is_quarantined(self, meeting_id: str) -> bool:
        record = self.record(meeting_id)
        return record.meetingqa_questions > 0 and record.role is not MeetingRole.QA_EVAL


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def default_registry_path() -> Path:
    """``<repo>/configs/corpora/ami-role-registry.json``, resolved from this
    module's location (``src/meeting_minutes_agent/corpora/roles.py``)."""

    return Path(__file__).resolve().parents[3] / "configs" / "corpora" / "ami-role-registry.json"


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateRoleError(
                f"duplicate key {key!r} in the AMI role registry: a meeting id may appear once, "
                "carrying one role"
            )
        seen[key] = value
    return seen


def _parse_role(meeting_id: str, raw: Any) -> MeetingRole:
    try:
        return MeetingRole(raw)
    except ValueError:
        known = ", ".join(sorted(r.value for r in MeetingRole))
        raise RoleRegistryError(
            f"meeting {meeting_id!r} carries unknown role {raw!r}; known roles: {known}"
        ) from None


def _require(condition: bool, message: str, error: type[RoleRegistryError] = RoleRegistryError) -> None:
    if not condition:
        raise error(message)


def load_role_registry(path: Path | str | None = None) -> AmiRoleRegistry:
    """Load and fully validate the registry. Every check below is a refusal.

    Structural: known schema version, no duplicate meeting key, every record
    complete and well typed, every role in the enum.

    Split-freeze bindings: the file's frozen dev-18 / eval-16 lists must match
    this module's constants exactly (so an edited file cannot redefine the
    freeze), the two must be disjoint, ``asr-eval`` must be exactly the
    dev-18, and every eval-16 meeting must carry ``held-out-confirmatory`` --
    an eval-16 meeting holding any active role is
    :class:`HeldOutLeakageError`.

    Self-consistency: the declared roster size and per-role counts must match
    what the records actually say, every ``qa-eval`` meeting must actually
    have questions, and the declared quarantine must equal the recomputed one
    (meetings with questions whose role is not ``qa-eval``).
    """

    registry_path = Path(path) if path is not None else default_registry_path()
    raw_text = registry_path.read_text(encoding="utf-8")
    document = json.loads(raw_text, object_pairs_hook=_no_duplicate_keys)

    schema_version = document.get("schema_version")
    _require(
        schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported AMI role registry schema_version {schema_version!r}; "
        f"supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
    )

    raw_meetings = document.get("meetings")
    _require(isinstance(raw_meetings, dict) and raw_meetings, "registry carries no 'meetings' object")

    records: dict[str, MeetingRecord] = {}
    for meeting_id, raw in sorted(raw_meetings.items()):
        _require(isinstance(raw, dict), f"meeting {meeting_id!r} entry is not an object")
        missing = [f for f in _REQUIRED_RECORD_FIELDS if f not in raw]
        _require(not missing, f"meeting {meeting_id!r} is missing registry fields: {missing}")
        questions = raw["meetingqa_questions"]
        _require(
            isinstance(questions, int) and not isinstance(questions, bool) and questions >= 0,
            f"meeting {meeting_id!r} has a non-integer meetingqa_questions: {questions!r}",
        )
        _require(
            isinstance(raw["full_annotation_stack"], bool),
            f"meeting {meeting_id!r} has a non-boolean full_annotation_stack",
        )
        records[meeting_id] = MeetingRecord(
            meeting_id=meeting_id,
            role=_parse_role(meeting_id, raw["role"]),
            rule=str(raw["rule"]),
            asr_partition=str(raw["asr_partition"]),
            meetingqa_split=raw["meetingqa_split"],
            meetingqa_questions=questions,
            qmsum_split=raw["qmsum_split"],
            full_annotation_stack=raw["full_annotation_stack"],
        )

    _validate_frozen_splits(document, records)
    _validate_counts(document, records)
    quarantined, quarantined_questions = _validate_quarantine(document, records)

    return AmiRoleRegistry(
        meetings=dict(records),
        quarantined_meetings=quarantined,
        quarantined_question_count=quarantined_questions,
        source_path=registry_path,
        registry_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    )


def _validate_frozen_splits(document: Mapping[str, Any], records: Mapping[str, MeetingRecord]) -> None:
    frozen = document.get("frozen_splits")
    _require(isinstance(frozen, dict), "registry carries no 'frozen_splits' block")

    file_dev = tuple(frozen.get("dev_18") or ())
    file_eval = tuple(frozen.get("eval_16") or ())
    _require(
        set(file_dev) == set(FROZEN_DEV_18) and len(file_dev) == len(FROZEN_DEV_18),
        "registry frozen_splits.dev_18 does not match the frozen ASR dev-18 in "
        "meeting_minutes_agent.corpora.roles.FROZEN_DEV_18; the split freeze is not editable "
        "from the data file",
    )
    _require(
        set(file_eval) == set(FROZEN_EVAL_16) and len(file_eval) == len(FROZEN_EVAL_16),
        "registry frozen_splits.eval_16 does not match FROZEN_EVAL_16; the split freeze is not "
        "editable from the data file",
    )
    _require(not (set(file_dev) & set(file_eval)), "frozen dev-18 and eval-16 overlap")

    missing = sorted((set(file_dev) | set(file_eval)) - set(records))
    _require(not missing, f"frozen split members absent from the roster: {missing}")

    for meeting_id in FROZEN_EVAL_16:
        role = records[meeting_id].role
        if role in ACTIVE_ROLES:
            raise HeldOutLeakageError(
                f"eval-16 meeting {meeting_id!r} carries active role {role.value!r}; the confirmatory "
                "held-out set may never hold a discovery or evaluation role"
            )
        _require(
            role is MeetingRole.HELD_OUT_CONFIRMATORY,
            f"eval-16 meeting {meeting_id!r} carries role {role.value!r}, expected "
            f"{MeetingRole.HELD_OUT_CONFIRMATORY.value!r}",
            HeldOutLeakageError,
        )

    asr_eval = {m for m, r in records.items() if r.role is MeetingRole.ASR_EVAL}
    _require(
        asr_eval == set(FROZEN_DEV_18),
        "the 'asr-eval' role set must be exactly the frozen dev-18; "
        f"extra={sorted(asr_eval - set(FROZEN_DEV_18))} missing={sorted(set(FROZEN_DEV_18) - asr_eval)}",
    )


def _validate_counts(document: Mapping[str, Any], records: Mapping[str, MeetingRecord]) -> None:
    corpus = document.get("corpus") or {}
    declared_roster = corpus.get("n_meetings")
    _require(
        declared_roster == len(records),
        f"registry declares corpus.n_meetings={declared_roster!r} but carries {len(records)} records",
    )

    declared = document.get("role_counts") or {}
    actual = {role.value: 0 for role in MeetingRole}
    for record in records.values():
        actual[record.role.value] += 1
    _require(
        {k: v for k, v in declared.items()} == actual,
        f"registry role_counts {dict(declared)} disagree with the records {actual}",
    )

    for meeting_id, record in records.items():
        if record.role is MeetingRole.QA_EVAL:
            _require(
                record.meetingqa_questions > 0,
                f"meeting {meeting_id!r} carries role 'qa-eval' but has no MeetingQA questions",
            )


def _validate_quarantine(
    document: Mapping[str, Any], records: Mapping[str, MeetingRecord]
) -> tuple[tuple[str, ...], int]:
    block = document.get("quarantine") or {}
    entries = block.get("meetings")
    _require(isinstance(entries, list), "registry carries no 'quarantine.meetings' list")

    expected = tuple(
        sorted(
            m
            for m, r in records.items()
            if r.meetingqa_questions > 0 and r.role is not MeetingRole.QA_EVAL
        )
    )
    declared = tuple(sorted(str(e["meeting_id"]) for e in entries))
    _require(
        declared == expected,
        "declared quarantine does not match the recomputed one; "
        f"declared-only={sorted(set(declared) - set(expected))} "
        f"missing={sorted(set(expected) - set(declared))}",
    )

    expected_questions = sum(records[m].meetingqa_questions for m in expected)
    declared_questions = block.get("n_questions")
    _require(
        declared_questions == expected_questions,
        f"registry declares quarantine.n_questions={declared_questions!r}, records sum to "
        f"{expected_questions}",
    )
    for entry in entries:
        meeting_id = str(entry["meeting_id"])
        _require(
            int(entry["n_questions"]) == records[meeting_id].meetingqa_questions,
            f"quarantine entry for {meeting_id!r} disagrees with its record's question count",
        )
    return expected, expected_questions


def quarantined_question_ids(
    registry: AmiRoleRegistry, questions: Iterable[Mapping[str, Any]], *, meeting_field: str = "title"
) -> tuple[str, ...]:
    """Return the ids of MeetingQA questions that the registry quarantines.

    Convenience for a loader that already holds MeetingQA records: a question
    is usable only when its meeting's role is ``qa-eval``. Unknown meetings
    raise -- an unrecognised meeting id is never silently treated as usable.
    """

    out = []
    for question in questions:
        meeting_id = str(question[meeting_field])
        if registry.role_of(meeting_id) is not MeetingRole.QA_EVAL:
            out.append(str(question["id"]))
    return tuple(out)
