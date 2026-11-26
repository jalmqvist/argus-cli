# M4v2-2C3 local proposal workflow

`argus ask --agent-v2` keeps the deterministic explanatory path. Relevant manual
launch and mixed requests can make one untrusted proposal even when the bounded
intent extractor leaves gaps. Unsupported execution, broker actions and
detected instruction overrides stop before inference. Requests that lack enough
MPML context may still ask for clarification. Routing is deliberately bounded.

The proposal path uses verified lexical retrieval of up to eight excerpts,
including structured spec and matching documentation. It uses the configured
local model, temperature, seed and stream timeout, with the existing 8,192-token
context and 1,100-token generation cap. The default model is
`qwen2.5-coder:7b`, with temperature 0 and stream timeout 180 seconds.
Model identity metadata and preflight have their own existing timeouts.
No embedding model, repair loop, secondary verifier or additional generation
attempt is required. `--retrieval-mode` still applies to the existing M3 and
M4 v1 modes. The v2 proposal path is lexical.

Prompt evidence IDs map back to exact pinned index records. The C1 adapter
independently verifies that snapshot and checks candidate structure, setting
support, exact recognized constraints and authoritative MPML preflight. It uses
the same captured environment and rechecks source, index and environment before
returning. C2A supplies selector names and winning sources without publishing
their values. Proposal routing can permit a read-only probe with unresolved
intent. It supplies no release authorization.

The response uses the existing v2 fields with an additive `workflow` object.
The object records route, deterministic answer success, generation attempt,
stream-call count, proposal outcome, validation findings, preflight, blockers,
digest and timings. Model metadata checks do not count as generation calls.
A metadata failure can therefore record an attempted generation stage and zero
stream calls. The answer uses fixed templates and trusted observations.
It excludes raw model prose, private candidate settings, inherited values and
raw diagnostic messages. Published issue codes and severities are retained
where available. Exit 0 still denotes a grounded deterministic answer, 1 covers
withheld recipes or qualified guidance, and 2 indicates unavailable verification.
Every proposal leaves `command` and `settings` null.

## Offline development cases

[The C3 fixture](workflow-development-v1.json) is developer-authored smoke
coverage for routing. Mocked tests additionally exercise drift, bad proposals,
timeout, citation failures, prompt injection, abstention and preflight privacy.
These tests do not measure independent holdout performance or real-model quality.

## Maintainer-local smoke test on the GTX 1070 (8 GB)

Use the existing configured clean MPML checkout, up-to-date lexical index and
local Ollama instance with `qwen2.5-coder:7b` already installed. From the repo root:

```sh
argus ask 'What is the default for EXPERIMENT_SEED?' --agent-v2
argus ask 'Use strategy MR32 with seed 57.' --agent-v2 --model qwen2.5-coder:7b --timeout 180
```

Use a strategy from the pinned registry if MR32 is absent. The first command
should report a grounded answer and zero model calls. For the second, record
`workflow.model_digest`, `model_calls`, `generation_seconds`,
`elapsed_seconds`, `candidate_outcome`, `preflight_outcome` and `blockers`.
Exit 1 is expected if a recipe is withheld. The response should keep its
command and settings null regardless of preflight acceptance. No experiment
or artifact loading is part of the smoke test. Real Ollama and MPML were not
used to validate C3 in CI.

M4v2-3 should measure first-attempt usefulness, false withholding and latency on
the target hardware. Independent complete-intent and effective-configuration
verification remain prerequisites for validated recipe release.
