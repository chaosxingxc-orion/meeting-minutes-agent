# C-CTX flight evidence

- Registration: `docs/readiness/2026-08-20-cctx-preregistration.md`
- Frozen manifest: `configs/probes/contextasr/2026-08-20-cctx-32-manifest.json`
- Manifest hash: `ecc8bfd2a4700a19324e89584480cfeb4177f0d904278e9474db80d88d98281c`
- Outcome: 160/160 requests succeeded; no retry; 7,176.2075 audio seconds.
- `responses.jsonl` is append-only raw model output plus request metadata.
- `receipt.json` binds model identities, request ledger, budgets, and the dirty source commit.
- The flight did not inspect or score response text. The separate frozen read is in
  `docs/checks/2026-08-20-cctx-read/`.
