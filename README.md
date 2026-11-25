# argus-cli

Local, privacy-preserving, **read-only** research CLI assistant. An MPML-first portfolio
project demonstrating deterministic tool integration, local LLMs, structured generation,
RAG, validation and measured agent reliability.

**Current state:** foundation only. This scaffold supports `doctor`, `spec`, and `preflight`
against your own MPML checkout. It does not yet include RAG, Ollama calls, agent loops,
or natural-language command generation. Those are explicitly staged in `PLAN.md`.

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export MPML_REPO=/absolute/path/to/market-phase-ml
export MPML_PYTHON=/absolute/path/to/market-phase-ml/.venv/bin/python
argus doctor
argus spec
argus preflight -- --strategy MR32 --behavioral-surface trend_vol
argus preflight --env DL_SIGNALS_ENABLED=1 -- --strategy MR32
python -m pytest -q
```

MPML is not a pip dependency: the bridge uses MPML's own interpreter and the repo root
as the subprocess working directory. No experiment commands are executed.

## Key repo files

- `PLAN.md`: updated implementation roadmap and evaluation strategy
- `sources.yaml`: source repo bridge configuration (environment-variable expansion)
- `docs/adr/`: architectural decisions
- `docs/prompts/`: Codex implementation prompts
- `src/argus_cli/adapters/mpml.py`: constrained MPML spec/preflight subprocess bridge
- `tests/`: synthetic/mock tests, independent of private repos

## Limitations

- No live model/retrieval layer yet.
- Preflight is not a guarantee of DL artifact availability or successful execution.
- The adapter is scoped to MPML's `schema_version: 1`; schema changes require explicit
  review and version handling.
