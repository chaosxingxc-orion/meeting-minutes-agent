# PRECOMP — pinned-diar + featcache production pass — REGISTERED

Date: 2026-08-19. Status: **REGISTERED — wave-1 flyable once the machinery lands**; owner
mode ruling 2026-08-18 ("大规模并行 diar + featcache 之后再进行持续的实验") and the
TOOL-LOCKED(B) adjudication (`2026-08-19-diar-adjudication-TOOL-LOCKED-B.md`) are the
authorities. This is a PRODUCTION pass, not a probe: it computes reusable derived assets so
every later experiment is decode-only. One registration covers both waves.

## 1. Cache dependency chain (what this pass freezes)

pinned diar (TOOL-LOCKED(B) binding) → speaker turns (RTTM) → two-level plans (task chunks
180–900 s; transport slices 90 s [60,120] turn-aware, slicer at ≥ `5a762cb` with the
room-cap fix) → slice bytes (librosa decoder, ffmpeg absent by design) → featcache entries.
Invalidation axes (any change cold-starts downstream): diar pin, slicer constants/algorithm,
audio set, GGUF/encoder identity. All four are hash-pinned.

## 2. Waves and scope

- **Wave-1 (now): the dev-18 meetings** (covers any G1 seed choice; four already have
  P-ATTR-era oracle slices). Per meeting, BOTH turn sources: tool turns (Arm B streaming)
  AND oracle NXT turns (G1's ceiling arm needs both slice sets).
- **Wave-2 (night batch, resumable chunks): the remaining usable-discovery meetings**
  (~83). Same construction. Interruptible filler whenever the GPU would otherwise idle;
  never blocks a registered flight (ready-first rule).
- eval-16 and reserved-final-reporting meetings are NOT precomputed (untouchable until
  their governed use).

## 3. Steps per meeting

1. Diar via the pinned Arm B (per-contact log: tool id, checkpoint hash, args, wall, rc).
2. Slice plans for tool turns and oracle turns; plan manifests hashed.
3. CPU slice cutting (parallel workers per the owner baseline: ~20 idle / cap 8 during GPU
   campaigns); slice bytes hashed into a manifest.
4. Featcache warm pass: encode-only frozen-core contact per slice (minimal generation cap,
   outputs NEVER read — the contact exists solely to populate the feature cache), llama.cpp
   featcache build pinned as in all prior flights.

## 4. Ceilings

Wave-1: ≤0.5 GPU-h diar + ≤2.0 GPU-h encode-warm + ≤2 h wall CPU cutting; ≤900 encode
calls. Wave-2: ≤2.0 GPU-h diar + ≤8.0 GPU-h encode-warm (night window), resumable at
meeting granularity; ≤4,500 encode calls. Budgets enforced by the runner; per-wave receipts.

## 5. Metrics (descriptive only — this pass renders no verdicts)

Per meeting: turn counts, slice counts (tool vs oracle, count delta), boundary-displacement
distribution (descriptive; the positional packing-change fraction is RETIRED as saturated
per the smoke read), cache entries added/bytes, encode wall, diar wall. Receipts under
`docs/checks/2026-08-19-precomp-wave{1,2}/`; all derived bytes on the data root, manifests
only in Git.

## 6. Discipline

Machinery built (Sonnet) and coordinator-reviewed before wave-1 runs; encode-warm outputs
are never read (fail-closed: the runner discards generation text unread, receipts carry
counts only); per-contact logging throughout; AMI CC BY 4.0; no gold anywhere in any
prompt path (oracle turns supply boundaries/labels to the SLICER only, scoring-side
conventions unchanged).
