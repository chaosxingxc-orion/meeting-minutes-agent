#!/usr/bin/env python3
"""Standalone cold-cache generator -- the piece a collaborator runs on
THEIR OWN audio, without this repository's full per-meeting diarization/
slicing pipeline.

Background (full account: ``third_party/llama.cpp-featcache/COLD-CACHE.md``):
the llama.cpp featcache patch (``third_party/llama.cpp-featcache/patches/``)
gives an ALREADY-RUNNING, patched ``llama-server`` a persistent, on-disk
cache of audio-chunk encoder embeddings under ``LLAMA_MTMD_FEAT_CACHE_DIR``.
A cache entry is written the same way regardless of what kind of request
caused it -- any real request that encodes a chunk the server has not seen
before back-fills that chunk's entry as a side effect. This script performs
nothing but that: it sends one minimal, generation-capped, reply-discarded
request per audio slice (:func:`meeting_minutes_agent.precomp.encode_warm.
encode_warm_slice` -- reused verbatim here, never duplicated) so the SERVER's
own encoder runs once over each slice's bytes and warms the cache, without
running this repository's diarization/manifest/budget machinery at all.

Two input modes (exactly one required):

- ``--audio-dir DIR``: every audio file directly under ``DIR`` (non-
  recursive), sorted by filename for a deterministic slice index.
- ``--manifest PATH``: a JSON manifest, either shape auto-detected per
  entry:

  1. a generic entry -- ``{"path": "<audio file>", "audio_seconds": 12.3}``
     (``audio_seconds`` optional; probed from the file's own header via
     ``soundfile`` when absent, exactly like directory mode);
  2. this repository's own :meth:`~meeting_minutes_agent.chunking.slicer.
     SliceManifest.to_dict` entry shape -- ``{"filename": "<name>", "start":
     <float>, "end": <float>, ...}``; ``filename`` resolves against
     ``--base-dir`` (default: the manifest file's own directory), duration
     is ``end - start``.

  The manifest's top level is either a bare JSON list of entries, or an
  object carrying an ``"entries"`` list (so this repository's own
  ``SliceManifest.to_dict()`` output can be passed straight through).

Hit/miss visibility: this script never talks to the server's own log (a hit
is deliberately near-silent -- ``COLD-CACHE.md``'s own note on
``SLT_INF``-level hit logging) and the transport layer here never learns
whether a given reply came from the encoder or the cache. Instead it
observes the SAME operational signal ``README.md`` recommends watching for
by hand: the ``*.feat``-entry count of the cache directory itself, sampled
immediately before and immediately after every individual slice's contact.
A slice whose contact grew the count is reported ``"encoded (new cache
entry written)"``; a slice whose contact left the count unchanged is
reported ``"already-cached (no new cache entry)"``. This needs
``--cache-dir`` (or ``--dataset``/``--encoder``, resolved the same way
``meeting_minutes_agent.client.featcache.campaign_cache_dir`` resolves a
server's own ``LLAMA_MTMD_FEAT_CACHE_DIR`` -- pass whichever one actually
matches the running server's own environment) to be observable at all; pass
neither and every slice is still sent, just reported ``"unknown"``.

Idempotent: running this script twice over the same slices is safe and
cheap. The first run's contacts back-fill the cache; the second run's
identical contacts come back as hits (the entry count does not grow) and
the request still completes normally -- a decode-only flight, per
``README.md`` -- so re-running this tool is never harmful and never
wasted beyond the (comparatively cheap) decode cost.

Reply text is never read (structural proof, not a promise): every per-slice
outcome this script prints or writes comes from
:func:`~meeting_minutes_agent.precomp.encode_warm.encode_warm_slice`'s own
return value, which never carries the model's reply text -- see that
module's own docstring for the "PROOF OF DISCARD" this script inherits
unchanged.

Usage::

    python scripts/build_featcache.py \\
        --audio-dir /path/to/my/slices \\
        --server-url http://127.0.0.1:8080 \\
        --cache-dir /path/to/feat-cache/my-dataset-my-encoder

    python scripts/build_featcache.py \\
        --manifest /path/to/manifest.json \\
        --server-url http://127.0.0.1:8080 \\
        --dataset my-dataset --encoder my-encoder
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.client.budgets import BudgetExceeded, BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.featcache import campaign_cache_dir  # noqa: E402
from meeting_minutes_agent.client.transport import (  # noqa: E402
    LlamaServerTransport,
    TransportConfig,
    TransportError,
)
from meeting_minutes_agent.precomp.encode_warm import (  # noqa: E402
    DEFAULT_ENCODE_WARM_MAX_TOKENS,
    encode_warm_slice,
)

#: Common slice-audio suffixes this script's directory mode globs for.
#: Non-recursive, sorted -- mirrors how this repository's own slicer writes
#: one flat directory of per-meeting slice files.
DEFAULT_AUDIO_EXTENSIONS = (".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac")

#: Used only when a slice's real duration cannot be read (directory mode,
#: or a manifest entry with neither "audio_seconds" nor "start"/"end") --
#: affects this script's own budget/report bookkeeping only. The file's raw
#: bytes are always sent as-is regardless of this value (mirrors
#: ``client.transport.build_request_payload``, which never decodes audio).
DEFAULT_FALLBACK_AUDIO_SECONDS = 30.0

#: The exact suffix ``patches/0001`` writes -- ``COLD-CACHE.md``'s "Cache
#: key and entry format" section. Used only to count entries; this script
#: never opens a ``.feat`` file's own bytes.
FEAT_FILE_SUFFIX = ".feat"


class BuildFeatCacheError(RuntimeError):
    """A slice-resolution or configuration error raised before any model
    contact is attempted."""


@dataclass(frozen=True)
class SliceInput:
    """One resolved slice to encode-warm: an audio file path plus its
    duration -- exactly what :func:`~meeting_minutes_agent.precomp.
    encode_warm.encode_warm_slice` needs, resolved once up front so both
    input modes (directory, manifest) converge on the same shape before any
    model contact happens."""

    index: int
    path: Path
    audio_seconds: float
    audio_seconds_source: str  # "measured" | "assumed" | "manifest"

    def request_id(self, prefix: str) -> str:
        return f"{prefix}-slice{self.index:04d}"


def _probe_duration(path: Path, fallback_seconds: float) -> tuple[float, str]:
    """Best-effort real duration via the SAME header-only read
    :func:`meeting_minutes_agent.chunking.slicer.read_audio_duration` uses
    (no full decode). Falls back to ``fallback_seconds`` (recorded source
    ``"assumed"``) for anything that call cannot read a header for -- this
    script always sends the file's own raw bytes regardless (module
    docstring), so an assumed duration only ever affects this script's own
    bookkeeping."""

    try:
        from meeting_minutes_agent.chunking.slicer import read_audio_duration

        return read_audio_duration(path), "measured"
    except Exception:
        return float(fallback_seconds), "assumed"


def discover_audio_files(directory: Path, *, extensions: Sequence[str] = DEFAULT_AUDIO_EXTENSIONS) -> list[Path]:
    """Every audio file directly under ``directory`` (non-recursive),
    sorted by name for a deterministic index assignment."""

    directory = Path(directory)
    if not directory.is_dir():
        raise BuildFeatCacheError(f"--audio-dir {directory} is not a directory")
    exts = {e.lower() for e in extensions}
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in exts)
    if not files:
        raise BuildFeatCacheError(f"no audio files found directly under {directory} with extensions {sorted(exts)}")
    return files


def resolve_slices_from_directory(
    directory: Path, *, fallback_seconds: float = DEFAULT_FALLBACK_AUDIO_SECONDS
) -> list[SliceInput]:
    files = discover_audio_files(directory)
    slices = []
    for i, path in enumerate(files):
        seconds, source = _probe_duration(path, fallback_seconds)
        slices.append(SliceInput(index=i, path=path, audio_seconds=seconds, audio_seconds_source=source))
    return slices


def _manifest_entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, Mapping) and isinstance(document.get("entries"), list):
        return document["entries"]
    raise BuildFeatCacheError(
        "manifest JSON must be either a top-level list of entries, or an object carrying an "
        f'"entries" list (this repository\'s own SliceManifest.to_dict() shape) -- got {type(document).__name__}'
    )


def resolve_slices_from_manifest(
    manifest_path: Path, *, base_dir: Path | None = None, fallback_seconds: float = DEFAULT_FALLBACK_AUDIO_SECONDS
) -> list[SliceInput]:
    """Module docstring: two entry shapes accepted, auto-detected per
    entry -- a generic ``{"path", "audio_seconds"}`` entry, or this
    repository's own ``{"filename", "start", "end"}`` slice-manifest entry
    shape. Either shape may set ``"index"`` explicitly; entries without one
    are numbered by their position in the manifest."""

    manifest_path = Path(manifest_path)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = _manifest_entries(document)
    if not entries:
        raise BuildFeatCacheError(f"manifest {manifest_path} carries no entries")
    resolved_base = Path(base_dir) if base_dir is not None else manifest_path.resolve().parent

    slices: list[SliceInput] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise BuildFeatCacheError(f"manifest entry #{position} is not a JSON object: {entry!r}")
        index = int(entry["index"]) if "index" in entry else position

        if "path" in entry:
            path = Path(entry["path"])
            if not path.is_absolute():
                path = resolved_base / path
        elif "filename" in entry:
            path = resolved_base / str(entry["filename"])
        else:
            raise BuildFeatCacheError(
                f'manifest entry #{position} carries neither "path" nor "filename": {entry!r}'
            )

        if "audio_seconds" in entry:
            seconds, source = float(entry["audio_seconds"]), "manifest"
        elif "start" in entry and "end" in entry:
            seconds, source = float(entry["end"]) - float(entry["start"]), "manifest"
        else:
            seconds, source = _probe_duration(path, fallback_seconds)

        slices.append(SliceInput(index=index, path=path, audio_seconds=seconds, audio_seconds_source=source))
    return slices


def count_cache_entries(cache_dir: Path | None) -> int | None:
    """Number of ``*.feat`` entries currently on disk under ``cache_dir`` --
    ``None`` when no cache directory is known (hit/miss becomes
    unobservable, module docstring). A cache directory that does not exist
    yet reads as zero, never a failure -- a cold-cold cache the server has
    not written to at all is a legitimate starting state, not an error."""

    if cache_dir is None:
        return None
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return 0
    return sum(1 for _ in cache_dir.glob(f"*{FEAT_FILE_SUFFIX}"))


def build_transport(
    *,
    base_url: str,
    timeout_seconds: float,
    slots: int,
    max_retries: int,
    max_calls: int,
    max_audio_seconds: float,
) -> LlamaServerTransport:
    call_budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    return LlamaServerTransport(
        TransportConfig(base_url=base_url, slots=slots, max_retries=max_retries, timeout_seconds=timeout_seconds),
        call_budget,
    )


def run_build(
    transport: LlamaServerTransport,
    slices: Sequence[SliceInput],
    *,
    cache_dir: Path | None,
    request_id_prefix: str,
    max_tokens: int = DEFAULT_ENCODE_WARM_MAX_TOKENS,
    on_slice: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """The generator's whole job: one encode-warm contact
    (:func:`~meeting_minutes_agent.precomp.encode_warm.encode_warm_slice`,
    reused, never duplicated) per slice, in index order, with a before/after
    ``*.feat``-entry-count delta observed around EVERY individual contact
    when ``cache_dir`` is given (module docstring). A
    :class:`~meeting_minutes_agent.client.budgets.BudgetExceeded` stops the
    run early and still returns whatever completed (``stopped_reason`` on
    the summary); any other per-slice failure (a
    :class:`~meeting_minutes_agent.client.transport.TransportError`, e.g. a
    missing file or an over-long slice, or an ``OSError`` reading it) is
    recorded as that slice's own ``"error: ..."`` status and the run
    continues with the next slice, so one bad file in a large batch never
    discards every other slice's already-collected result."""

    entries_before = count_cache_entries(cache_dir)
    outcomes: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    n_encoded = 0
    n_already_cached = 0
    n_unknown = 0
    n_error = 0

    for slc in slices:
        before = count_cache_entries(cache_dir)
        record: dict[str, Any] = {
            "index": slc.index,
            "path": str(slc.path),
            "audio_seconds": slc.audio_seconds,
            "audio_seconds_source": slc.audio_seconds_source,
        }
        try:
            outcome = encode_warm_slice(
                transport,
                request_id=slc.request_id(request_id_prefix),
                audio_path=slc.path,
                audio_seconds=slc.audio_seconds,
                max_tokens=max_tokens,
            )
        except BudgetExceeded as error:
            record["outcome_kind"] = "stopped"
            record["status"] = f"stopped: {error}"
            record["entries_added"] = None
            outcomes.append(record)
            if on_slice is not None:
                on_slice(record)
            stopped_reason = str(error)
            break
        except (TransportError, OSError) as error:
            record["outcome_kind"] = "error"
            record["status"] = f"error: {error}"
            record["entries_added"] = None
            n_error += 1
            outcomes.append(record)
            if on_slice is not None:
                on_slice(record)
            continue

        after = count_cache_entries(cache_dir)
        if before is None or after is None:
            record["outcome_kind"] = "unknown"
            record["status"] = "unknown (no --cache-dir given)"
            record["entries_added"] = None
            n_unknown += 1
        elif after > before:
            record["outcome_kind"] = "encoded"
            record["status"] = "encoded (new cache entry written)"
            record["entries_added"] = after - before
            n_encoded += 1
        else:
            record["outcome_kind"] = "already_cached"
            record["status"] = "already-cached (no new cache entry)"
            record["entries_added"] = 0
            n_already_cached += 1
        record.update(outcome)
        outcomes.append(record)
        if on_slice is not None:
            on_slice(record)

    entries_after = count_cache_entries(cache_dir)
    entries_added_total = (
        entries_after - entries_before if (entries_before is not None and entries_after is not None) else None
    )
    return {
        "cache_dir": str(cache_dir) if cache_dir is not None else None,
        "n_slices": len(slices),
        "n_encoded": n_encoded,
        "n_already_cached": n_already_cached,
        "n_unknown": n_unknown,
        "n_error": n_error,
        "entries_before": entries_before,
        "entries_after": entries_after,
        "entries_added_total": entries_added_total,
        "stopped_reason": stopped_reason,
        "slices": outcomes,
    }


def _resolve_cache_dir(args: argparse.Namespace) -> Path | None:
    if args.cache_dir is not None:
        return Path(args.cache_dir)
    if args.dataset is not None and args.encoder is not None:
        return campaign_cache_dir(args.dataset, args.encoder, root=args.featcache_root, create=False)
    if args.dataset is not None or args.encoder is not None:
        raise BuildFeatCacheError("--dataset and --encoder must be given together")
    return None


def _resolve_slices(args: argparse.Namespace) -> list[SliceInput]:
    if bool(args.audio_dir) == bool(args.manifest):
        raise BuildFeatCacheError("pass exactly one of --audio-dir or --manifest")
    if args.audio_dir:
        return resolve_slices_from_directory(Path(args.audio_dir), fallback_seconds=args.fallback_audio_seconds)
    base_dir = Path(args.base_dir) if args.base_dir else None
    return resolve_slices_from_manifest(
        Path(args.manifest), base_dir=base_dir, fallback_seconds=args.fallback_audio_seconds
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audio-dir", default=None, help="a flat directory of audio slice files (non-recursive)")
    parser.add_argument("--manifest", default=None, help="a JSON manifest of slice entries (module docstring)")
    parser.add_argument(
        "--base-dir", default=None,
        help='base directory manifest "filename" entries resolve against (default: the manifest file\'s own directory)',
    )
    parser.add_argument(
        "--server-url", required=True,
        help="an ALREADY-RUNNING patched llama-server base URL -- this script never starts one",
    )
    parser.add_argument(
        "--cache-dir", default=None,
        help="the SAME directory passed to the server as LLAMA_MTMD_FEAT_CACHE_DIR -- needed to observe hit/miss",
    )
    parser.add_argument(
        "--dataset", default=None,
        help="convenience alternative to --cache-dir: resolves <root>/<dataset>-<encoder>/ (needs --encoder too)",
    )
    parser.add_argument("--encoder", default=None, help="paired with --dataset")
    parser.add_argument("--featcache-root", default=None, help="override the root --dataset/--encoder resolve under")
    parser.add_argument("--request-id-prefix", default="build-featcache")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_ENCODE_WARM_MAX_TOKENS)
    parser.add_argument("--slots", type=int, default=1)
    parser.add_argument("--max-retries", type=int, default=1, help="matches TransportConfig's own default")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--max-calls", type=int, default=None,
        help="defaults to n_slices * (max-retries + 1) -- override only if you expect more retries than that",
    )
    parser.add_argument(
        "--max-audio-seconds", type=float, default=None,
        help="defaults to total slice audio_seconds * (max-retries + 1)",
    )
    parser.add_argument("--fallback-audio-seconds", type=float, default=DEFAULT_FALLBACK_AUDIO_SECONDS)
    parser.add_argument("--out-json", default=None, help="also write the full summary JSON here")
    parser.add_argument("--quiet", action="store_true", help="suppress the per-slice progress line on stderr")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    slices = _resolve_slices(args)
    cache_dir = _resolve_cache_dir(args)

    total_audio_seconds = sum(s.audio_seconds for s in slices)
    max_calls = args.max_calls if args.max_calls is not None else len(slices) * (args.max_retries + 1)
    max_audio_seconds = (
        args.max_audio_seconds
        if args.max_audio_seconds is not None
        else max(total_audio_seconds * (args.max_retries + 1), 1.0)
    )
    transport = build_transport(
        base_url=args.server_url,
        timeout_seconds=args.timeout_seconds,
        slots=args.slots,
        max_retries=args.max_retries,
        max_calls=max_calls,
        max_audio_seconds=max_audio_seconds,
    )

    def _progress(record: dict[str, Any]) -> None:
        if not args.quiet:
            print(f"[{record['index']:04d}] {record['path']} -> {record['status']}", file=sys.stderr)

    summary = run_build(
        transport,
        slices,
        cache_dir=cache_dir,
        request_id_prefix=args.request_id_prefix,
        max_tokens=args.max_tokens,
        on_slice=_progress,
    )

    payload = json.dumps(summary, indent=2, sort_keys=True)
    print(payload)
    if args.out_json:
        Path(args.out_json).write_text(payload + "\n", encoding="utf-8")
    return 0


__all__ = [
    "BuildFeatCacheError",
    "SliceInput",
    "discover_audio_files",
    "resolve_slices_from_directory",
    "resolve_slices_from_manifest",
    "count_cache_entries",
    "build_transport",
    "run_build",
    "build_arg_parser",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
