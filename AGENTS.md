# Repository Guidelines

## Project Structure & Module Organization

Production code lives in `src/meeting_minutes_agent/`: corpus loading (`corpora/`), chunking (`chunking/`), episode supply (`state/`, `glossary/`, `supply/`), model I/O (`heads/`, `client/`), orchestration (`controller/`, `harness/`), and evaluation (`metrics/`, `probes/`). Mirror packages under `tests/unit/`; use `tests/integration/` for real corpus checks. Utilities belong in `scripts/`, frozen inputs in `configs/`, plans in `docs/plans/` or `docs/readiness/`, evidence in `docs/checks/`, and research navigation in `docs/wiki/`. Before experiments, read the Wiki registry and linked plan. Register before model contact and update the Wiki after the one-shot read.

## Build, Test, and Development Commands

Use Python 3.12+ on Linux/WSL2:

```bash
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"
pytest                         # run the complete offline suite
pytest tests/unit/chunking     # run one subsystem
pytest tests/unit/test_runreceipt.py -k hash
python scripts/data/verify.py --dataset qmsum
```

The default suite must not contact models or require datasets. See `scripts/data/README.md` before preparing corpora; corpus bytes belong outside the checkout under `SPEECHRL_DATA_DIR`.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules/functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Type public interfaces and keep heavy audio imports lazy. Configuration uses JSON; YAML requires a design decision. Markdown, comments, and commit messages are English-only, except Chinese reporting pages under `docs/wiki/` and explicitly designated plans. Preserve LF line endings.

## Testing Guidelines

Use `pytest`. Name files `test_<subject>.py` and tests `test_<behavior>`. Add unit tests beside the mirrored subsystem and reusable fixtures in its `fixtures.py` or `conftest.py`. Cover deterministic outputs, boundary conditions, hashes/receipts, and leakage guards. Model-contact experiments require a pre-registration, pinned inputs and budgets, and a prebuilt read suite; do not treat them as ordinary integration tests.

## Commit & Pull Request Guidelines

History favors concise, imperative, scoped subjects such as `feat(precomp): ...`, `fix(diar-smoke-scoring): ...`, and `third_party: ...`. Keep each commit limited to one coherent research or engineering change. Pull requests should explain the research motivation, affected pipeline stages, commands run, and configuration or data-lock changes. Link the relevant plan/readiness record and issue. Include receipts or metric summaries for experiment changes, but never commit audio, datasets, weights, credentials, or unreviewed generated artifacts.

## Reproducibility & Security

Keep the model core frozen and training-free. Pin model, tool, dataset, and split identities and record design rulings in `docs/decisions.md`. Never place gold labels or reference transcripts in runtime prompts, and do not persist speaker or glossary state across meetings without an explicit owner decision.
