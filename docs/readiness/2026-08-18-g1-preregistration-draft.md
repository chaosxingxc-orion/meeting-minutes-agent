# G1 preregistration DRAFT — zero-supply baselines (AMI dev-18 + MeetingQA floor)

Date: 2026-08-18 (night). Status: **DRAFT — not registered, not flyable.** Owner review +
binding pass required. This is the meeting topic's first flight; it establishes every floor the
later glossary/supply arms are measured against.

## 1. Purpose

Measure the frozen core's zero-supply floors on the meeting stack: (a) chunked transcription +
speaker attribution on AMI dev-18 (9.667 h, the frozen ASR-partition dev set, per-meeting IDs
in the 2026-08-17 split freeze), (b) zero-shot minutes generation (four sections + evidence
claims), (c) the MeetingQA zero-shot floor (retiring the 57.3-vs-84.6 headroom language, per
the deep-check ruling: 57.3 is a fine-tuned DeBERTa, not an LLM floor).

## 2. Arms (all zero-supply; the registered controls from the deep check)

| Arm | Shape |
|---|---|
| Z-chunked | topic-aligned chunk plan (E3), oracle-diar speaker spans, transcribe+attribute head per chunk, minutes head at end |
| Z-single-pass | meetings ≤ core window flown as ONE instance (E3 single-pass plan) — the chunking-cost control: chunking cost = (single-pass − chunked) is a named line item |
| Z-no-diar | chunked, no speaker spans supplied — the attribution ablation floor |
| Z-qa | MeetingQA dev questions over the meeting audio (qa head unstubbed first — precondition), abstention scored against empty string |

Timing rule (BINDING, from the E7b review): time-constrained metrics (tcpWER/tcORC) take
segment timing from the **oracle-diar layer** (AMI gold turn times), never from the transcribe
head's synthetic even-split timestamps — the E5 anti-gaming validator refuses synthetic timing
by design. Arms without diar timing report only non-time-constrained metrics.

## 3. Metrics (E5 pins)

Primary attribution cost: tcpWER − tcORC-WER @ collar 5 s (identical streams, MetricPins
hashed). Secondary: cpWER − ORC-WER (literature row). Minutes: SAER-M (pre-registered draft
definition; per-statement attribution over evidence-linked sentences) + section-completeness
counts; ROUGE legacy row only. QA: macro token-F1 + IoU with empty-string abstention;
abstention and multi-span sub-metrics reported separately; comparability check against the
MeetingQA paper's own scoring script REQUIRED before any cross-paper comparison. Consumption
instrumentation on every arm (copy-rate, per the E1 instrument) even though supply is zero —
it establishes the instrument's floor noise.

## 4. Power discipline (deep-check §3.6)

After G1: per-meeting bootstrap CIs + per-metric MDEs from zero-arm variance; paired
per-meeting design for all later arms; deltas below MDE reported as null. KILL: AMI-dev MDE >
2 cpWER points retires AMI as a gain substrate (NOTSOFAR-1 then inherits, post-census).

## 5. Bindings required before registration

n = 18 meetings (frozen dev list) + [TBD] MeetingQA dev question count; GPU estimate from a
[TBD] 1-meeting timing smoke (9.7 h audio, chunked ≈ 15–17 chunks + single-pass re-fly of
≤40-min meetings — expect the largest flight so far, 8–15 GPU-h projected); budgets and
exposure-equivalent receipts per this repo's lean receipt discipline (FlightReceipt + ledger
note in docs/); AMI role registry (one role per meeting: glossary-discovery / ASR-eval /
QA-eval, machine-checked fail-closed) committed BEFORE flight — the MeetingQA 80:10:10 overlap
matrix from the deep check is its input.

## 6. Preconditions

E-track complete (E1–E7b ✅, suite 508/2); qa head unstub + MeetingQA loader (small ticket);
role registry (small ticket); 1-meeting timing smoke (first core contact of this repo —
receipt + owner-visible note); oracle-diar span extraction from the NXT layer (E2 provides
turns — a thin adapter).
