"""DIAR-SMOKE machinery: the registered meeting roster, Mix-Headset audio
path resolution, per-arm pinned-tool configuration loading, the wall-clock/
GPU-hour budget guard, and a best-effort GPU-utilization snapshot.

Registered design: ``docs/readiness/2026-08-18-diar-smoke-preregistration.md``.
Six dev-18 Mix-Headset meetings; arms A (NeMo fp32, isolated venv) / B
(NeMo-Speech.cpp CUDA + GGUF) / C (contingent, flag-gated). This module is
MACHINERY ONLY: it never bundles a concrete tool command, checkpoint path,
or hash -- the acquisition prerequisite (prereg SS6) has not landed at
engineering time, so every tool identity is caller-supplied configuration
(``scripts/launch_diar_smoke.py --arm-config``), mirroring
``scripts/launch_pattr_smoke.py``'s own "budgets, server identity... are all
caller-supplied CLI arguments, never hardcoded" discipline. Nothing here
performs a subprocess call or touches audio bytes; the real per-(arm,
meeting) tool contact is wired in ``scripts/launch_diar_smoke.py`` using
:class:`~meeting_minutes_agent.chunking.diarization.PinnedToolDiarization`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ..chunking.diarization import ToolDiarizationConfig
from ..corpora.roles import MeetingRole, load_role_registry

__all__ = [
    "ARM_A",
    "ARM_B",
    "ARM_C",
    "REQUIRED_ARMS",
    "CONTINGENT_ARMS",
    "ALL_ARMS",
    "REGISTERED_MEETINGS",
    "DEFAULT_AMI_AUDIO_ROOT_RELATIVE",
    "GPU_HOUR_CEILING",
    "WALL_HOUR_CEILING",
    "meeting_audio_relpath",
    "resolve_meeting_audio_path",
    "require_meeting_audio_path",
    "assert_registered_meetings_exposable",
    "ArmConfigError",
    "load_arm_configs",
    "SmokeBudgetExceeded",
    "SmokeBudget",
    "query_gpu_utilization_snapshot",
    "estimate_gpu_seconds",
]

ARM_A = "A"
ARM_B = "B"
ARM_C = "C"
REQUIRED_ARMS: tuple[str, ...] = (ARM_A, ARM_B)
CONTINGENT_ARMS: tuple[str, ...] = (ARM_C,)
ALL_ARMS: tuple[str, ...] = (ARM_A, ARM_B, ARM_C)

#: The six registered dev-18 Mix-Headset meetings (prereg SS3): four shared
#: with the G1 oracle-smoke set, plus TS3004d, covering all three scenario
#: sites (ES/IS/TS).
REGISTERED_MEETINGS: tuple[str, ...] = (
    "ES2011a",
    "ES2011b",
    "IS1008b",
    "IS1008d",
    "TS3004b",
    "TS3004d",
)

#: Matches ``scripts/build_pattr_manifest.py``'s own
#: ``DEFAULT_AMI_AUDIO_ROOT_RELATIVE`` -- one convention for where AMI audio
#: lives under the data root.
DEFAULT_AMI_AUDIO_ROOT_RELATIVE = "datasets/ami/amicorpus"

#: Registered cost ceilings (prereg SS7).
GPU_HOUR_CEILING = 1.0
WALL_HOUR_CEILING = 2.0


# ---------------------------------------------------------------------------
# audio resolution
# ---------------------------------------------------------------------------


def meeting_audio_relpath(meeting_id: str, *, ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE) -> str:
    """The Mix-Headset WAV's path relative to the data root -- the same
    ``{root}/{meeting_id}/audio/{meeting_id}.Mix-Headset.wav`` convention
    ``scripts/build_pattr_manifest.py`` uses."""

    return f"{ami_audio_root_relative}/{meeting_id}/audio/{meeting_id}.Mix-Headset.wav"


def resolve_meeting_audio_path(
    meeting_id: str, *, data_dir: Path | str, ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE
) -> Path:
    """:func:`meeting_audio_relpath` resolved against ``data_dir``.
    Existence is NOT checked -- a caller may resolve a path before the
    acquisition step has landed the bytes; see
    :func:`require_meeting_audio_path` for the checked variant a real
    flight needs."""

    return Path(data_dir) / meeting_audio_relpath(meeting_id, ami_audio_root_relative=ami_audio_root_relative)


def require_meeting_audio_path(
    meeting_id: str, *, data_dir: Path | str, ami_audio_root_relative: str = DEFAULT_AMI_AUDIO_ROOT_RELATIVE
) -> Path:
    """:func:`resolve_meeting_audio_path`, refusing (``FileNotFoundError``)
    if the resolved WAV is not on disk."""

    path = resolve_meeting_audio_path(meeting_id, data_dir=data_dir, ami_audio_root_relative=ami_audio_root_relative)
    if not path.is_file():
        raise FileNotFoundError(f"AMI Mix-Headset audio not found for meeting {meeting_id!r}: {path}")
    return path


def assert_registered_meetings_exposable(meetings: Any = REGISTERED_MEETINGS) -> None:
    """Defense in depth (same discipline as ``scripts/build_pattr_manifest.py``'s
    own ``build_manifest``): every meeting a real flight touches must carry
    the ``asr-eval`` role on the committed AMI role registry, checked
    against the machine-checked registry rather than trusted from this
    module's own roster constant."""

    registry = load_role_registry()
    for meeting_id in meetings:
        registry.assert_exposable(meeting_id, for_role=MeetingRole.ASR_EVAL)


# ---------------------------------------------------------------------------
# per-arm tool configuration
# ---------------------------------------------------------------------------


class ArmConfigError(ValueError):
    """The ``--arm-config`` JSON was structurally invalid: a required arm
    (A or B) is missing, or an unknown arm key is present."""


def load_arm_configs(path: Path | str) -> dict[str, ToolDiarizationConfig]:
    """Load a ``{"A": {...}, "B": {...}, "C": {...}}`` JSON object, each
    value shaped as :meth:`~meeting_minutes_agent.chunking.diarization.
    ToolDiarizationConfig.from_dict` expects. ``A``/``B`` are required;
    ``C`` (the contingent arm, prereg SS2) is optional."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ArmConfigError(f"arm-config {path} must be a JSON object keyed by arm letter, got {type(document).__name__}")
    missing = [a for a in REQUIRED_ARMS if a not in document]
    if missing:
        raise ArmConfigError(f"arm-config {path} is missing required arm(s) {missing}; expected at least {REQUIRED_ARMS}")
    unknown = [a for a in document if a not in ALL_ARMS]
    if unknown:
        raise ArmConfigError(f"arm-config {path} carries unknown arm key(s) {unknown}; expected a subset of {ALL_ARMS}")
    return {arm: ToolDiarizationConfig.from_dict(raw) for arm, raw in document.items()}


# ---------------------------------------------------------------------------
# budget guard
# ---------------------------------------------------------------------------


class SmokeBudgetExceeded(RuntimeError):
    """Fail-closed refusal: the wall-clock or GPU-hour ceiling would already
    be exceeded by the NEXT contact. A diarization tool call's duration is
    not knowable in advance the way an LLM request's audio-seconds is
    (:class:`~meeting_minutes_agent.client.budgets.CallBudget`'s own
    pre-reservation model does not apply here), so this is a post-hoc guard:
    checked before every contact against usage already recorded from
    completed ones, never a prediction of the next contact's cost."""


@dataclass
class SmokeBudget:
    """Cumulative wall-clock and (advisory) GPU-second usage across a
    flight, checked before every contact against the registered ceilings
    (prereg SS7: <=1.0 GPU-h, <=2h wall)."""

    max_wall_seconds: float = WALL_HOUR_CEILING * 3600.0
    max_gpu_seconds: float = GPU_HOUR_CEILING * 3600.0
    wall_seconds_used: float = 0.0
    gpu_seconds_used: float = 0.0

    def check_before_contact(self) -> None:
        if self.wall_seconds_used >= self.max_wall_seconds:
            raise SmokeBudgetExceeded(
                f"wall-clock ceiling already reached: {self.wall_seconds_used:.1f}s used of "
                f"{self.max_wall_seconds:.1f}s allowed -- refusing to start another contact"
            )
        if self.gpu_seconds_used >= self.max_gpu_seconds:
            raise SmokeBudgetExceeded(
                f"GPU-hour ceiling already reached: {self.gpu_seconds_used:.1f}s used of "
                f"{self.max_gpu_seconds:.1f}s allowed -- refusing to start another contact"
            )

    def record(self, *, wall_seconds: float, gpu_seconds: float) -> None:
        self.wall_seconds_used += max(0.0, wall_seconds)
        self.gpu_seconds_used += max(0.0, gpu_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_seconds_used": self.wall_seconds_used,
            "max_wall_seconds": self.max_wall_seconds,
            "gpu_seconds_used": self.gpu_seconds_used,
            "max_gpu_seconds": self.max_gpu_seconds,
        }


# ---------------------------------------------------------------------------
# GPU accounting (best-effort, advisory -- module docstring)
# ---------------------------------------------------------------------------

_GPU_QUERY_FIELDS = ("utilization.gpu", "memory.used", "clocks.sm", "temperature.gpu", "power.draw")
_GPU_SNAPSHOT_KEYS = ("utilization_gpu_pct", "memory_used_mib", "clocks_sm_mhz", "temperature_c", "power_draw_w")


def query_gpu_utilization_snapshot(
    *, run: Callable[..., "subprocess.CompletedProcess[str]"] | None = None
) -> dict[str, float] | None:
    """One best-effort ``nvidia-smi`` query (prereg SS4: "GPU seconds if
    available via nvidia-smi query"). Returns ``None`` -- NEVER raises -- if
    ``nvidia-smi`` is absent, times out, or its output does not parse, so a
    CPU-only or GPU-less dev host exercises every code path around this
    function identically to a GPU host that simply reports 0% utilization."""

    runner = run or subprocess.run
    try:
        completed = runner(
            ["nvidia-smi", f"--query-gpu={','.join(_GPU_QUERY_FIELDS)}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    first_line = next((line for line in completed.stdout.splitlines() if line.strip()), None)
    if first_line is None:
        return None
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) < len(_GPU_SNAPSHOT_KEYS):
        return None
    try:
        return {key: float(value) for key, value in zip(_GPU_SNAPSHOT_KEYS, parts)}
    except ValueError:
        return None


def estimate_gpu_seconds(wall_seconds: float, snapshot: Mapping[str, float] | None) -> float:
    """Coarse, single-sample proxy: ``wall_seconds * utilization_pct/100``.
    Never a substitute for a real integrated-over-time GPU-seconds account
    (the operational sampler pattern this repository's own flight receipts
    use, e.g. ``docs/checks/2026-08-18-pprompt-flight/script-gpu-sampler.sh``'s
    ``utilization_integrated_gpu_seconds``). ``snapshot=None`` (no GPU
    queryable) returns ``0.0`` -- never fabricates a number."""

    if snapshot is None:
        return 0.0
    pct = max(0.0, min(100.0, float(snapshot.get("utilization_gpu_pct", 0.0))))
    return max(0.0, wall_seconds) * (pct / 100.0)
