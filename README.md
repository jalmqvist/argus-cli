# argus-cli

Local, privacy-preserving, **read-only** research CLI assistant. An MPML-first portfolio
project demonstrating deterministic tool integration, local LLMs, structured generation,
RAG, validation and measured agent reliability.

**Current state:** deterministic MPML lookup and preflight. Argus reads the
published MPML spec from your checkout and can check a default launch candidate.

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

## Look up MPML settings

```bash
argus inspect --strategy
argus inspect EXPERIMENT_VARIANT
argus explain precedence
argus explain experiment_variant
argus explain warnings
argus explain strategies
argus recipe defaults
```

`inspect` matches exact flag spellings and environment variable names. It prints the
published parameter record, including its default, any structured choices or post-parse
choices, and matching precedence entries. Environment choices and alias behavior may
appear in the published semantics text. The flag default is the parser default. Consult
precedence and environment semantics for runtime fallbacks.

`explain` also accepts an exact flag, environment variable, precedence setting, or preflight
issue code. The `warnings` topic lists the published diagnostic summaries, including
potential errors. Actual findings come from preflight. Lookup reports include the MPML
checkout SHA, dirty state, interpreter, schema version, and canonical spec SHA-256.

`recipe defaults` proposes an empty argument list with no environment overrides and
runs MPML preflight using the inherited process environment. The JSON includes the working
directory, interpreter, entrypoint, arguments, overrides, findings, and verification
status. `validated` and `validated_with_warnings` describe the preflight result.
`rejected` and `unverified` return a nonzero status. For a custom candidate, use
`argus preflight --env KEY=VALUE -- <MPML args>`.

## Key repo files

- `PLAN.md`: updated implementation roadmap and evaluation strategy
- `sources.yaml`: source repo bridge configuration (environment-variable expansion)
- `docs/adr/`: architectural decisions
- `docs/prompts/`: Codex implementation prompts
- `src/argus_cli/adapters/mpml.py`: constrained MPML spec/preflight subprocess bridge
- `tests/`: synthetic/mock tests, independent of private repos

## Limitations

- Lookup reports documented settings. It does not resolve the effective value for your
  current environment or infer choices and precedence the spec leaves implicit.
- The only recipe is `defaults`. Inherited settings may affect the candidate, including
  whether it requests DL. Preflight checks the launch surface. Artifact loading,
  DL activation, and experiment success require a separate run.
- Lookup uses the live spec. A dirty checkout means its Git SHA alone cannot identify
  the inspected content.
- The adapter is scoped to MPML's `schema_version: 1`; schema changes require explicit
  review and version handling.
