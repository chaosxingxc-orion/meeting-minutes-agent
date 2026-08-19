"""E3 -- chunking engine.

Two-level design (``docs/readiness/2026-08-18-chunk-slice-granularity-
analysis.md`` SS8): deterministic TASK-CHUNK planning under a configurable
``[min, target, max]`` band, with boundaries snapped to topic-segmentation
marks when admissible and a plain-duration fallback otherwise
(:mod:`.planner`); the real TRANSPORT-SLICE builder -- the actual request
unit, VAD/grid or turn-aware, real audio in, a frozen content-hashed slice
manifest out (:mod:`.slicer`); boundary-provenance leakage tiering shared
by both (:mod:`.leakage`); an episode-local, append-only inter-chunk
glossary-state interface (:mod:`.state`); and adapters from E2's
``ResolvedMeeting`` (:mod:`.adapters`).
"""

from __future__ import annotations

from .adapters import (
    build_chunk_plan_for_resolved_meeting,
    topic_marks_from_resolved_meeting,
    turn_table_from_resolved_meeting,
    turn_table_provenance,
)
from .constants import (
    ENCODER_CHUNK_S,
    TASK_CHUNK_MAX_S,
    TASK_CHUNK_MIN_S,
    TASK_CHUNK_TARGET_S,
    TRANSPORT_SLICE_MAX_S,
    TRANSPORT_SLICE_MIN_S,
    TRANSPORT_SLICE_OVERLAP_S,
    TRANSPORT_SLICE_SNAP_S,
    TRANSPORT_SLICE_TARGET_S,
)
from .diarization import (
    DiarizationBackend,
    DiarizationResult,
    DiarizationToolNotPinnedError,
    NxtOracleDiarization,
    PinnedToolDiarization,
    ToolContactRecord,
    ToolDiarizationConfig,
    ToolDiarizationInvocationError,
    build_turn_aware_slice_plan_for_resolved_meeting,
    build_turn_aware_slice_plan_from_backend,
)
from .leakage import (
    BoundaryLeakageTier,
    BoundaryLeakageTierViolation,
    BoundaryProvenance,
    assert_runtime_admissible,
)
from .models import BoundarySource, Chunk, ChunkPlan, ChunkPlanKind, Segment, SegmentLike
from .planner import SinglePassNotAdmittedError, build_chunk_plan
from .rttm import (
    RttmParseError,
    parse_rttm_file,
    parse_rttm_text,
    write_rttm_file,
    write_rttm_text,
)
from .slicer import (
    SlicerError,
    Slice,
    SliceManifest,
    SliceManifestEntry,
    SlicePlan,
    SlicePlanMode,
    SliceTurnEntry,
    TurnSpan,
    build_slice_manifest,
    build_turn_aware_slice_plan,
    build_vad_slice_plan,
    detect_energy_pause_transitions,
    make_audio_chunk_resolver,
    materialize_slice_plan,
    plan_transport_slices_from_audio,
    read_audio_duration,
)
from .state import GlossaryStateLog, StateEntry

__all__ = [
    "BoundarySource",
    "Chunk",
    "ChunkPlan",
    "ChunkPlanKind",
    "Segment",
    "SegmentLike",
    "TASK_CHUNK_TARGET_S",
    "TASK_CHUNK_MIN_S",
    "TASK_CHUNK_MAX_S",
    "TRANSPORT_SLICE_TARGET_S",
    "TRANSPORT_SLICE_MIN_S",
    "TRANSPORT_SLICE_MAX_S",
    "TRANSPORT_SLICE_SNAP_S",
    "TRANSPORT_SLICE_OVERLAP_S",
    "ENCODER_CHUNK_S",
    "BoundaryProvenance",
    "BoundaryLeakageTier",
    "BoundaryLeakageTierViolation",
    "assert_runtime_admissible",
    "SinglePassNotAdmittedError",
    "build_chunk_plan",
    "build_chunk_plan_for_resolved_meeting",
    "topic_marks_from_resolved_meeting",
    "turn_table_from_resolved_meeting",
    "turn_table_provenance",
    "SlicerError",
    "TurnSpan",
    "SliceTurnEntry",
    "Slice",
    "SlicePlanMode",
    "SlicePlan",
    "SliceManifestEntry",
    "SliceManifest",
    "build_vad_slice_plan",
    "build_turn_aware_slice_plan",
    "read_audio_duration",
    "detect_energy_pause_transitions",
    "plan_transport_slices_from_audio",
    "materialize_slice_plan",
    "build_slice_manifest",
    "make_audio_chunk_resolver",
    "GlossaryStateLog",
    "StateEntry",
    "DiarizationResult",
    "DiarizationBackend",
    "NxtOracleDiarization",
    "DiarizationToolNotPinnedError",
    "ToolDiarizationConfig",
    "ToolContactRecord",
    "ToolDiarizationInvocationError",
    "PinnedToolDiarization",
    "build_turn_aware_slice_plan_from_backend",
    "build_turn_aware_slice_plan_for_resolved_meeting",
    "RttmParseError",
    "parse_rttm_text",
    "parse_rttm_file",
    "write_rttm_text",
    "write_rttm_file",
]
