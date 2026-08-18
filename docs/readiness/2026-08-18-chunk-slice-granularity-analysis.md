# Chunk / slice granularity: what the audio-token budget actually permits (2026-08-18)

Lock item (c) of the owner's 2026-08-18 G1 gate (`docs/plans/2026-08-17-founding-workplan.md` §4b.3).
CPU only, zero model contact, no downloads. Everything numeric below is either read out of the
pinned llama.cpp source, read out of a flown SAEA receipt, or computed from those two; nothing is
estimated from memory except the four planning reserves that are labelled as planning estimates.

## 0. Verdict, up front

| question | answer |
|---|---|
| audio-token rate | **exactly 13 tokens per audio-second** (780/min), floor-quantized to whole seconds |
| per-request context actually available | **12,288 tokens**, not 49,152 — `-c 49152 -np 4` divides per slot |
| max feasible audio in ONE request | **~9.9–11.3 min** at `-np 4`; ~42 min at `-np 1` |
| E3's "~40-min chunk as one core request" | **REFUTED.** 31,200 audio tokens = **2.54x the whole slot**; the server hard-refuses it |
| the SAEA ~90 s prior | **CONFIRMED — with a corrected justification** (see §5); 90 s is the top of a flat plateau, not a peak |
| single-pass mode for AMI dev meetings | **infeasible at the locked serving config**; see §7 |
| required design | **two-level: task chunk (topic unit, state/dispatch) vs transport slice (90 s, the actual request)** |

## 1. The audio-token rate, from the source and from flown receipts

The rate is not an estimate. It is a constant in the pinned build
(`/home/chao/llama.cpp-featcache`, commit `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`).

The flown mmproj (`mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…2883`) declares
`clip.audio.projector_type = qwen3a`. That projector's token count, `tools/mtmd/clip.cpp`
`clip_n_output_tokens`, case `PROJECTOR_TYPE_QWEN3A`:

```c
// chunk_size=100 frames --> 3x stride-2 conv2d --> 13 tokens per chunk
const int chunk_size       = 100;
const int tokens_per_chunk = 13;
n_patches = (img->nx() / chunk_size) * tokens_per_chunk;
```

`img->nx()` is the mel frame count. The audio hparams for this projector family are
`audio_sample_rate = 16000`, `audio_hop_len = 160` — i.e. **100 mel frames per second**. So:

> **100 mel frames = 1.00 s of audio = 13 tokens.**
> **13 tokens per audio-second. 780 tokens per audio-minute.**

The integer division is a **floor**: the fractional final second of a slice contributes nothing
(up to 12 tokens dropped per request). This is a rounding detail, not a saving to design around.

Two further mechanical facts, both binding on the design:

- **The encoder works on a 30-second grid.** `tools/mtmd/mtmd-audio.cpp`: *"because the cgraph in
  clip.cpp only accepts 3000 frames each, we need to split the mel"*, `frames_per_chunk = 3000`
  = 30.0 s = **390 tokens per encoder chunk**. A transport slice is internally a sequence of
  30 s encoder chunks; a slice length that is not a multiple of 30 s ends on a partial chunk.
- **The feature cache is keyed per encoder chunk.** The SAEA featcache patch keys on a
  bitmap-level content id plus a media ordinal, so a cache entry is *(this exact audio content,
  this chunk position)*. Byte-identical audio hits; anything that shifts the bytes misses.

### Cross-checks against flown measurements

The constant reproduces three independent SAEA measurements taken on the same build:

| measurement | source | predicted at 13 tok/s | measured |
|---|---|---|---|
| least-squares fit over 614 real calls, 13–60 s slices | `docs/readiness/2026-08-09-segmentation-cost-model.md` | slope 13.0 | **slope 12.87** (R²=0.891), intercept 228 |
| 10 s slice protocol, per-request prompt | `2026-08-11-segmentation-efficiency-frontier.md` (slice10 probe) | 10x13 + 228 = 358 | **352** |
| 60 s slice protocol, per-request context | same, S0 row | 60x13 + 228 = 1,008 | **"~1,000"** |

The fitted slope sits just under 13.0 exactly as the floor-quantization predicts (a partial final
second is dropped on most calls, biasing the regression slope down by a few tenths). **The measured
12.87 and the source-exact 13.00 are the same number.** I use 13 for all arithmetic below.

The 2026-08-18 P-SLU flight (`SAEA-PROBE-pslu-n60`, attempt 4, 363/363 requests) is consistent:
132,516 prompt tokens over 1,101.24 audio-seconds. Its audio is SLURP utterances (mean 3.04 s), so
after floor-quantization ~11.9k tokens are audio and the remaining ~332 tokens/request are the arms'
roster and instruction text — the expected shape for that protocol. That flight cannot *isolate* the
rate (its per-request token counts are aggregated in the receipt), which is why the rate is taken
from the source and validated on the three slice-length measurements above.

## 2. The context budget is 12,288 tokens, not 49,152

The flown server argv (`attempt4-flight-receipt.json`, `session.argv`) is:

```
llama-server -m …Q4_K_M.gguf --mmproj …bf16.gguf -c 49152 -np 4 -fa on -ngl 999 -ctk q8_0 -ctv q8_0
```

`-c` is the **total** context, divided across slots. `tools/server/server-context.cpp`:
`slot.n_ctx = llama_n_ctx_seq(ctx_tgt)` (field comment: *"context size per slot"*), and
`llama_n_ctx_seq` returns `n_ctx / n_seq_max`. With `-np 4`:

> **Per-request context = 49,152 / 4 = 12,288 tokens.**

The model itself is not the limit (`qwen3vlmoe.context_length = 65536`), so the slot cap is purely a
serving choice — but it is the choice that is currently locked and flown.

Three properties of that ceiling make overrun a hard engineering failure rather than a soft
degradation:

1. **Context shift is force-disabled under mmproj.** `server-context.cpp`:
   `"ctx_shift is not supported by multimodal, it will be disabled"` — because *"an image chunk may
   contain multiple tokens"* and cannot be partially evicted. `cache_reuse` is disabled for the same
   reason.
2. **An oversized request is refused, not truncated:** `if (slot.task->n_tokens() > slot.n_ctx)` →
   `send_error(... "input (%d tokens) is larger than the max context size (%d tokens). skipping",
   ERROR_TYPE_EXCEED_CONTEXT_SIZE)` and the slot is released.
3. **Running out mid-generation stops the response**: with `ctx_shift` off, generation halts with
   `truncated = true` / `STOP_TYPE_LIMIT` once `prompt.n_tokens() + 1 >= slot.n_ctx`.

So the budget must hold **prompt + completion**, with margin, or the request either fails outright
or returns a silently amputated answer. Both failure modes are expensive in a long-form loop.

### Maximum feasible audio per request

A LISTEN request carries: instruction, the supply block, the carried tail, the audio, and the
generated completion. Transcription completions are **audio-proportional** — SAEA measured
≈2.55 completion tokens per audio-second, and speaker-attributed output is higher (4.0 used here as
a planning upper bound). So the budget equation is:

```
13*W  +  comp_rate*W  +  (instruction + supply + tail)  <=  0.9 * slot_ctx
```

| profile | slot | fixed reserve | comp rate | **max audio** |
|---|---|---|---|---|
| lean (SAEA-style instruction 228, supply 200, tail 100), ASR only | 12,288 | 528 | 2.55 | **677 s = 11.3 min** |
| meeting LISTEN (instruction 450, supply 400, tail 100), ASR only | 12,288 | 950 | 2.55 | **650 s = 10.8 min** |
| meeting LISTEN, transcription **+ attribution** | 12,288 | 950 | 4.0 | **595 s = 9.9 min** |
| same, at `-np 2` | 24,576 | 950 | 4.0 | 1,245 s = 20.8 min |
| same, at `-np 1` | 49,152 | 950 | 4.0 | 2,546 s = 42.4 min |
| degenerate audio-only ceiling (no text, no output) | 12,288 | 0 | 0 | 945 s = 15.8 min |

Instruction/supply/tail sizes are **planning estimates**; the audio rate, the completion rate and the
slot size are measured. Note the reserves barely matter: at 13 tok/s the audio term dominates, so the
ceiling is robust to a factor-of-two error in the text reserves.

## 3. The ~40-minute single request: refuted with numbers

E3 currently plans task chunks up to ~40 min and E7b sends a chunk's audio as one core request.

| quantity | value |
|---|---|
| audio | 2,400 s |
| **audio tokens** | **31,200** |
| + instruction/supply/tail | 32,150 prompt tokens |
| + transcription completion (2.55/s) | 6,120 tokens |
| **total context needed** | **~38,270** |
| vs the `-np 4` slot (12,288) | **3.11x — impossible** |
| vs the audio alone | 31,200 = **2.54x the whole slot** |
| vs `-np 1` (49,152) | 0.78x — fits |
| vs model train context (65,536) | 0.58x |

**At the locked serving config the request cannot be made.** It does not degrade; the server replies
`ERROR_TYPE_EXCEED_CONTEXT_SIZE` and releases the slot. The audio alone overflows the slot 2.5x
before a single word of prompt or output.

At `-np 1` it becomes arithmetically possible, and that is the option worth killing explicitly,
because "just set `-np 1`" is the obvious rescue. It is a bad trade on four measured grounds:

1. **Throughput collapse from decode-vs-context.** SAEA measured per-slot decode at 13.07 tok/s at
   816-token context, 6.31 at ~1,233, and 3.07–4.40 at ~4,700. Extrapolating that curve to ~38,000
   tokens gives ~2 tok/s at best. The 6,120-token transcription completion then takes ~51 minutes —
   **slower than real time**, on a single slot, with zero concurrency, against 5.5x real time
   measured at 4-way with 60 s slices. That is a 25–30x throughput loss.
2. **Concurrency is surrendered.** `-np 1` gives up the 4-way batching the owner's own G1 lock (b)
   asks to optimize ("maximal GPU parallelism… `obs_batch_samples` <= `-np`").
3. **Blast radius.** One failed or malformed request costs 40 minutes of audio and its full prefill
   and encode (~133 s of GPU encode alone at the measured 3.32 s per 60 s). There is no resume
   granularity below the chunk.
4. **It contradicts a standing owner directive on the same core.** SAEA 2026-08-08:
   *"the frozen core must never be asked to process a whole 40-75-minute earnings call in one
   request"*; the same document records that whole-call single requests **failed** and that the
   windowed sizes are *"far below the whole-call sizes that failed"*.

There is also a quality argument that is independent of cost: Qwen3-Omni's temporal grounding on
long audio is documented as poor (median timestamp deviation 11.8 s, 43 % within a 10 s tolerance —
`2026-08-10-segmentation-who-decides-the-cut.md`, citing arXiv:2602.08979 on this exact model), and
degradation with clip duration is a general finding for omni models.

## 4. What the SAEA "90 s optimum" actually claimed

Read from the four source documents rather than from recollection.

**What was claimed** (`2026-08-09-segmentation-cost-model.md`): projecting the measured cost model
onto 30,408 s of audio, 90 s non-overlapping slices cost **0.77x** the tokens of the shipped 60 s /
1.2x-overlap protocol, versus 1.02x at 30 s, 1.78x at 10 s and 2.92x at 5 s. The recommendation was
*"VAD-packed, non-overlapping, still long: cut only at a pause, pack consecutive speech up to a
60–90 s target."*

**Why 90 and not 900.** The token model alone is monotone — longer is always cheaper, because the
228-token intercept is charged per call. Three separate things set the ceiling:

1. **Pause availability.** Measured on 10 discovery files: a ≥1 s pause arrives every 12–55 s in
   9 of 10 files. A 60–90 s packing target is reachable at a real pause; much longer is not
   reliably reachable, and one file (4366522, 7 dB dynamic range) has no detectable silence at all.
2. **Seam count is the dominant error mechanism.** 86 % of all deletions (10,693 words, r=0.847)
   were made at overlap-dedup seams. Fewer, longer slices means fewer seams.
3. **Quality above 60 s was never measured.** 604 of 614 slices were exactly 60 s, so the study had
   no variation to regress quality against window length. The A-2a arm (30/60/90 s) was designed to
   supply exactly that and is not reported in these documents.

**Status of the number.** The "~90 s optimum" is a **cost-model projection with a pause-availability
ceiling**, corroborated by seam-count and reproducibility arguments — *not* a measured quality
optimum. The honest transfer statement is: 90 s was the longest slice SAEA could justify, not a
peak it had located.

**What transfers to meetings, and what does not:**

| SAEA finding | transfers? |
|---|---|
| 13 tok/audio-second; 228-token per-call intercept | **Yes** — same core, same build, same transport |
| per-call wall floor ~4.3 s; decode decays with context | **Yes** — serving properties, corpus-independent |
| fine slicing is catastrophic (10 s: +26.6 pp WER, 1.75x slower) | **Yes** — mechanism is seams and floor, not domain |
| model-declared boundaries drift and cascade | **Yes, and harder** — meetings are longer than earnings calls |
| "a ≥1 s pause every 12–55 s" | **Partly** — measured on continuous professional monologue. Meetings have MORE silence and more turn boundaries, so pause-packing to 90 s should be easier, not harder. But AMI/ICSI have **overlapped speech**, which earnings calls do not — a pause in a mixed-headset signal is rarer than a pause per speaker |
| overlap-dedup stitch is the deletion source | **Yes** — and it is why the meeting loop must not overlap either |
| 0.77x token saving at 90 s | **Directionally yes**, but tokens are not the binding unit here; wall clock is |

## 5. The real frontier: two opposing forces, and where the knee is

The SAEA cost table is one-sided — it counts only intercept amortization, so it says longer is always
better, which is what licensed the 40-minute assumption in the first place. The measured serving
constants supply the opposing force. Combining both, anchored on SAEA measurements:

```
latency(W) = 4.3 s floor  +  encode(W)  +  13W/470  +  completion(W)/decode(ctx)
decode(ctx) = 6.31 * (ctx/1233)^-0.4        [fitted on the 4-way points: 6.31@1233, ~3.7@4700]
wall per slice at -np 4 = latency / 4
```

Validation: this reproduces the measured locked-config figure — modelled 9.5 s wall per 60 s slice at
4-way against **10.8 s measured** (12 % under, acceptable for a planning model).

Real-time factor (higher is better), cold featcache / warm featcache:

| slice W | context | decode tok/s | wall/slice (4-way) | **RTF cold** | RTF warm |
|---|---|---|---|---|---|
| 15 s | 1,183 | 6.42 | 2.87 s | 5.23 | 5.64 |
| 30 s | 1,416 | 5.97 | 4.88 s | 6.15 | 6.72 |
| 45 s | 1,650 | 5.62 | 7.13 s | **6.31** | **6.92** |
| **60 s** | 1,883 | 5.33 | 9.50 s | **6.32** | **6.92** |
| **90 s** | 2,349 | 4.88 | 14.68 s | **6.13** | 6.70 |
| 120 s | 2,816 | 4.53 | 20.43 s | 5.87 | 6.39 |
| 180 s | 3,749 | 4.04 | 33.18 s | 5.42 | 5.86 |
| 300 s | 5,615 | 3.44 | 62.88 s | 4.77 | 5.11 |
| 600 s | 10,280 | 2.70 | 155.11 s | 3.87 | 4.09 |

**The frontier is a plateau, not a peak.** Throughput is flat within 3 % across **30–90 s**, falls
off below 30 s (the 4.3 s floor dominates), and declines monotonically above 90 s (−7 % at 120 s,
−14 % at 180 s, −25 % at 300 s, −39 % at 600 s) as decode-rate decay overtakes floor amortization.

Throughput therefore does not choose a value inside 30–90 s. **Seam count does**: seams are the
measured dominant error mechanism, and within a flat-throughput band the correct choice is the
longest slice, i.e. the top of the plateau. That is 90 s.

Three independent considerations agree on the same value:

- **90 s = exactly 3 encoder chunks** (3 x 30 s), so no partial final encoder chunk is wasted. 60 s
  and 120 s also align; 45 s and 75 s do not.
- **90 s is 20 % of a 12,288-token slot** (2,480 tokens incl. completion), leaving ~9,800 tokens of
  headroom for a supply block that will grow. SAEA's ConEC evidence blocks reached **1,850 tokens
  median and 5,835 worst-case** per call — a meeting glossary roster under dose caps will trend the
  same way, and at 90 s even the worst case still fits. At 300 s it would not.
- **Token cost per hour of audio** still favours 90 s over 60 s (84,800 vs 103,800 prompt tokens per
  audio-hour) — the SAEA argument, preserved but demoted to a tiebreak since this study pays GPU
  hours, not per-token fees.

**Verdict on the prior: CONFIRMED at 90 s, with the justification corrected.** The prior was right
about the value and incomplete about the reason. It is not "longer is always cheaper, capped by
pauses"; it is "throughput plateaus at 30–90 s and decays beyond, and within the plateau seam count
picks the top." The corrected reasoning is what makes 90 s defensible against the 40-minute
alternative, which the original monotone cost argument could not rule out.

## 6. What the corpora actually look like

Measured from headers and shipped annotation (no decode, no model contact).

**AMI dev-18** (frozen split, `Mix-Headset`, mono 16 kHz PCM, one mixed channel per meeting):
min 943.8 s (15.7 min), median 1,831.5 s (30.5 min), mean 1,933.4 s, p90 2,813.7 s,
max 2,970.0 s (49.5 min); total **34,801.8 s = 9.667 h** (matches the carrier manifest exactly).

**AMI topic layer** (`annotations/manual_1.6.2/topics/`, 139 files; **15 of the 18 dev meetings have
one — IB4001, IB4002, IB4004 have none**):

| unit | n | min | p10 | median | p90 | max | per meeting |
|---|---|---|---|---|---|---|---|
| top-level topic, full extent | 103 | 4.6 s | 33.2 s | **136.7 s** | 577.6 s | 1,514 s | 4 / 7 / 10 |
| leaf topic (atomic) | 175 | 4.6 s | 27.1 s | **79.8 s** | 302.1 s | 920 s | 4 / 10 / 41 |

Topic marks tile the meetings essentially without holes (91.7–98.5 % coverage for 14 of 15).

**ICSI** (present, 75 meetings, mono 16 kHz): median 3,382 s (56.4 min), max 6,157.8 s (102.6 min),
total 71.7 h — roughly 1.8x longer than AMI. Topic spans: median 273.6 s, p90 1,292.5 s.
Annotations ship as un-extracted ZIPs and no repo code reads ICSI yet.

**MeetingBank** agenda items (real audio spans from the shipped Legistar index, 6,894 items):
median 388 s, p75 1,160 s, p90 2,937 s, max 27,223 s; items per meeting median 5, p90 11. Items
cover 64.5 % of video time. The landed 50-meeting audio subset is **44.1 kHz stereo MP3** — the only
carrier that is not 16 kHz mono.

**The structural observation.** Natural task units across all three corpora sit in the **~130–600 s**
band at the median-to-p90 (AMI top-level 137/578, ICSI 274/1,293, MeetingBank item 388/2,937), while
AMI's *leaf* topics have a **median of 79.8 s — within 12 % of the 90 s transport figure derived
independently from the token budget.** Natural discourse units and the serving optimum are the same
order of magnitude. The ~40-minute cap is an order of magnitude above both, and is not a unit any
corpus exhibits.

## 7. Single-pass feasibility: zero of eighteen

For each dev-18 meeting: audio tokens = floor(seconds) x 13; single-pass context = audio + 950
reserve + completion.

| meeting | min | audio tokens | x the `-np 4` slot | fits `-np 4` | fits `-np 1` (ASR) | slices @90 s |
|---|---|---|---|---|---|---|
| IS1008a | 15.7 | 12,259 | **1.00** | no | yes | 11 |
| ES2011a | 18.6 | 14,469 | 1.18 | no | yes | 13 |
| TS3004a | 22.4 | 17,485 | 1.42 | no | yes | 15 |
| IS1008d | 24.7 | 19,240 | 1.57 | no | yes | 17 |
| IS1008c | 25.8 | 20,098 | 1.64 | no | yes | 18 |
| ES2011b | 26.4 | 20,553 | 1.67 | no | yes | 18 |
| ES2011c | 26.9 | 21,008 | 1.71 | no | yes | 18 |
| IB4001 | 29.7 | 23,140 | 1.88 | no | yes | 20 |
| IS1008b | 29.5 | 22,984 | 1.87 | no | yes | 20 |
| IB4002 | 31.4 | 24,466 | 1.99 | no | yes | 21 |
| ES2011d | 33.0 | 25,766 | 2.10 | no | yes | 23 |
| IB4003 | 33.7 | 26,299 | 2.14 | no | yes | 23 |
| TS3004b | 37.4 | 29,198 | 2.38 | no | yes | 25 |
| IB4004 | 39.9 | 31,096 | 2.53 | no | yes | 27 |
| IB4011 | 40.3 | 31,408 | 2.56 | no | yes | 27 |
| TS3004d | 45.9 | 35,750 | 2.91 | no | yes (ASR only) | 31 |
| IB4010 | 49.3 | 38,480 | 3.13 | no | **no** | 33 |
| TS3004c | 49.5 | 38,610 | 3.14 | no | **no** | 33 |

> **Not one of the 18 dev meetings fits in a single request at the locked serving config.**
> The shortest meeting in the split, IS1008a, spends **99.8 % of the entire 12,288-token slot on
> audio tokens alone** — 12,259 of 12,288, leaving 29 tokens for the system prompt, the supply
> block and the whole answer. Single-pass is not merely tight on this split; it misses on the audio
> term by itself, on the most favourable meeting.

At `-np 1` (49,152/slot), 16 of 18 fit for plain transcription and 15 of 18 with speaker
attribution; **IB4010 and TS3004c do not fit at any concurrency**. And the whole-split cost of doing
it that way is the counterfactual in §3: ~12.3 h of decode-bound single-slot wall per arm, versus
**1.44 h** at 90 s slices with a warm feature cache — **8.5x worse**, for a plan that still fails on
two meetings and forfeits all concurrency.

**Consequence for the current code.** `chunking/planner.py` uses `DEFAULT_WINDOW_CAP_S = 2400.0`
with `mode="auto"` collapsing to `single_pass` whenever the meeting is under the cap. On dev-18 that
makes **14 of 18 meetings a single 15–40 minute request**, and the remaining 4 produce chunks up to
2,400 s. Every one of those requests is physically impossible at `-np 4`. **Today's E3 emits a plan
in which 100 % of dev-18 requests would be refused by the server.**

Note also `client/transport.py` sets `timeout_seconds = 300.0`: even at `-np 1`, a 40-minute
single-pass request would need roughly 51 minutes of decode and would blow the client timeout by an
order of magnitude before the context question was reached.

## 8. Binding proposal

### 8.1 Transport slice — the unit of a core request

| parameter | value |
|---|---|
| **nominal length** | **90 s** (= 3 encoder chunks exactly, 1,170 audio tokens) |
| snap window | ±3 s to the nearest VAD speech/non-speech transition; if none, cut at the grid point |
| hard bounds after snapping | **[60 s, 120 s]** (2–4 encoder chunks; both grid-aligned) |
| overlap | **none. Zero.** Non-overlapping is the point |
| final slice of a chunk | may be short; no padding, no merging back past 120 s |
| audio format | 16 kHz mono PCM WAV, cut from the decoded meeting signal |
| boundary source | **signal only** (fixed grid + VAD snap). Never a model-declared boundary, never a gold annotation |
| determinism | slice plan computed once per meeting, before any arm runs, and frozen in a slice manifest with per-slice sha256 |

Why each of these:

- **90 s** — top of the measured throughput plateau (§5), minimum seam count within it, exact
  multiple of the 30 s encoder chunk, 20 % of the slot so the supply block has room to grow to
  SAEA's worst-case 5,835 tokens and still fit.
- **VAD snap, not model boundary** — the model-declared boundary is the mechanism SAEA measured as
  responsible for 1,648 s of audio advanced-past-untranscribed, and it makes slice bytes
  run-dependent, which both destroys feature-cache reuse and creates the measured non-determinism
  cascade (126 vs 124 slices across identical-config runs).
- **Frozen slice manifest, computed before any arm** — this is what makes the feature cache pay.
  The cache key is (audio content, chunk ordinal), so identical slice bytes hit across every arm.
  The P-SLU flight is the direct evidence: 6 arms over 60 audio files produced exactly 60 cache
  entries during phase 1, then **zero growth across 303 further requests**. For dev-18 that turns
  audio encoding into a **one-time ~32 minutes of GPU** for the whole split, rather than a cost
  re-paid by every arm.
- **No overlap** — overlap exists only to serve a dedup stitch, and the dedup stitch is where 86 %
  of SAEA's deletions were made.

### 8.2 Task chunk — the unit of state and dispatch

A task chunk is a **topic-aligned span, bounded to [180 s, 900 s], target ~360 s**, i.e. **2–10
transport slices, typically 4**. It is *never* a transport unit; no request ever carries a whole
task chunk's audio.

- **Boundaries**: pack consecutive transport slices until the chunk reaches the target, preferring
  to close at a boundary the control plane can justify. Split any topic longer than 900 s; merge any
  topic shorter than 180 s into its successor.
- **Boundary provenance must be declared and tiered**, because AMI's topic layer is *manual
  annotation of the evaluation material*:
  - `signal` — fixed packing of slices, no annotation. **This is the default and the only
    provenance admissible in a headline arm.**
  - `oracle-topic` — AMI/ICSI gold topic marks. Legitimate as a **declared oracle ceiling arm**,
    never as the default.
  - `shipped-materials` — MeetingBank agenda/bill index, i.e. materials genuinely shipped with the
    meeting. Admissible as a normal (non-oracle) provenance, and it is the provenance the
    speech-only / metadata-only / combined factorization already contemplates.
  This matters immediately: `chunking/adapters.py` currently feeds gold AMI topic-node start times
  straight into the runtime planner with no provenance tier attached.
- **Why this band**: it brackets the median-to-p90 natural unit of all three corpora (§6) while
  keeping state-consolidation intervals frequent enough that a bad glossary commit cannot poison
  40 minutes of transcript.
- **The 3 dev meetings with no topic layer** (IB4001, IB4002, IB4004) fall back to pure signal
  packing — which is the default anyway, so no special case is needed for the headline arm.

### 8.3 The stitching rule — SAEA's boundary-share window does NOT transfer

Explicit verdict, because the question was asked directly. SAEA's stitching machinery is:

```
limit = round(len(text) * advance / buffer_len)
accept through the LAST sentence-final character inside text[:limit]
```

That rule exists **only** because consecutive slices overlap and the model declares where to
advance. It is a repair for a design this proposal removes. Transplanting it would import the exact
mechanism that produced 86 % of SAEA's deletion mass.

**The meeting stitching rule is:**

1. **Concatenate in order.** Non-overlapping slices produce non-overlapping text; there is nothing
   to deduplicate and no boundary share to compute.
2. **Continuity is carried prompt-side, never audio-side**: the previous slice's accepted tail
   (~400 characters, SAEA's `obs_condition_tail_chars` value) is appended to the instruction as
   prior context. This is model output, never gold. It costs ~100 prompt tokens and **does not
   disturb the feature cache**, because the cache keys on audio content only — the P-SLU flight
   proves prompt text can vary across six arms over identical audio with full cache reuse.
3. **Order the payload evidence-text-first, audio-last**, preserving SAEA's prefix-stability
   convention.
4. **Keep the supply block constant within a task chunk** — re-render it only at chunk boundaries.
   This gives an identical prompt prefix across a chunk's slices. Treat any resulting prompt-cache
   benefit as a bonus, not a plan: SAEA measured **zero** prompt-cache hits under 4x4 saturation,
   and `cache_reuse` is force-disabled under mmproj.
5. **A word split across a cut is accepted as-is at both ends.** The VAD snap makes this rare; a
   dedup pass to "fix" it would reintroduce the deletion mechanism.

### 8.4 Serving configuration this proposal assumes

`-c 49152 -np 4` (12,288/slot) is sufficient with 5x headroom at 90 s and needs no change. Do not
raise `-np` beyond 4 without re-deriving this table: at `-np 8` the slot falls to 6,144 and the
usable audio ceiling halves. `-np 1` is only for deterministic paired reads, and at 90 s slices it
costs concurrency for no context benefit.

### 8.5 Campaign arithmetic at the proposed granularity

| quantity | dev-18, per arm |
|---|---|
| transport slices (calls) | **393** |
| prompt tokens | ~833,000 |
| wall, cold feature cache | **~1.58 h** |
| wall, warm feature cache | **~1.44 h** |
| one-time audio encode for the whole split | ~32 min GPU, paid once across all arms |

For ICSI (median 3,382 s, max 6,157.8 s) the same rule gives ~38 slices for a median meeting and
**~69 for the longest** — which immediately exceeds the current `max_calls = 50` per episode.

## 9. Implied E3 / E7b changes (list only — not implemented here)

**E3 — `chunking/`**

1. `chunking/planner.py:22` — `DEFAULT_WINDOW_CAP_S = 2400.0` is refuted; replace the single cap
   with the two-level parameters (`TASK_CHUNK_TARGET_S = 360`, `TASK_CHUNK_MIN_S = 180`,
   `TASK_CHUNK_MAX_S = 900`, `TRANSPORT_SLICE_S = 90`, `SLICE_MIN_S = 60`, `SLICE_MAX_S = 120`,
   `SLICE_SNAP_S = 3`).
2. `chunking/adapters.py:40` — the duplicated `window_cap_s = 2400.0` literal must go; adapters
   import the shared constants rather than re-declaring them.
3. `planner.py:87` — the `mode == "auto"` → `single_pass` branch must be **removed or hard-gated**.
   `single_pass` cannot remain a "first-class plan type" for meeting audio: it is impossible for
   every meeting in the frozen split. If it is retained at all, it must (a) be selectable only
   explicitly, (b) assert the computed context against the slot budget, and (c) refuse at plan time
   rather than at request time.
4. **New: a transport-slice layer under the chunk layer.** `build_chunk_plan` gains a slice plan per
   chunk: grid at 90 s, VAD snap, bounds [60,120], no overlap, deterministic, with per-slice
   `(start, end, sha256)` frozen into a slice manifest.
5. **New: a plan-time context assertion.** Every emitted slice must satisfy
   `13*seconds + reserve + completion_estimate <= 0.9 * slot_ctx`, with `slot_ctx` a declared
   config value (`n_ctx / n_parallel`), and fail closed at plan time.
6. `planner.py:111-128` — topic marks currently influence a cut only when the 2,400 s cap is
   crossed, so on dev-18 the topic layer is nearly inert (it can affect at most 4 meetings). Under
   the two-level design topic marks become the *task chunk* packing preference and are consulted on
   every chunk close.
7. **New: `BoundaryProvenance` tier on every boundary** (`signal` / `oracle-topic` /
   `shipped-materials`), machine-enforced, so an oracle-topic plan cannot be run in a headline arm.
   `BoundarySource.TOPIC_MARK` currently records *which* mark was used but not that it is gold.
8. Slice plans must be corpus-uniform: MeetingBank's 44.1 kHz stereo MP3 needs a declared
   decode → 16 kHz mono → cut path, identical to AMI/ICSI, before any slice hashes mean anything.

**E7b — `controller/`, `client/`, `harness/`**

9. `controller/loop.py:169,284` — `audio_chunk_resolver` is injected and **has no implementation**
   anywhere in `src/` (only test fakes). The real slicer must be built: decode once per meeting,
   cut per the frozen slice plan, write 16 kHz mono WAV, hash, and register. This is the single
   largest missing piece and it is a precondition for any G1 flight.
10. `client/transport.py:157-191` — `build_request_payload` base64-encodes **the entire audio
    file**. It must send the *slice* bytes. As written it would ship a whole 30-minute meeting on
    every request regardless of the chunk plan.
11. `client/transport.py:87-89` — `slots = 1` contradicts the `-np 4` batching that lock (b) asks to
    optimize; raise to match `-np` and keep `obs_batch_samples <= -np`. `timeout_seconds = 300.0` is
    ample for a 90 s slice (~59 s modelled latency, cold) — keep, and note it would be violated by
    any long-chunk design.
12. `controller/loop.py:207-216` — the budget pre-check charges `chunk.end - chunk.start`. With two
    levels it must charge **slice** seconds (the seconds actually sent), matching SAEA's rail where
    metering equals the slice actually transmitted.
13. `harness/episode.py:71-80` — `max_calls = 50` is too low once calls are slices: dev-18 needs up
    to 33 per episode (survivable) but ICSI needs ~69 for its longest meeting. Re-derive per corpus
    from the slice plan rather than hard-coding.
14. `harness/episode.py:199-204,218` — the task set builds one `TRANSCRIBE_SPAN` per *chunk*; it
    becomes one per *slice*, while `SUMMARIZE_SECTION` stays per task chunk and `RESOLVE_LEDGER`
    stays per episode. `max_iterations = len(chunks) + 2 + headroom` must be recomputed off the
    slice count.
15. `supply/config.py:34-36` — `max_glossary_terms`, `max_speaker_bindings` and
    `max_supply_tokens_estimate` are all `None` (uncapped). Now that a real per-request budget
    exists, set `max_supply_tokens_estimate` to a value the slice budget can absorb (≤ ~4,000 leaves
    margin at 90 s) and make it fail-closed. `supply/render.py:70`'s
    `_CHARS_PER_TOKEN_ESTIMATE = 4` is a rough proxy — acceptable for a cap, but the cap must be
    conservative because overflow is a hard server refusal, not truncation.
16. **New: a slice manifest artifact** (per meeting: slice index, start, end, sha256, VAD snap
    applied, encoder-chunk count) committed to the run receipt, so that a re-run provably re-sends
    identical bytes and the feature-cache reuse claim is auditable rather than assumed.
17. **New: featcache routing** per the SAEA convention — a fresh
    `/home/chao/feat-cache/<dataset>-<encoder>` directory per corpus campaign, never the legacy
    `q4km` directory. (Lock (b) item.)

## 10. What this analysis does not settle

- **Quality as a function of slice length is still unmeasured**, here and in SAEA. Every quality
  argument above is a *seam-count* argument (fewer seams is better, measured) plus the negative
  result at 10 s (+26.6 pp WER, measured). Nothing establishes that 90 s transcribes better than
  60 s or 120 s. The [60,120] bound exists so that a future arm can move inside it without
  re-deriving the budget.
- **The decode-vs-context exponent is fitted on three confounded points** (SAEA's own caveat: taken
  under different concurrency). The frontier's *shape* — a plateau with decline — is robust to that
  fit; the exact peak location within 30–90 s is not.
- **Instruction, supply and tail reserves are planning estimates**, not measurements. They are not
  load-bearing: at 13 tok/s the audio term dominates and a 2x error in the reserves moves the
  feasible ceiling by under 8 %.
- **VAD pause structure has not been measured on meeting audio.** SAEA measured it on earnings
  calls (a ≥1 s pause every 12–55 s in 9 of 10 files). Meetings should be easier (more silence, more
  turn boundaries) but AMI/ICSI carry **overlapped speech in a single mixed channel**, where pauses
  common to all speakers are rarer. If the ±3 s snap window turns out to miss frequently, the
  fallback is the unsnapped grid cut, which is what the [60,120] bound guarantees remains legal.
- **No model contact was made.** Every serving constant is inherited from SAEA receipts on the same
  build and the same model files; the first meeting-repo flight should re-measure the per-call floor
  and the 60/90 s wall on this corpus before the numbers in §5 are treated as this repo's own.

