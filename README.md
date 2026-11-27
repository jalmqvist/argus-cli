# Argus CLI

Argus is a local, read-only research assistant for developers working with
[MPML](docs/releases/V0_1_0_RC1_SCOPE.md). The `v0.1.0rc1` developer preview
inspects the published MPML specification, retrieves cited local evidence,
runs explicit read-only preflight, and offers qualified configuration guidance
through `argus ask --agent-v2`.

## Quickstart

Use Python 3.12, Git, and a local MPML checkout whose own interpreter can run
`mpml.spec` and `mpml.preflight`. MPML is configured separately from the Argus
package. Run the examples from the Argus checkout so `sources.yaml` and the
local index share a working directory.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install '.[llm]'
argus --version

export MPML_REPO=/absolute/path/to/market-phase-ml
export MPML_PYTHON=/absolute/path/to/market-phase-ml/.venv/bin/python

argus doctor
argus inspect EXPERIMENT_VARIANT
argus explain precedence
argus index
argus retrieve 'What takes precedence over EXPERIMENT_VARIANT?'
argus ask --agent-v2 'What is the default for EXPERIMENT_SEED?'
argus preflight -- --strategy MR32 --experiment-seed 57
```

`pip install .` provides the deterministic core commands. The `llm` extra also
installs the v2 interface, including its deterministic answer path. That path
does not call a model. MPML credentials and market datasets are unnecessary
for this inspection and preflight workflow. Use `argus --config /path/to/sources.yaml`
before the subcommand to use a different source file.

For one local configuration assessment, start Ollama on its default loopback
port and install the existing Qwen model if needed:

```sh
ollama pull qwen2.5-coder:7b
argus ask --agent-v2 'Use strategy MR32 with seed 57.'
```

V2 uses lexical retrieval and at most one model call. Its standard workflow
requires neither an embedding model nor LangGraph. Choose a strategy published
by your MPML revision if it does not include `MR32`.

## Read the results

| Finding | What it establishes |
| --- | --- |
| Cited deterministic explanation | A documented setting or precedence rule in the verified MPML snapshot. |
| Preflight acceptance | MPML accepted the candidate launch surface. Execution, DL activation and artifact loading remain unverified. |
| Candidate correctness | The proposed settings match the request where separately checked. Accepted preflight alone cannot establish this. |
| Complete intent and release authorization | Requires independent verification of the entire request and effective configuration. V2 in this preview withholds manual commands and full candidate settings. |

V2 returns `argus-response-v2.0` JSON with `answer_status`, `recipe_status`,
`intent_coverage`, `material_constraints_status`, and `workflow` diagnostics.
Public `command` and `settings` are null. Exit code **0** denotes a grounded
deterministic answer, **1** covers qualified guidance, a withheld request or
needed clarification, and **2** indicates unavailable verification or a CLI
error. A qualified assessment can be useful even when it exits 1. Explicit
`argus preflight` reports MPML diagnostics and uses MPML’s exit status.

Inspection reports parser defaults and published precedence separately. The
lexical index lives at `indexes/mpml.json` relative to the working directory
and contains selected source text. Keep it local. If source revision, spec or
reference text changes, run `argus index` again from that directory. V2 requires
a clean MPML checkout and a current verified index.

## Preview boundaries and legacy workflows

Environment-only requests can still lead to wrong proposed channels, and
`ACTIVE_PAIRS` requests can omit the pair filter. Argus performs no experiment
execution or broker operations. Support is scoped to MPML schema version 1.

**Plain `argus ask` still runs M3.** The `--agent` option selects historical
M4 v1. These experimental modes may produce manual commands under different
checks. `--agent` and `--agent-v2` are mutually exclusive.
See [legacy usage, architecture and evaluation](docs/architecture/LEGACY_WORKFLOWS.md).

## Release and development

- [Release scope](docs/releases/V0_1_0_RC1_SCOPE.md)
- [Acceptance checklist and exact smoke commands](docs/releases/V0_1_0_RC1_ACCEPTANCE.md)
- [Draft release notes](docs/releases/V0_1_0_RC1_NOTES.md)
- [Roadmap](PLAN.md) and [v2 development evaluation](eval/m4v2/README.md)
