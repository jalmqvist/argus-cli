# Argus CLI — Implementation Plan

**Status:** Updated 2026-11-25 · MPML-first MVP · local-first portfolio project

## 1. Purpose and scope

Argus is a **local, privacy-preserving, read-only RAG/agent assistant** that answers
"How do I run this research experiment?" with an evidence-grounded, validated launch
recipe. The user manually executes the proposed command; Argus never launches research
experiments. The application should showcase local LLM integration, retrieval engineering,
LangChain/LangGraph orchestration, structured output, tool constraints, evaluation, and
reproducibility—not just a chat interface.

**MVP target: MPML only.** MSML, BSVE and MRML are explicitly supported as future source
adapters; no need to import/parse their code or define their commands in the first MVP.
The first useful MPML workflow is recalling valid arguments and environment overrides,
including the less obvious differences between a baseline and DL request.

### MVP success criteria

- For a natural-language MPML launch question, return: repository, cwd, interpreter,
  entrypoint, ordered argv tokens, env overrides, explanation, source citations, source SHA,
  preflight findings, and an explicit verification status.
- No invented flags; every answer validated against `mpml.preflight` using real process env.
- Report warnings accurately, including strict DL booleans and artifacts; never promise that
  a clean preflight guarantees DL activation or successful experiment execution.
- Report retrieval hit@5, command validity, intent match, warning accuracy, abstention,
  repair count, latency, and the differences between the deterministic baseline and RAG agent.
- Public clone can run CI tests and toy adapter without private code, data or Ollama.
  A separate documented local demo with Ollama should be reproducible when Ollama/models
  are installed. CI does not need to download a multi-GB model.

### Non-goals (MVP)

- Experiment execution, trading orders, broker credentials, or mutating MPML state.
- Artifact loading or verified DL activation (MPML preflight is intentionally limited).
- Science/research strategy advice; dataset analysis; automated backtests.
- Full repository-independent arbitrary argparse introspection before supporting MPML.
- Web UI, hosted LLM APIs, multi-agent collaboration, cloud deployment.

## 2. Authoritative MPML integration boundary

The MPML launch-surface refactor is **complete and merged**:

| PR | Capability | Merge SHA |
|---|---|---|
| [#97](https://github.com/jalmqvist/market-phase-ml/pull/97) | Parser extraction and import-side-effect isolation | `de08b701cd2bec86715a8b84595fdef3170c5a4d` |
| [#98](https://github.com/jalmqvist/market-phase-ml/pull/98) | `python -m mpml.preflight` | `f0850084dd6075608b38d588628812347c2f4686` |
| [#99](https://github.com/jalmqvist/market-phase-ml/pull/99) | `python -m mpml.spec`, generated reference and tests | `14ad36e3f70a10bb5781b88200e825a717ca402f` |

Live source of truth, in priority order:

1. MPML's **own** `python -m mpml.spec` JSON (schema version 1) for arguments, registry,
   environment inventory, precedence and preflight issue-code descriptions.
2. MPML's **own** `python -m mpml.preflight <argv>` to validate using its interpreter,
   cwd and caller-supplied process environment (JSON issues; nonzero when errors).
3. MPML `docs/CLI_REFERENCE.md` and
   `docs/architecture/MPML_LAUNCH_SURFACE_REFACTOR.md` for explanatory retrieval.
4. The historical launch audit as context, not as a modern replacement for preflight.

**Do not rebuild modern MPML's argparse/environment AST parser or duplicate the 15
preflight rules in Argus.** This supersedes those components of the original plan.
AST-based CLI discovery is a later fallback for MSML/BSVE/MRML, where no equivalent
machine-readable spec exists yet.

The target interpreter is MPML's venv, not Argus's venv. Invoke spec/preflight with a
fixed list of allowed module names, `subprocess.run([...], shell=False)`, timeout and
captured output. The process cwd is the MPML repo root. Set candidate environment
variables on that subprocess; don't inject a fake env object into MPML. Do not call
`main.py`, load prediction data or mutate caches.

Record MPML `git rev-parse HEAD`, dirty state, generated spec hash and config/model info.
Treat stale indexed knowledge explicitly; never silently claim the index covers another
revision. Pin the MPML integration profile to schema version 1 and fail with a useful
message for unknown versions. A dirty MPML worktree is provenance metadata, not by itself
an error; a dirty source invalidates claims that HEAD alone describes local content.

### Verified scientific compatibility (scope-limited)

The post-refactor `gen1_A` baseline CSV
`walkforward_results_per_fold__baseline.csv` was byte-identical to the earlier baseline
between `de08b701cd2bec86715a8b84595fdef3170c5a4d` and
`14ad36e3f70a10bb5781b88200e825a717ca402f`. The `experiment_manifest.json`
changed only in git_sha, run_id and timestamp_utc. This validates that selected baseline
cell, not every DL/strategy combination or artifact compatibility.

## 3. Product architecture

```text
sources.yaml -> source adapter -> MPML spec + docs -> normalized evidence -> local index
                                                            |               |
user question -> retrieval (BM25 + vector) -> Ollama structured recipe             |
                                              -> safety/shape validation           |
                                              -> MPML preflight (same cwd/env)      |
                                              -> bounded repair or abstain          |
                                              -> answer + citations + provenance <-+
```

#### Data / evidence tiers

- **Tier 1 structured:** MPML spec JSON; prioritize exact argument and env facts.
- **Tier 2 text:** generated CLI reference, roadmap, audited technical docs; split by
  heading, include file paths and Git SHA, reserve short excerpts as citations.
- **Tier 3 local validation:** preflight, invoked *after* structured candidate generation.
- **Local-only evidence:** optional experiment recipes/logs used to build private evals,
  never automatically uploaded or committed.

#### Structured recipe contract (planned)

`repo`, `script`, `cwd`, `argv: list[str]`, `env: dict[str,str]`, `explanation`,
`citations: list[evidence_id]`, `requested_intent`, `unknowns`, `verification`.
Do **not** let the model fabricate a shell command. Render an escaped, copyable command
only after validation. Keep argv token order and env value strings. Resolve citations
against retrieved evidence IDs; unknown or nonexistent IDs are rejected.

#### Validation states (planned)

- `validated`: structured candidate + preflight success without errors, but not a run.
- `validated_with_warnings`: preflight success with warnings; explain impact on intent.
- `rejected`: parse or project validation error; bounded repair may retry.
- `unverified`: stale source/index, incompatible schema, unavailable MPML or uncertain
  artifact behavior.
- `abstained`: insufficient evidence for a trustworthy command.

Preflight can be clean when artifact loading later fails. Distinguish *launch-surface*
validation from *intent satisfaction* and *experiment success*. A request to **enable DL**
must not be presented as fulfilled merely because `DL_SIGNALS_ENABLED=true` parses.

### Technology choice

- Python 3.12, `pytest`, Ruff, GitHub Actions; `pyproject.toml` packaging and `argus` CLI.
- Ollama local-only. Start with a 7–8B available model; make model name configurable.
  Verify availability and structured-output quality before choosing a production default.
- `langchain-ollama`/LangChain for model and embedding integrations; LangGraph for a
  visible finite-state retrieve/generate/validate/repair/abstain workflow.
- Hybrid retrieval: lexical BM25 plus embedding cosine similarity, with exact tokens
  (strategy IDs, flags and env keys) weighted carefully. Begin with local JSON files
  as an index/build artifact; choose Chroma/FAISS only if evaluation justifies it.
- Pydantic schema validation and deterministic rendering. Avoid gratuitous abstractions.
- Pin exact resolved dependencies in a lock file after the first functioning installation.

## 4. Milestones and exit criteria (portfolio-first, vertical slices)

| Milestone | Deliverable | Exit test / evidence |
|---|---|---|
| **M0 Foundation** | GitHub repo, packaging, CLI, YAML config, restricted MPML bridge, docs, CI, ADRs | `pytest`/Ruff green on synthetic tests; `argus doctor/spec/preflight` locally |
| **M1 Working MPML lookup** | Inspect MPML spec and answer deterministic flag/env/precedence questions, formatted command templates, source SHA | 10 curated launch questions answer without Ollama; no unknown flags |
| **M2 Evidence ingestion / retrieval** | Spec chunks + Markdown heading chunks, commit-aware index, BM25, embeddings via Ollama, hybrid retrieval; provenance | Retrieval hit@5 recorded on held-out questions; stale index detected |
| **M3 Local LLM structured output** | LangChain-Ollama/Pydantic candidate generation, command renderer, citations | Baselines (no RAG/docs-only/hybrid); 20 MPML questions scored |
| **M4 LangGraph validated agent** | retrieve → generate → preflight → repair ≤ 2 → answer or abstain; warning/intent handling | Golden eval with correct warnings and abstentions; no experiment execution |
| **M5 Portfolio release** | Clear README, demo, diagrams, model and ablation comparisons, reproducibility metadata, limitations | Fresh-clone toy demo; CI runs tests; local Ollama eval report committed with sanitized data |
| **Later** | MSML, BSVE, MRML source adapters; optional experimental results retrieval | Separate ADR + integration test per source repo |

Milestones produce independently reviewable PRs. **Avoid building every adapter,
vector DB, tool registry and agent framework before the first MPML use case works.**
Do not require an LLM for M0/M1 CI tests.

## 5. Public vs local data and deployment

**Commit:** public toy fixtures, sanitized golden prompts, schema definitions, ADRs,
unit tests, mock preflight responses, architectural diagrams, and generated eval tables
whose inputs are public/sanitized.

**Never commit:** private source clones, `.env`, model weights, vector stores, local
absolute paths, broker credentials, actual experiments or logs, market/sentiment data.
The source code under `market-phase-ml` stays in its own repo; Argus references it via
`MPML_REPO` / `MPML_PYTHON` and reads only selected documented paths.

The first release is a local Python CLI, not a web service. The LLM does not receive
unrestricted tool access; only Argus code may invoke fixed, reviewed, read-only
modules. Environment overrides are data and must not be interpolated into shell
commands. Cite retrieved evidence with repo/path/heading/revision.

## 6. Evaluation and run evidence

Keep the original evaluation metrics, but separate **syntactic validity**, **preflight
status**, **intent fulfillment**, and **scientific run outcome**. A zero-issue preflight
is never proof the full experiment completed or DL actually activated.

Metrics: retrieval hit@5, parse validity, rule validity, warning accuracy, normalized
command exact/semantic match, abstention precision/recall, mean repair attempts,
model output/schema failure rate, hallucinated flag count, p50/p95 latency. Track
cost proxies such as generated tokens; no cloud API charges.

Ablations: deterministic spec-only; model without retrieval; docs-only; spec+docs;
BM25-only; vector-only; hybrid; hybrid+preflight; hybrid+repair. Compare two local
small models as time permits; one larger model is an optional quality ceiling.

Start with **20 public/sanitized MPML golden questions**, including at least one per
preflight diagnostic family, multi-flag requests, malformed/contradictory intent,
unknown strategy, repeated PhaseAware, strict DL boolean, artifact-alias precedence,
generation/variant mismatch, output-name hints, empty default baseline, and abstentions.
Hold out roughly 30% before prompt tuning. Record the dataset version, source SHA,
Ollama/model details, retrieval config and run seed. The historical
`mpml_run_examples.tgz` is optional *local context*, not a CI dependency or oracle.

Older local run evidence may help author questions, but do not treat historical run
artifacts as verified exact answers for a new MPML revision. A pending LSTM
consensus-mature MR32 USDJPY-only recipe remains **unverified** until a matching real
run confirms its artifact/state, DL activation and completed evaluations.

## 7. High-risk failure modes

- Stale source indexes, dirty repo and model hallucination: display provenance, prefer
  deterministic spec and preflight, abstain when evidence is insufficient.
- Real env differences between preflight and copied command: capture an ordered env
  override map, preserve MPML cwd, display effective invocation and warnings.
- MPML preflight does not load artifacts; do not promise DL activation.
- Large documentation / 7B context windows: chunk by headings and keep top-k limited.
- Prompt injection embedded in source documents: treat retrieved text as **data**, never
  executable instructions or authority to run arbitrary scripts.
- Private-data leak: local-only inference; no source embedding uploads to hosted APIs.
- Scope creep: MSML/BSVE/MRML and experiment-result analytics are future milestones.

## 8. Acceptance / definition of done for MPML MVP

- Local `argus ask 'How do I run MR32 baseline?'` produces a structured, cited recipe
  and validated preflight status, or honest abstention.
- Documentation includes a real demo transcript, architecture diagram, tests, and
  an evaluation report with numbers obtained from actual runs (never fabricated).
- An unfamiliar reviewer can clone, install, run synthetic CI tests and understand
  how to reproduce local Ollama results without access to private MPML data.
- All tool invocations remain read-only and allowlisted; no experiment execution.
- Known limitations and next-source adapter interfaces documented.

## 9. Sequenced Codex implementation prompts

See `docs/prompts/` for prompts M0 through M5. Ask Codex for one reviewable PR per
milestone, using green tests and observable exits rather than long procedural rules.
