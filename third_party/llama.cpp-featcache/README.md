# llama.cpp featcache patch series

A 4-commit patch series against upstream [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
that adds a per-dataset, on-disk cache of `mtmd` (multimodal) encoder embeddings to
`llama-server`. This program calls it "featcache". See `UPSTREAM` for the exact base/tip hashes
and a per-commit breakdown; see `patches/` for the patches themselves.

## What it does

Qwen3-Omni's audio path runs each input audio chunk through an encoder to produce an embedding
(`embd`) before the LLM ever sees it. This patch intercepts that step inside
`tools/server/server-context.cpp`:

- **Cache key**: each `mtmd_input_chunk` carries a bitmap-level content id. Because that id is
  shared across every chunk cut from one audio buffer, the key also folds in the chunk's
  **media ordinal** — its position among same-id chunks in the prompt, counted by walking
  `input_tokens.find_next_media_chunk(...)` up to the chunk's own start — so distinct chunks of
  the same buffer never collide. (Two earlier key schemes are visible in the patch history and
  both failed in measured ways before this one landed: a raw shared-id key produced 382 false
  hits across 52 slices by injecting the first chunk's features into every later chunk; a
  position-based key broke under rolling-tail drift, at 60% hit rate. A final off-by-one fix
  corrects a `find_next_media_chunk` upper-bound that had been collapsing even ordinals onto odd
  ones. See `patches/0002`-`0004` commit messages for the forensics.)
- **Storage**: a RAM layer (an in-process `unordered_map<key, vector<float>>`, mutex-guarded)
  backed by an optional on-disk directory, read from the environment variable
  `LLAMA_MTMD_FEAT_CACHE_DIR` at process start. If that variable is unset, the cache is RAM-only
  for the process's own lifetime.
- **Hit path**: skips the encoder entirely and decodes straight from the cached embedding
  (`mtmd_helper_decode_image_chunk` called with the cached buffer in place of a freshly-encoded
  one). This is the entire point: encoding is the expensive step; decoding from a cached
  embedding is comparatively cheap.
- **Miss path**: encodes as stock llama.cpp does, then back-fills both the RAM map and (if
  `LLAMA_MTMD_FEAT_CACHE_DIR` is set) an on-disk `<key>.feat` file (binary: an `{n_tokens,
  n_embd}` header followed by the raw `float` embedding, written to a `.tmp` path and atomically
  `rename()`d into place).
- **Fail-safe fallback**: any read/write/header-mismatch failure on the disk path is treated as a
  miss, never a hard error — the request always still completes via the stock encode path.
- **Hit logging is deliberately quiet.** A hit does emit one `SLT_INF`-level log line
  (`"mtmd feat-cache HIT, chunk idx = %zu"`), but `SLT_INF` is llama.cpp's info-level slot log,
  which does not print at this program's default server log verbosity. In practice, under the
  server invocations this program runs, a hit produces **no visible log line at all** — the only
  observable trace of a hit is the *absence* of the encoder-side log activity a miss would
  otherwise produce, plus an unchanged on-disk cache directory (no new `.feat` file, no growth in
  entry count or byte total). That is also this program's standard way of proving cache hits
  operationally: watch for zero "encoding" log lines plus an untouched cache directory across a
  run, rather than grep for a hit-specific string.
- **Optional validate mode**: setting `LLAMA_MTMD_FEAT_CACHE_VALIDATE` (to any value) switches the
  cache into an audit mode — every chunk is always encoded (the cache is never read to skip
  encoding), and a *stored* cache entry is byte-compared (`memcmp`) against the freshly-computed
  embedding on every store, logging `VALIDATE MATCH` or `VALIDATE MISMATCH` (and, on mismatch,
  overwriting the cache entry with the freshly-encoded "truth"). This mode is for verifying cache
  correctness, not for production runs — it does not skip encoder cost, it adds a comparison on
  top of it.

### Cache directory convention

Callers do not point `LLAMA_MTMD_FEAT_CACHE_DIR` at a bare root. This program's convention (kept
in each consuming repository's own Python wrapper, e.g.
`studies/speech-aware-evidence-acquisition/docs/featcache-directories.md` and this repository's
`src/meeting_minutes_agent/client/featcache.py`) is one subdirectory per `(dataset, encoder)`
pair:

```
<root>/<dataset>-<encoder>/
```

e.g. `/home/chao/feat-cache/ami-q4km` for the `ami` dataset against the `q4km`-quantized encoder.
This is enforced entirely on the Python/caller side — the C++ patch itself only ever sees one
directory path per server process, exactly as handed to it in `LLAMA_MTMD_FEAT_CACHE_DIR`. The
convention exists because a cached embedding is encoder-specific (produced by one exact mmproj
build) and is only ever valid for a server running that same encoder; mixing datasets or encoders
under one shared directory risks silent cross-contamination of unrelated runs' cached features.

## Why this program needs it

Every experiment in this program re-serves the same audio slices repeatedly — across arms of a
comparison, across repeated runs for variance, across resumed/retried flights. Qwen3-Omni's audio
encoder is the dominant per-request cost on this hardware (see, e.g., this program's own
`docs/readiness/2026-08-09-serving-config-decision.md` and
`docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md` for measured per-slice timings).
Stock llama.cpp re-encodes an audio chunk from raw samples on every single request that touches
it, even when the exact same chunk was already encoded in a previous request or a previous run.

With a warm featcache, a repeated slice becomes a **decode-only flight**: the encoder is skipped
entirely and the server proceeds directly from a cached embedding. Measured on this program's own
hardware in the sibling `speech-aware-evidence-acquisition` study repository, this cuts wall time
to roughly 4.5x the CPU-encode baseline once the cache is warm (that repository's git history,
commit `12590d4`, "consume(toolB): lexicon v3-backlog aligned - 3690/3690 on GPU at 4.5x the CPU
baseline"). For a research program that reruns the same audio corpus under many experimental
conditions, this is the difference between each new arm paying full encoder cost again and each
new arm paying only decode cost.

## How to reproduce the build

1. **Clone upstream at the pinned base commit.**

   ```bash
   git clone https://github.com/ggml-org/llama.cpp
   cd llama.cpp
   git checkout fdbd6abee20e408de21e90ca77a24cd50a6ea073
   ```

2. **Apply the patch series in order.**

   ```bash
   git am /path/to/third_party/llama.cpp-featcache/patches/*.patch
   ```

   Expected resulting tip hash: `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`. (`git am` replays each
   commit with its original author/date/message, so a clean apply against an unmodified base
   reproduces that exact hash. If you rebase, squash, or reorder, the hash will differ even
   though the resulting source tree is identical — the patches carry the tree change, not the
   commit graph.)

3. **Configure and build with CUDA.** This program's canonical build line (umbrella
   `scripts/env-setup.sh`, which pins the identical `LLAMACPP_COMMIT` used as this series' base)
   is:

   ```bash
   cmake -S llama.cpp -B llama.cpp/build -G Ninja \
         -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER="$CUDA_128/bin/nvcc" \
         -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_CURL=OFF
   cmake --build llama.cpp/build -j 6
   ```

   `-DCMAKE_CUDA_ARCHITECTURES=120` targets Blackwell (RTX 5090, sm_120) with CUDA 12.8
   (`$CUDA_128`, matching the program's pinned `torch` cu128 index — see the umbrella
   `CLAUDE.md`). Adjust `CMAKE_CUDA_ARCHITECTURES` and the CUDA toolchain path for your own GPU
   generation; the flags above are this program's own build, not a claim that they are the only
   correct choice.

   The resident build this program has actually run from reports binary sha256
   `097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68` for `build/bin/llama-server`
   (17,920 bytes; see e.g.
   `docs/checks/2026-08-19-precomp-wave1/runtime-identity.json` in this repository). Treat that
   hash as informational, not as a target to hit: compiled binary bytes depend on the exact
   compiler, CUDA toolkit patch version, and Ninja/cmake versions used, none of which are pinned
   as tightly as the source is. **The reproducible pin is the source tip hash
   (`5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`) from step 2, not the binary hash.** If your build
   produces a different binary sha256 from an identical source tree, that is expected toolchain
   variance, not a sign the patches applied incorrectly.

4. **Launch with this program's server flags.** The featcache layer is activated purely through
   an environment variable read once at process start; there is no CLI flag for it:

   ```bash
   LLAMA_MTMD_FEAT_CACHE_DIR=/path/to/cache/<dataset>-<encoder> \
     ./build/bin/llama-server \
       -m <model>.gguf --mmproj <mmproj>.gguf \
       -c 49152 -np 4 -fa on -ngl 999 -ctk q8_0 -ctv q8_0
   ```

   `-np 4` (four parallel slots, 12,288 tokens/slot) is this program's default serving
   configuration (`docs/readiness/2026-08-09-serving-config-decision.md`,
   `docs/readiness/2026-08-10-serving-config-verdict.md`). Individual flights that need the full
   49,152-token context in one sequence instead run `-np 1` — the same `-c`/`-fa`/`-ngl`/`-ctk`/
   `-ctv` values, just one slot instead of four (see e.g.
   `docs/checks/speech-aware-evidence-acquisition/2026-08-18-a2t-s2-flight/README.md` for a
   worked example of that swap). Optionally set `LLAMA_MTMD_FEAT_CACHE_VALIDATE=1` to run in
   audit mode instead of normal cache-skip mode (see "What it does" above).

## `verify.sh`

`verify.sh` applies the patch series to a fresh checkout of the pinned base commit and reports
the resulting tip hash and a diff-stat against the base, so a colleague can confirm their applied
tree matches this series without doing a full CUDA build. It makes no network calls beyond
`git clone`/`git fetch` and never touches this repository's own tree.

## License

llama.cpp is MIT-licensed (see upstream `LICENSE`). This patch series consists of textual diffs
against MIT-licensed upstream source and is redistributed here with upstream attribution; it
grants no rights beyond, and imposes no restriction on top of, upstream's own MIT license.
