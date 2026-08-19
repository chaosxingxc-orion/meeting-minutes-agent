# The cold-cache tier: generation, storage, and cross-session reuse

`README.md` in this directory documents the patch series end to end, including the on-disk tier.
This file exists because that narrative is spread across several README paragraphs and a reader
who only wants "how do I generate and reuse cold-cache entries myself" has to reassemble it. This
is that reassembly, plus the standalone tooling this repository ships for it
(`scripts/build_featcache.py`). Nothing here contradicts `README.md`; where the two overlap, this
file is the more detailed account and `README.md` is the summary.

## Two tiers, two lifetimes

The patch (`patches/0001`-`0004`, applied to `tools/server/server-context.cpp`) maintains exactly
two storage tiers for one audio chunk's encoder embedding, checked in this order on every chunk a
request needs decoded:

1. **Hot tier — the RAM map.** A single, process-wide `static std::unordered_map<std::string,
   std::vector<float>>` (`feat_ram`, mutex-guarded), function-local to the code block inside
   `server_slot`'s decode path. "Process-wide" and "function-local static" both matter: it is
   shared across every request and every slot the *same* `llama-server` process ever serves, and
   it is initialized exactly once, on that process's first pass through this code. Its lifetime is
   the server process's own lifetime — every entry is lost when the process exits, restarts, or
   crashes. This is the tier `README.md` calls "in-HBM/RAM behavior during serving": no disk I/O on
   a hit once an entry is RAM-resident.
2. **Cold tier — the on-disk directory.** One file per cache entry, under whatever directory
   `LLAMA_MTMD_FEAT_CACHE_DIR` named at server-process start (read via a function-local `static
   const char * feat_dir = std::getenv(...)`, so — like the RAM map — it is captured once, on this
   process's first pass through the code, not re-read per request). If that variable is unset, the
   whole cache degrades to RAM-only for that process's lifetime: nothing is ever written to disk,
   and nothing is ever read from disk. This tier's lifetime is **until a human deletes something**:
   it survives server restarts, survives a crash, survives a completely different `llama-server`
   process on the same machine days later — the only thing this program's own engineering treats
   as its natural life span (see "Invalidation" below).

A cache **hit** decodes straight from whichever tier answered first (RAM checked before disk) and
skips the encoder entirely. A cache **miss** runs the stock encode path, then back-fills *both*
tiers before returning — RAM always, disk only if `LLAMA_MTMD_FEAT_CACHE_DIR` is set. A hit that
came from disk is itself promoted into RAM on the way out (`feat_load`'s final step), so the first
process-lifetime read of an entry pays one file read; every subsequent read of that same key by
that same process is RAM-only until the process exits.

## Cache key and entry format, exactly as the patch writes them

The key (final form, after all four patches — see `patches/0002`-`0004` for the forensics that
produced it):

```
<sanitized chunk id>_o<media ordinal>
```

- `<sanitized chunk id>` is `mtmd_input_chunk_get_id(chunk)` — an FNV content hash of the chunk's
  *bitmap* (the whole audio buffer a request's `input_audio` part decoded into, not one 30 s
  encoder-grid slice of it) — with every non-alphanumeric character replaced by `_`.
- `<media ordinal>` is this chunk's position among same-id chunks in the prompt, computed by
  walking `input_tokens.find_next_media_chunk(...)` from the start of the prompt up to (but not
  including) this chunk's own start position and counting how many prior chunks share this chunk's
  id. This exists because the bitmap id alone is **shared by every encoder-grid chunk cut from one
  audio buffer** — a 90 s slice, for instance, decodes into three 30 s chunks (`ENCODER_CHUNK_S` =
  30.0 s, `tools/mtmd/mtmd-audio.cpp`'s `frames_per_chunk = 3000`) that all report the *same*
  `mtmd_input_chunk_get_id`. Without the ordinal, every chunk after the first would either collide
  with the first chunk's entry (patch 0001's bug: 382 false hits across 52 slices) or with each
  other under a fragile positional scheme (patch 0002's `_i<chunk_idx>` attempt: broke under
  rolling-tail drift at a 60% hit rate) or — the specific bug patch 0004 fixed — collapse even
  ordinals onto odd ones because `find_next_media_chunk`'s upper bound was off by one. The ordinal
  scheme as shipped is invariant to how much text precedes the audio in a request, which is what a
  bitmap-content-hash key needs to stay stable across differently-worded requests carrying the same
  audio.

The on-disk entry: `<feat_dir>/<key>.feat`, a flat binary file with no version field and no
checksum beyond the shape check `feat_load` performs on read:

```
[uint64 n_tokens] [uint64 n_embd_model]   -- 16-byte header, native size_t/endianness
[float32 × (n_tokens * n_embd_model)]     -- the raw embedding, native byte order
```

Written via `<key>.feat.tmp`, `fwrite`d in full, then `rename()`d over the final path — a crash or
a concurrent reader mid-write either sees the old file (rename hasn't happened) or the new one
(rename is atomic on the same filesystem), never a half-written one. On read, `feat_load` recomputes
the expected `n_tokens`/`n_embd_model` for the chunk it is trying to decode and refuses (falls back
to the miss/encode path) unless both header fields match exactly — the *only* structural
correctness check this format carries. Any other read/write/open failure on the disk path is
likewise treated as a plain miss, never a hard error (`README.md`'s "fail-safe fallback"): a
request always completes via the stock encode path if the cache misbehaves.

## The `<dataset>-<encoder>` directory convention — and what it actually buys you

**The patch itself has no concept of a dataset or an encoder.** It reads exactly one path from
`LLAMA_MTMD_FEAT_CACHE_DIR` and treats it as a flat bucket of `<key>.feat` files; it never asks
where the directory lives on disk beyond that string, and the key format above encodes neither a
dataset name nor an encoder/GGUF identity. `<root>/<dataset>-<encoder>/` is a convention this
program's Python layer imposes on top — in this repository, `src/meeting_minutes_agent/client/
featcache.py` (`campaign_cache_dir`, `server_env`); the sibling `speech-aware-evidence-acquisition`
study documents the same rule independently in its own `docs/featcache-directories.md` (see that
file's provenance note in `featcache.py`'s module docstring — this repository reimplements the
convention, small; it imports no code from that study).

Why this is a safety mechanism and not just tidy naming: a cached embedding is valid **only** for
the exact encoder build that produced it. The key's FNV content hash is a hash of *audio bytes*, so
two different (dataset, encoder) pairs that happen to decode overlapping or identical audio bytes
would — absent directory separation — collide on the *same* key, and the patch's only defense
against serving the wrong encoder's features is the header's `n_embd_model` check, which catches a
**dimension** mismatch, nothing else. Two encoders that happen to share an embedding width would
collide silently: the header check would pass, and a request would decode from an embedding no
encoder in that process ever actually produced. Directory separation is what actually prevents
this, by construction, since a given server process only ever reads the one `LLAMA_MTMD_FEAT_CACHE_
DIR` path it was launched with. This repository's `featcache.py` additionally hard-refuses
(`FeatCacheError`) any dataset/encoder pair that resolves onto, or nested under, the sibling SAEA
study's legacy `q4km` directory (a dataset-segment-less exception that study still depends on) —
never a valid target from this repository, so a fresh campaign here can never silently write into,
or read stale hits out of, another study's already-scored 26 GB cache.

## Invalidation

Three distinct axes, only one of which needs a person to act:

- **Encoder/GGUF change.** Nothing in the patch detects this beyond the coarse `n_embd_model`
  dimension check above. The operative discipline is entirely the directory convention: point a
  server running a new/different encoder at a *new* `<dataset>-<encoder>` directory, and the old
  directory's entries are simply never read by that process — there is no explicit "invalidate"
  action to take because a mismatched encoder is never handed the old directory's path in the first
  place, by construction of how the directory is chosen. Two encoder builds that share a directory
  name and an embedding width by accident of naming are outside what either the patch or this
  convention can catch; do not reuse an `<encoder>` segment for two different GGUF builds.
- **Slice-byte change.** This axis is self-invalidating and needs no action: a re-cut slice with
  even one different byte produces a different bitmap content hash and therefore a different key,
  so the old entry (still on disk, still keyed to the old bytes) is simply never looked up again —
  it becomes inert, not wrong. Re-cutting a corpus's slices with a different snap window, sample
  rate, or channel count will not serve stale features; it will just leave the previous entries
  as harmless orphans under the same directory.
- **Manual invalidation.** The patch provides no cache-clearing or pruning tool of its own — the
  only supported way to force a re-encode of specific content is to delete the corresponding
  `<key>.feat` file(s), or the whole `<dataset>-<encoder>` directory, from outside the server
  process. Two things to know about deletion's timing: (1) it only takes full effect for a *new*
  server process — the RAM tier of an already-running process keeps serving whatever it already
  loaded, since RAM entries are never invalidated by a disk-side change; (2) `feat_store`'s own
  back-fill is write-once-per-process-per-key (`if (feat_ram.count(key)) return;` before ever
  touching disk on a normal, non-`VALIDATE` store) — so deleting a `.feat` file and expecting the
  *same still-running* process to re-write it on the next request touching that key will not work;
  restart the server to actually force a re-encode of deleted entries.

## Generation paths

Two ways a cache entry gets written, both going through the exact same `feat_store` back-fill —
there is no separate "warm mode" flag inside the patch itself:

1. **Lazy back-fill on first ordinary encode.** Any real request that causes the server to encode a
   chunk it has not seen before warms that chunk's entry as an incidental side effect of serving the
   request normally — nothing about the request needs to look like a "warm-up" call.
2. **Explicit warm pass.** A request engineered to trigger the encode step as cheaply as possible,
   with its generated text thrown away unread. This program's warm-pass primitive is
   `src/meeting_minutes_agent/precomp/encode_warm.py::encode_warm_slice` (and the manifest-driven
   `encode_warm_manifest` built on top of it for the internal PRECOMP pipeline): a
   `transcribe-only`-template request capped at `max_tokens=1` (`DEFAULT_ENCODE_WARM_MAX_TOKENS`),
   whose only purpose is to make the frozen core's encoder run once over the given audio bytes.
   `encode_warm_slice` never binds the reply text to any name (see that module's own docstring for
   the structural discard-unread proof) — the module cares about warming the cache, never about
   what the model said.

Both paths write identically-shaped `.feat` files; nothing downstream can tell which path produced
a given entry.

## `LLAMA_MTMD_FEAT_CACHE_VALIDATE`

An audit mode, not a production mode (`README.md`'s own warning, repeated here because it is easy
to reach for by mistake when debugging a suspected cache-correctness issue): setting this variable
to any value makes the patch (a) **never** take the cache-hit shortcut — every chunk is always
encoded, so `VALIDATE` mode pays full encoder cost on every single chunk, the opposite of what the
cache exists for — and (b) on every store, if that key is already RAM-resident, `memcmp` the fresh
encoder output against the cached bytes and log `feat-cache VALIDATE MATCH` or `... MISMATCH`. A
mismatch **overwrites the RAM entry** with the freshly-encoded "truth" but does **not** rewrite the
on-disk `.feat` file — a `VALIDATE` run that finds and silently repairs a stale RAM entry leaves the
disk file exactly as wrong as it was; restart the server (so the repaired-in-RAM-only entry is
dropped) and delete the offending `.feat` file to actually fix the disk copy. Use this mode to
confirm a cache-key scheme is collision-free on real data (exactly how patches 0002-0004 were
diagnosed, per their own commit messages) — never to warm a cache, and never left on for a timed
run.

## Cross-references

- `README.md` (this directory) — the patch series' own account of what it does, why this program
  needs it, and how to reproduce the build. Read that first if you have not already.
- `src/meeting_minutes_agent/client/featcache.py` — this repository's `<dataset>-<encoder>`
  directory router (`campaign_cache_dir`, `server_env`, the fixed `LLAMA_MTMD_FEAT_CACHE_DIR` name
  constant `SERVER_ENV_VAR`).
- `src/meeting_minutes_agent/precomp/encode_warm.py` — the reusable warm-pass primitive
  (`encode_warm_slice`, `encode_warm_manifest`) this repository's own PRECOMP pipeline uses to warm
  the cache ahead of a real flight.
- `scripts/build_featcache.py` — a standalone command-line generator built on top of
  `encode_warm_slice` for anyone who has their own audio slices and an already-running patched
  server, but no need for this repository's full per-meeting diarization/slicing pipeline. See that
  script's own `--help` for usage; the short version:

  ```bash
  # directory of loose slice files
  python scripts/build_featcache.py \
      --audio-dir /path/to/my/slices \
      --server-url http://127.0.0.1:8080 \
      --cache-dir /path/to/feat-cache/my-dataset-my-encoder

  # a JSON manifest instead of a directory (see the script's own docstring
  # for the two accepted manifest shapes)
  python scripts/build_featcache.py \
      --manifest /path/to/manifest.json \
      --server-url http://127.0.0.1:8080 \
      --dataset my-dataset --encoder my-encoder
  ```

  It reports a before/after `*.feat`-entry count for the cache directory as a whole, and — when
  `--cache-dir` (or `--dataset`/`--encoder`) is given so the entry count is observable — a
  per-slice `"encoded (new cache entry written)"` / `"already-cached (no new cache entry)"` status,
  which is the same operational hit/miss signal `README.md` recommends watching for by hand (an
  unchanged cache directory across a run). Running it twice over the same slices is safe: the
  second run's entry count does not grow, because every request already back-filled on the first
  run comes back as a hit on the second (module docstring, `precomp/encode_warm.py`'s own
  write-once-per-key back-fill rule above).
- `docs/checks/2026-08-19-precomp-wave1/script-serve.sh` — a real example of launching a patched
  `llama-server` with `LLAMA_MTMD_FEAT_CACHE_DIR` set from this program's own environment script.

## Provenance note

No piece of this cold-cache *generation* lifecycle was found living only outside this repository at
the time this file was written. The sibling `speech-aware-evidence-acquisition` study documents the
same directory convention (`docs/featcache-directories.md`, already cross-referenced above and in
`featcache.py`'s own docstring) but never shipped a standalone, reusable warm-pass generator either
— its own cache-inspection tooling under `docs/checks/speech-aware-evidence-acquisition/2026-08-16-
p2-r0bias-salvage/` (`featcache_check.sh`, `featcache_dir.sh`) is ad hoc, one-off forensic shell
scripts built to debug a specific live incident (`ls`/`find`/`grep` over a running server's log and
cache directory), not a tool meant for reuse, and that study's own cache warming has always
piggy-backed on real, full transcription flights (the lazy-back-fill path above), never a dedicated
warm-only pass. `scripts/build_featcache.py` is this program's first standalone tool for this job.
