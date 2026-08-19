"""PRECOMP receipt schemas: one per-meeting receipt, one per-wave summary,
plus the fsynced-write and resume-check helpers every existing launcher in
this repository already uses
(``scripts/launch_diar_smoke.py``'s ``receipt_path``/``already_done``/
``_fsync_write_json``, ``scripts/launch_pattr_smoke.py``'s
``ResponseSink``).

Layout (registered: ``docs/readiness/2026-08-19-precomp-preregistration.md``
SS5): "Receipts under ``docs/checks/2026-08-19-precomp-wave{1,2}/``; all
derived bytes on the data root, manifests only in Git." A receipt (this
module's shape) carries hashes/counts/paths -- never audio bytes -- so it
is exactly the "manifest" that prereg line means is safe to commit; the
RTTM files, slice WAVs, and feature-cache entries it references all live
under the caller's data root and are never written here.

Schema versioning (the G1 VAD-supplement extension,
``docs/readiness/2026-08-19-g1-floors-preregistration.md`` SS3): bumping
``SCHEMA_VERSION`` to ``"1.1.0"`` adds an OPTIONAL third ``"vad"`` key
alongside the existing ``"tool"``/``"oracle"`` keys under
``slice_plans``/``cutting``/``encode_warm`` (:mod:`.pipeline`'s
``TURN_SOURCES``) -- purely additive over ``"1.0.0"``, never a field
removed or a meaning changed. :func:`already_done`'s compatibility check is
therefore MAJOR-version-only (:func:`_schema_major`), not an exact string
match: the 18 already-committed wave-1 receipts
(``docs/checks/2026-08-19-precomp-wave1/receipts/*.json``, all
``schema_version: "1.0.0"``, no ``"vad"`` key at all) are read as
already-done exactly as before this change, and every reader that sums a
per-source field (:func:`~.budget.wave_usage_from_receipts`) already
defaults a missing key to zero/empty, so an absent ``"vad"`` key reads as
"that source was never requested for this receipt" everywhere, not as a
parse failure.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.1.0"


def _schema_major(version: Any) -> str | None:
    """The leading dot-separated component of a ``schema_version`` string,
    or ``None`` for anything that is not a non-empty string (module
    docstring's compatibility check operates on this, never on the full
    version string)."""

    if not isinstance(version, str) or not version:
        return None
    return version.split(".", 1)[0]


def _schema_compatible(version: Any) -> bool:
    """``True`` iff ``version`` shares this module's own SCHEMA_VERSION
    major component (module docstring) -- the backward-compatibility test
    :func:`already_done` applies instead of an exact string match."""

    return _schema_major(version) == _schema_major(SCHEMA_VERSION)


def meeting_receipt_path(out_dir: Path, meeting_id: str) -> Path:
    return Path(out_dir) / "receipts" / f"{meeting_id}-receipt.json"


def wave_summary_path(out_dir: Path) -> Path:
    return Path(out_dir) / "wave-summary.json"


def fsync_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    """Write ``payload`` as pretty JSON, fsynced before returning -- the
    same "every receipt write is fsynced before the next contact starts, so
    a crash costs at most the in-flight contact" discipline
    ``scripts/launch_diar_smoke.py`` documents for its own receipts."""

    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return resolved


def build_meeting_receipt(
    *,
    wave: int,
    meeting_id: str,
    ok: bool,
    error: str | None,
    diar: Mapping[str, Any],
    slice_plans: Mapping[str, Any],
    cutting: Mapping[str, Any],
    encode_warm: Mapping[str, Any],
    metrics: Mapping[str, Any],
    budget_after: Mapping[str, Any],
    recorded_utc: str,
) -> dict[str, Any]:
    """The one per-meeting receipt shape every PRECOMP pipeline run
    produces, success or failure -- a failed meeting still carries this
    exact top-level shape (``ok: False``, ``error`` set, and whichever of
    ``diar``/``slice_plans``/``cutting``/``encode_warm``/``metrics`` the
    pipeline reached before failing left at their pre-failure default, per
    :mod:`~.pipeline`'s own ``FAILURE_STAGE_DEFAULTS``), so a resume/audit
    reader never needs to branch on ``ok`` to find a field."""

    return {
        "schema_version": SCHEMA_VERSION,
        "wave": wave,
        "meeting_id": meeting_id,
        "ok": ok,
        "error": error,
        "diar": dict(diar),
        "slice_plans": dict(slice_plans),
        "cutting": dict(cutting),
        "encode_warm": dict(encode_warm),
        "metrics": dict(metrics),
        "budget_after": dict(budget_after),
        "recorded_utc": recorded_utc,
    }


def write_meeting_receipt(out_dir: Path, receipt: Mapping[str, Any]) -> Path:
    return fsync_write_json(meeting_receipt_path(out_dir, str(receipt["meeting_id"])), receipt)


def already_done(out_dir: Path, meeting_id: str) -> bool:
    """Resume support (prereg SS6 / task instruction: "resumable at meeting
    granularity: skip meetings whose receipt is complete+verified"). A
    receipt is complete+verified when it parses as JSON, declares a
    schema-COMPATIBLE ``schema_version`` (module docstring:
    :func:`_schema_compatible`, major-version match rather than an exact
    string match, so the 18 committed ``"1.0.0"`` wave-1 receipts remain
    recognized as done under this module's current ``"1.1.0"``), and
    records ``ok: true``. A missing, unparsable, schema-INCOMPATIBLE, or
    errored receipt is NOT done -- it (or the whole meeting) will be
    retried."""

    path = meeting_receipt_path(out_dir, meeting_id)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    return _schema_compatible(data.get("schema_version")) and bool(data.get("ok"))


def build_wave_summary(
    outcomes: list[Mapping[str, Any]], *, wave: int, budget_totals: Mapping[str, Any], stopped_reason: str | None
) -> dict[str, Any]:
    """The whole wave's summary -- mirrors
    ``scripts/launch_diar_smoke.py::build_flight_summary``'s own shape."""

    return {
        "schema_version": SCHEMA_VERSION,
        "wave": wave,
        "n_meetings": len(outcomes),
        "n_ok": sum(1 for o in outcomes if o.get("ok")),
        "n_error": sum(1 for o in outcomes if not o.get("ok")),
        "budget": dict(budget_totals),
        "stopped_reason": stopped_reason,
        "outcomes": [dict(o) for o in outcomes],
    }


def write_wave_summary(out_dir: Path, summary: Mapping[str, Any]) -> Path:
    return fsync_write_json(wave_summary_path(out_dir), summary)


__all__ = [
    "SCHEMA_VERSION",
    "meeting_receipt_path",
    "wave_summary_path",
    "fsync_write_json",
    "build_meeting_receipt",
    "write_meeting_receipt",
    "already_done",
    "build_wave_summary",
    "write_wave_summary",
]
