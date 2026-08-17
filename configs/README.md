# configs

Plain-JSON run configs for this repository's engineering and analysis
entry points. No YAML dependency is introduced (lean by design; stdlib
`json` is sufficient at this stage).

`example.json` is a minimal config shape accepted by
`meeting_minutes_agent.runreceipt.write_run_receipt` — see that module's
docstring for the run-receipt fields it produces (run id, config hash, git
commit, timestamps).
