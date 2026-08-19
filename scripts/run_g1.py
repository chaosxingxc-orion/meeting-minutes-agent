#!/usr/bin/env python3
"""G1 floors campaign runner -- MACHINERY ONLY.

This engineering mission builds and import/wiring-verifies this script; it
never contacts a real ``llama-server`` or runs a real flight (task scope:
"MACHINERY ONLY -- no model contact, no flights"). A later, separate,
coordinator-reviewed mission runs it for real, per the REGISTERED
preregistration: ``docs/readiness/2026-08-19-g1-floors-preregistration.md``.

Wires: the mode roster (:func:`meeting_minutes_agent.probes.g1_campaign.meetings_for_mode`)
x the four registered arms (:mod:`meeting_minutes_agent.probes.g1`) -> real,
CPU-only (never model-contacting) rebuilt slice plans per (meeting, arm),
reused from PRECOMP's own on-disk cache (RTTM bytes, NXT gold XML, the
already-cut slice WAVs) -> a resumable
:class:`~meeting_minutes_agent.probes.g1_campaign.WorkItem` list ->
:func:`~meeting_minutes_agent.probes.g1_campaign.plan_chunks` (<=50-minute
chunks) -> ONE CHUNK per invocation, its own
:class:`~meeting_minutes_agent.probes.g1_campaign.ManagedLlamaServer` started
and torn down within that SAME process (the 60-minute harness-reap rule --
``docs/checks/2026-08-19-precomp-wave1/README.md``'s resume-pass lesson: a
server started as a separate background job outlived, and was independently
killed out from under, the work depending on it) ->
:class:`~meeting_minutes_agent.client.transport.LlamaServerTransport` ->
per-item fsynced receipts (:mod:`meeting_minutes_agent.probes.g1_campaign`)
+ a per-chunk fsynced JSONL response sink.

Chunk-granularity server ownership: this script, invoked once PER CHUNK
(``--run-chunk N``), starts its own server as a direct subprocess CHILD when
``--server-cmd`` is given, does that chunk's own (resumable) work, tears the
server down in a ``finally``, and exits -- so the whole invocation finishes
well inside the 60-minute harness background-job reap window, and the child
server process can never outlive (or be independently killed out from
under) the work depending on it.

Every meeting/arm's own slice plan is REBUILT (never re-cut, never re-
diarized) on every invocation from PRECOMP's on-disk cache -- deterministic,
CPU-only, real I/O with zero model contact (module docstring's own "no
model contact" scope): :func:`resolve_slice_plan` reads an RTTM file or NXT
gold XML plus the meeting's source-audio duration/VAD structure, exactly the
same real inputs PRECOMP's own pipeline fed
``chunking.slicer.build_turn_aware_slice_plan``, so the rebuilt plan names
the SAME cached slice-WAV filenames PRECOMP already cut. This is why
``--run-chunk`` needs no separate ``--plan-file``: the chunk plan is always
re-derived, identically, from the same on-disk inputs plus the registered
roster/arm/QA-cap parameters.

Usage (safe right now -- no server, no model contact, prints the resolved
roster/arms/QA-cap count)::

    python scripts/run_g1.py --mode floors --data-dir "$SPEECHRL_DATA_DIR" --summary-only

Usage (the FLIGHT mission -- one invocation per chunk)::

    python scripts/run_g1.py --mode floors --data-dir "$SPEECHRL_DATA_DIR" \\
        --run-chunk 0 --resume --stop-file docs/checks/<campaign>/G1_YIELD \\
        --server-cmd llama-server --host 127.0.0.1 --port 8080 -m <gguf> ... \\
        --base-url http://127.0.0.1:8080 \\
        --model-path /home/chao/models/<pinned-gguf> --model-sha256 <sha256> \\
        --meetingqa-root "$SPEECHRL_DATA_DIR/datasets/meetingqa" \\
        --ami-root "$SPEECHRL_DATA_DIR/datasets/ami" \\
        --out-dir docs/checks/<campaign>/<release-id>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.models import Segment  # noqa: E402
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, ModelResponse, TransportConfig  # noqa: E402
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus  # noqa: E402
from meeting_minutes_agent.corpora.roles import FROZEN_DEV_18, load_role_registry  # noqa: E402
from meeting_minutes_agent.heads.transcribe_attribute import parse_transcribe_attribute_response  # noqa: E402
from meeting_minutes_agent.probes import g1  # noqa: E402
from meeting_minutes_agent.probes import g1_campaign  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DERIVED_ROOT_RELATIVE = "derived/meeting-minutes/precomp"
DEFAULT_SLICE_DIR_RELATIVE_TOOL = f"{DEFAULT_DERIVED_ROOT_RELATIVE}/slices/tool"
DEFAULT_SLICE_DIR_RELATIVE_ORACLE = f"{DEFAULT_DERIVED_ROOT_RELATIVE}/slices/oracle"
DEFAULT_SLICE_DIR_RELATIVE_VAD = f"{DEFAULT_DERIVED_ROOT_RELATIVE}/slices/vad"


def default_out_dir(mode: str) -> Path:
    return REPO_ROOT / "docs" / "checks" / f"2026-08-19-g1-{mode}"


# ---------------------------------------------------------------------------
# slice-plan resolution per arm (PRECOMP cache reuse / VAD supplement)
# ---------------------------------------------------------------------------


def resolve_slice_plan(
    arm: str,
    meeting_id: str,
    *,
    data_dir: Path,
    derived_root: Path,
    nxt_corpus: NxtCorpus,
    vad_manifest_dir: Path | None,
    slice_dir_tool: str = DEFAULT_SLICE_DIR_RELATIVE_TOOL,
    slice_dir_oracle: str = DEFAULT_SLICE_DIR_RELATIVE_ORACLE,
    slice_dir_vad: str = DEFAULT_SLICE_DIR_RELATIVE_VAD,
) -> tuple[Any, str]:
    """One arm's :class:`~meeting_minutes_agent.chunking.slicer.SlicePlan`
    plus the relative directory its cached slice-WAV files live under.
    Z-turn/Z-free reuse the SAME rebuilt tool-diar plan (floors table:
    "Z-free... same tool-turn slices"); Z-oracle rebuilds the oracle-diar
    plan; Z-nodiar consumes the PRECOMP VAD supplement's manifest,
    fail-closed if absent (:class:`meeting_minutes_agent.probes.g1.G1VadSupplementMissingError`)."""

    if arm in (g1.ARM_Z_TURN, g1.ARM_Z_FREE):
        audio_path = g1_campaign.meeting_audio_path(meeting_id, data_dir=data_dir)
        rttm_path = g1_campaign.rttm_path_for(derived_root, meeting_id)
        return g1_campaign.rebuild_tool_slice_plan(meeting_id, rttm_path, audio_path), slice_dir_tool
    if arm == g1.ARM_Z_ORACLE:
        audio_path = g1_campaign.meeting_audio_path(meeting_id, data_dir=data_dir)
        return g1_campaign.rebuild_oracle_slice_plan(meeting_id, nxt_corpus, audio_path), slice_dir_oracle
    if arm == g1.ARM_Z_NODIAR:
        if vad_manifest_dir is None:
            raise g1.G1VadSupplementMissingError(
                "Z-nodiar requires --vad-manifest-dir naming where the PRECOMP VAD supplement "
                "writes its per-meeting SlicePlan JSON; none was given"
            )
        return g1.load_vad_slice_plan(Path(vad_manifest_dir) / f"{meeting_id}.json"), slice_dir_vad
    raise g1.G1Error(f"unknown G1 arm {arm!r}")


def resolve_all_slice_plans(
    meetings: Sequence[str],
    arms: Sequence[str],
    *,
    data_dir: Path,
    derived_root: Path,
    nxt_corpus: NxtCorpus,
    vad_manifest_dir: Path | None,
) -> dict[tuple[str, str], tuple[Any, str]]:
    """Every ``(meeting_id, arm)``'s own ``(SlicePlan, slice_dir_relative)``
    pair -- the campaign's own real-but-model-contact-free planning input.
    A Z-nodiar meeting whose VAD supplement manifest is not yet present
    propagates :class:`~meeting_minutes_agent.probes.g1.G1VadSupplementMissingError`
    unchanged (fail-closed, never silently skipped)."""

    out: dict[tuple[str, str], tuple[Any, str]] = {}
    for meeting_id in meetings:
        for arm in arms:
            out[(meeting_id, arm)] = resolve_slice_plan(
                arm, meeting_id, data_dir=data_dir, derived_root=derived_root, nxt_corpus=nxt_corpus,
                vad_manifest_dir=vad_manifest_dir,
            )
    return out


# ---------------------------------------------------------------------------
# dispatch: one work item's full (transcribe [+ minutes + qa]) workload
# ---------------------------------------------------------------------------


class ResponseSink:
    """Append-only, fsynced JSONL sink -- identical shape to
    ``scripts/launch_pprompt_sweep.py::ResponseSink``."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, record: Mapping[str, object]) -> None:
        import os

        self._handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "ResponseSink":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _dispatch(
    spec: "g1.G1RequestSpec", *, data_dir: Path, transport: LlamaServerTransport, sink: ResponseSink | None
) -> ModelResponse:
    kwargs = spec.to_transport_kwargs(data_dir=data_dir)
    response = transport.request(**kwargs)
    if sink is not None:
        sink.write(
            {
                **spec.to_dict(),
                "outcome": "ok",
                "response_request_id": response.request_id,
                "text": response.text,
                "usage": dict(response.usage),
                "max_tokens": (kwargs.get("decoding_params") or {}).get("max_tokens"),
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    return response


def _parse_transcribe_reply_into_segments(
    meeting_id: str, slice_index: int, raw_text: str, *, start: float, end: float
) -> tuple[Segment, ...]:
    """One transcribe-attribute reply, parsed into the ``resolved_transcript``
    the minutes head needs. Slice-whole timing (never per-segment -- this
    reply's own grammar carries none, the established P-ATTR/P-PROMPT
    treatment) is applied to every segment the reply parsed to."""

    parsed = parse_transcribe_attribute_response(raw_text)
    return tuple(
        Segment(id=f"{meeting_id}-slice{slice_index:04d}-{i}", speaker=seg.speaker, start=start, end=end, text=seg.text)
        for i, seg in enumerate(parsed.segments)
    )


def _response_gpu_seconds(response: ModelResponse) -> float:
    """The decode-occupancy estimate this campaign records as ``gpu_seconds``
    for one dispatched request: the sum of every attempt's own
    ``latency_seconds`` (retries included -- a retried attempt still held
    the GPU for its own wall time), the same request-latency convention the
    SAEA study's flight receipts use. Never wall-clock-around-the-whole-item
    (that also counts CPU-side plan/parse time this request never occupied
    the GPU for)."""

    return sum(attempt.latency_seconds for attempt in response.attempts)


def run_item(
    item: "g1_campaign.WorkItem",
    *,
    data_dir: Path,
    plan: Any,
    slice_dir_relative: str,
    transport: LlamaServerTransport,
    sink: ResponseSink | None,
    qa_questions: Sequence[Any],
) -> dict[str, Any]:
    """Dispatch one (meeting, arm) work item's full workload (module
    docstring), given its already-resolved ``plan``. Never raises: every
    failure is caught and folded into an ``ok: False`` receipt with
    whatever contacts already completed -- mirrors
    ``precomp.pipeline.run_meeting``'s own per-meeting failure isolation,
    one level down (per work item, not per meeting).

    ``qa_questions`` is the CAMPAIGN-WIDE capped set; this function is the
    per-meeting QA router (the G1-PATH structural NOT-PASS repair): it
    filters that set down to ``item.meeting_id``'s own questions via
    :func:`~meeting_minutes_agent.probes.g1.questions_for_meeting` BEFORE
    building any qa request, so a question is never asked over a different
    meeting's audio. A meeting with zero routed questions (e.g. ``IS1008a``
    under the registered N=200 cap) dispatches zero qa calls --
    :func:`~meeting_minutes_agent.probes.g1.build_qa_requests_for_meeting`
    itself tolerates an empty question set, so no campaign-wide
    ``if qa_questions`` guard is needed here.

    ``gpu_seconds`` on the returned receipt is real, not the unconditional
    ``0.0`` this function used to record: it accumulates
    :func:`_response_gpu_seconds` over every response actually received
    (transcribe, minutes, and qa alike), so the campaign's GPU-hour ceiling
    (``g1_campaign.G1Budget``) binds on real spend."""

    started = time.monotonic()
    contacts: list[dict[str, Any]] = []
    gpu_seconds = 0.0
    try:
        transcribe_specs = g1.build_transcribe_requests(
            item.arm, item.meeting_id, plan, slice_dir_relative=slice_dir_relative
        )
        resolved_transcript: list[Segment] = []
        for spec, sl in zip(transcribe_specs, plan.slices):
            response = _dispatch(spec, data_dir=data_dir, transport=transport, sink=sink)
            gpu_seconds += _response_gpu_seconds(response)
            contacts.append({"request_id": spec.request_id, "kind": spec.kind, "outcome": "ok"})
            if item.arm in g1.ARMS_WITH_MINUTES_QA:
                resolved_transcript.extend(
                    _parse_transcribe_reply_into_segments(item.meeting_id, sl.index, response.text, start=sl.start, end=sl.end)
                )

        if item.arm in g1.ARMS_WITH_MINUTES_QA:
            minutes_spec = g1.build_minutes_request_for_meeting(
                item.arm, item.meeting_id, plan, tuple(resolved_transcript), slice_dir_relative=slice_dir_relative
            )
            minutes_response = _dispatch(minutes_spec, data_dir=data_dir, transport=transport, sink=sink)
            gpu_seconds += _response_gpu_seconds(minutes_response)
            contacts.append({"request_id": minutes_spec.request_id, "kind": minutes_spec.kind, "outcome": "ok"})

            meeting_qa_questions = g1.questions_for_meeting(qa_questions, item.meeting_id)
            qa_specs = g1.build_qa_requests_for_meeting(
                item.arm, item.meeting_id, plan, meeting_qa_questions, slice_dir_relative=slice_dir_relative
            )
            for spec in qa_specs:
                response = _dispatch(spec, data_dir=data_dir, transport=transport, sink=sink)
                gpu_seconds += _response_gpu_seconds(response)
                contacts.append({"request_id": spec.request_id, "kind": spec.kind, "outcome": "ok"})

        wall_seconds = time.monotonic() - started
        return g1_campaign.build_item_receipt(
            meeting_id=item.meeting_id, arm=item.arm, ok=True, error=None, n_calls=len(contacts),
            gpu_seconds=gpu_seconds, wall_seconds=wall_seconds, contacts=contacts,
        )
    except Exception as error:  # noqa: BLE001 -- isolated per item, recorded not raised
        wall_seconds = time.monotonic() - started
        return g1_campaign.build_item_receipt(
            meeting_id=item.meeting_id, arm=item.arm, ok=False, error=f"{type(error).__name__}: {error}",
            n_calls=len(contacts), gpu_seconds=gpu_seconds, wall_seconds=wall_seconds, contacts=contacts,
        )


# ---------------------------------------------------------------------------
# chunk execution
# ---------------------------------------------------------------------------


def run_chunk(
    chunk: "g1_campaign.Chunk",
    *,
    data_dir: Path,
    slice_plans_by_meeting_arm: Mapping[tuple[str, str], tuple[Any, str]],
    transport: LlamaServerTransport,
    sink: ResponseSink | None,
    qa_questions: Sequence[Any],
    out_dir: Path,
    resume: bool,
    budget: "g1_campaign.G1Budget",
    stop_file: Path | str | None = None,
    seconds_per_request: float = g1_campaign.DEFAULT_SECONDS_PER_REQUEST,
) -> dict[str, Any]:
    """Run every (resumable) work item in ``chunk``, budget-guarded,
    stop-file-checked before each item -- mirrors
    ``scripts/run_precomp.py::run_wave``'s own loop shape, one level down
    (one chunk's items, not a whole wave's meetings)."""

    outcomes: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    for item in chunk.items:
        if stop_file is not None and Path(stop_file).is_file():
            stopped_reason = f"stop-file present at {stop_file}, yielded before {item.item_id}"
            break
        if resume and g1_campaign.item_already_done(out_dir, item.meeting_id, item.arm):
            continue
        try:
            budget.check_before_item(item, seconds_per_request=seconds_per_request)
        except g1_campaign.G1BudgetExceeded as error:
            stopped_reason = str(error)
            break
        plan, slice_dir_relative = slice_plans_by_meeting_arm[(item.meeting_id, item.arm)]
        receipt = run_item(
            item, data_dir=data_dir, plan=plan, slice_dir_relative=slice_dir_relative, transport=transport,
            sink=sink, qa_questions=qa_questions,
        )
        budget.record(n_calls=receipt["n_calls"], gpu_seconds=receipt["gpu_seconds"], wall_seconds=receipt["wall_seconds"])
        g1_campaign.write_item_receipt(out_dir, receipt)
        outcomes.append(receipt)

    chunk_receipt = g1_campaign.build_chunk_receipt(
        chunk_index=chunk.index, item_outcomes=outcomes, budget_after=budget.to_dict(), stopped_reason=stopped_reason
    )
    g1_campaign.write_chunk_receipt(out_dir, chunk.index, chunk_receipt)
    return chunk_receipt


# ---------------------------------------------------------------------------
# whole-campaign planning
# ---------------------------------------------------------------------------


def build_plan(
    mode: str,
    *,
    data_dir: Path,
    derived_root: Path,
    nxt_corpus: NxtCorpus,
    vad_manifest_dir: Path | None,
    qa_questions: Sequence[Any],
    dev18: Sequence[str] = FROZEN_DEV_18,
    max_chunk_wall_seconds: float = g1_campaign.DEFAULT_MAX_CHUNK_WALL_SECONDS,
    seconds_per_request: float = g1_campaign.DEFAULT_SECONDS_PER_REQUEST,
) -> tuple[
    tuple[str, ...],
    dict[tuple[str, str], tuple[Any, str]],
    tuple["g1_campaign.WorkItem", ...],
    tuple["g1_campaign.Chunk", ...],
]:
    """Real-but-model-contact-free campaign planning: resolve the roster,
    rebuild every (meeting, arm)'s own slice plan from PRECOMP's on-disk
    cache, derive each work item's real transcribe-call count from the
    rebuilt plan's own slice count, and bin-pack into <=50-minute chunks.
    Re-derivable, deterministically, on every invocation -- module
    docstring's "no separate --plan-file" design."""

    meetings = g1_campaign.meetings_for_mode(mode, dev18=dev18)
    slice_plans = resolve_all_slice_plans(
        meetings, g1.ARMS, data_dir=data_dir, derived_root=derived_root, nxt_corpus=nxt_corpus,
        vad_manifest_dir=vad_manifest_dir,
    )
    n_transcribe_by_meeting_arm = {key: len(plan.slices) for key, (plan, _slice_dir) in slice_plans.items()}
    # Per-meeting QA routing (the G1-PATH structural NOT-PASS repair): each
    # meeting plans QA calls for ONLY the capped questions attached to it,
    # never the whole campaign-wide capped set -- so the total QA call count
    # is len(qa_questions) x len(ARMS_WITH_MINUTES_QA), never
    # len(meetings) x len(qa_questions) x len(ARMS_WITH_MINUTES_QA). A
    # meeting the cap drew zero questions for (e.g. IS1008a) plans zero QA
    # calls, not an error.
    n_qa_by_meeting = {meeting_id: len(g1.questions_for_meeting(qa_questions, meeting_id)) for meeting_id in meetings}
    work_items = g1_campaign.build_work_items(
        meetings, n_transcribe_by_meeting_arm=n_transcribe_by_meeting_arm, n_qa_by_meeting=n_qa_by_meeting
    )
    chunks = g1_campaign.plan_chunks(
        work_items, max_chunk_wall_seconds=max_chunk_wall_seconds, seconds_per_request=seconds_per_request
    )
    return meetings, slice_plans, work_items, chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_transport_and_budget(
    *, base_url: str, model_path: str, model_sha256: str, max_calls: int, slots: int, timeout_seconds: float
) -> LlamaServerTransport:
    from meeting_minutes_agent.chunking.constants import TRANSPORT_SLICE_MAX_S

    call_budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_calls * TRANSPORT_SLICE_MAX_S))
    return LlamaServerTransport(TransportConfig(base_url=base_url, slots=slots, timeout_seconds=timeout_seconds), call_budget)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True, choices=("path", "floors"))
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument("--out-dir", default=None, help="receipts root; defaults to docs/checks/2026-08-19-g1-<mode>/")
    parser.add_argument(
        "--derived-root-relative", default=DEFAULT_DERIVED_ROOT_RELATIVE,
        help="data-root-relative root for PRECOMP's RTTM/slice bytes -- never committed",
    )
    parser.add_argument("--vad-manifest-dir", default=None, help="directory of Z-nodiar's per-meeting SlicePlan JSON")
    parser.add_argument("--meetingqa-root", default=None)
    parser.add_argument("--ami-root", default=None)
    parser.add_argument("--ami-annotations-root-relative", default="datasets/ami/annotations/manual_1.6.2")
    parser.add_argument("--qa-cap", type=int, default=g1.QA_CAP_N)
    parser.add_argument("--qa-seed", type=int, default=g1.QA_CAP_SEED)
    parser.add_argument("--max-chunk-wall-seconds", type=float, default=g1_campaign.DEFAULT_MAX_CHUNK_WALL_SECONDS)
    parser.add_argument("--seconds-per-request", type=float, default=g1_campaign.DEFAULT_SECONDS_PER_REQUEST)
    parser.add_argument("--max-calls", type=int, default=g1_campaign.CAMPAIGN_MAX_CALLS)
    parser.add_argument("--max-gpu-hours", type=float, default=g1_campaign.CAMPAIGN_MAX_GPU_HOURS)
    parser.add_argument("--max-wall-hours", type=float, default=g1_campaign.CAMPAIGN_MAX_WALL_HOURS)
    parser.add_argument(
        "--summary-only", action="store_true",
        help="print the resolved roster/arms/QA-cap count and exit -- no PRECOMP-cache I/O, no model contact",
    )
    parser.add_argument("--list-chunks", action="store_true", help="rebuild every slice plan and print the full chunk plan JSON, then exit")
    parser.add_argument("--run-chunk", type=int, default=None, help="run exactly this chunk index")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-file", default=None)
    parser.add_argument("--server-cmd", nargs="+", default=None, help="argv to launch llama-server as a CHILD of this invocation")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--model-sha256", default=None)
    parser.add_argument("--slots", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--health-timeout-seconds", type=float, default=g1_campaign.DEFAULT_HEALTH_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir) if args.out_dir is not None else default_out_dir(args.mode)
    derived_root = data_dir / args.derived_root_relative
    vad_manifest_dir = Path(args.vad_manifest_dir) if args.vad_manifest_dir is not None else None

    if args.qa_cap != g1.QA_CAP_N or args.qa_seed != g1.QA_CAP_SEED:
        print(
            f"WARNING: --qa-cap/--qa-seed override the registered N={g1.QA_CAP_N}/seed={g1.QA_CAP_SEED} "
            "(floors prereg SS2) -- only for machinery testing, never for a registered flight",
            file=sys.stderr,
        )

    registry = load_role_registry()

    qa_questions: tuple[Any, ...] = ()
    if args.meetingqa_root is not None and args.ami_root is not None:
        all_questions = g1_campaign.load_dev18_usable_discovery_questions(
            meetingqa_root=args.meetingqa_root, ami_root=args.ami_root, registry=registry
        )
        qa_questions = g1.select_capped_qa_questions(all_questions, cap=args.qa_cap, seed=args.qa_seed)

    if args.summary_only:
        meetings = g1_campaign.meetings_for_mode(args.mode)
        payload = {
            "mode": args.mode,
            "meetings": list(meetings),
            "arms": list(g1.ARMS),
            "n_work_items": len(meetings) * len(g1.ARMS),
            "n_qa_questions_capped": len(qa_questions),
            "ceilings": {
                "max_calls": args.max_calls,
                "max_gpu_hours": args.max_gpu_hours,
                "max_wall_hours": args.max_wall_hours,
                "max_chunk_wall_seconds": args.max_chunk_wall_seconds,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    nxt_corpus = NxtCorpus(data_dir / args.ami_annotations_root_relative)

    if args.list_chunks:
        _meetings, _plans, work_items, chunks = build_plan(
            args.mode, data_dir=data_dir, derived_root=derived_root, nxt_corpus=nxt_corpus,
            vad_manifest_dir=vad_manifest_dir, qa_questions=qa_questions,
            max_chunk_wall_seconds=args.max_chunk_wall_seconds, seconds_per_request=args.seconds_per_request,
        )
        print(
            json.dumps(
                {
                    "n_work_items": len(work_items),
                    "n_chunks": len(chunks),
                    "chunks": [c.to_dict(seconds_per_request=args.seconds_per_request) for c in chunks],
                },
                indent=2, sort_keys=True,
            )
        )
        return 0

    if args.run_chunk is None:
        parser.error("--run-chunk is required for a real invocation (omit only with --summary-only/--list-chunks)")

    missing = [
        name for name, value in (
            ("--server-cmd", args.server_cmd), ("--base-url", args.base_url),
            ("--model-path", args.model_path), ("--model-sha256", args.model_sha256),
        )
        if value is None
    ]
    if missing:
        parser.error(f"the following arguments are required for a real chunk run: {missing}")

    _meetings, slice_plans, work_items, chunks = build_plan(
        args.mode, data_dir=data_dir, derived_root=derived_root, nxt_corpus=nxt_corpus,
        vad_manifest_dir=vad_manifest_dir, qa_questions=qa_questions,
        max_chunk_wall_seconds=args.max_chunk_wall_seconds, seconds_per_request=args.seconds_per_request,
    )
    if not (0 <= args.run_chunk < len(chunks)):
        parser.error(f"--run-chunk {args.run_chunk} out of range: this plan has {len(chunks)} chunk(s)")
    chunk = chunks[args.run_chunk]

    budget = g1_campaign.G1Budget(max_calls=args.max_calls, max_gpu_hours=args.max_gpu_hours, max_wall_hours=args.max_wall_hours)
    budget.precharge(g1_campaign.load_item_receipts(out_dir))

    transport = build_transport_and_budget(
        base_url=args.base_url, model_path=args.model_path, model_sha256=args.model_sha256,
        max_calls=args.max_calls, slots=args.slots, timeout_seconds=args.timeout_seconds,
    )
    sink_path = out_dir / "responses" / f"chunk{args.run_chunk:04d}-responses.jsonl"

    server = g1_campaign.ManagedLlamaServer(
        args.server_cmd, base_url=args.base_url, health_timeout_seconds=args.health_timeout_seconds
    )
    with server, ResponseSink(sink_path) as sink:
        chunk_receipt = run_chunk(
            chunk, data_dir=data_dir, slice_plans_by_meeting_arm=slice_plans, transport=transport, sink=sink,
            qa_questions=qa_questions, out_dir=out_dir, resume=args.resume, budget=budget,
            stop_file=args.stop_file, seconds_per_request=args.seconds_per_request,
        )

    print(json.dumps({"chunk_index": chunk.index, "n_ok": chunk_receipt["n_ok"], "n_error": chunk_receipt["n_error"], "stopped_reason": chunk_receipt["stopped_reason"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
