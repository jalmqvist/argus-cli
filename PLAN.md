# Argus CLI — Implementation Plan and Research Roadmap

**Status:** Updated 2026-11-26 · MPML-first, local-first, read-only · M0–M4C complete · M4v2-0 through M4v2-2B complete · next: M4v2-2C1

## 1. Purpose, scope and success criteria

Argus is a **local, privacy-preserving, read-only research assistant** for understanding how to configure and manually launch experiments in MPML. It combines authoritative MPML configuration interfaces, retrieval, optional local LLM generation, structured validation and reproducible evaluation. It **does not execute experiments or trading orders**. MSML, BSVE and MRML remain possible future source adapters, not current MVP dependencies.

The product now has two distinct potential outputs:

1. **Grounded explanation:** a factual account of documented MPML settings, scope, defaults, precedence, diagnostic meanings or limitations, with verified provenance and citations. No runnable command is released.
2. **Verified manual launch recipe:** exact ordered argv and environment overrides, released only after independent evidence, structural, full material-intent, effective-configuration, provenance and authoritative MPML preflight gates succeed. A passing preflight **alone does not establish intent correctness**, execution, DL activation or artifact loading.

**Near-term success** is not simply more answered questions. It is greater completion of genuinely supported tasks without incorrect command release, while preserving honest withholding when evidence or intent remains unresolved. Separate explanatory-answer completion from recipe correctness and report false withholding, incorrect commands, uncertainty, calls and latency.

### Invariant boundaries

- Argus may invoke only narrowly allowed, read-only MPML metadata and preflight interfaces. Never call MPML `main.py`, open broker positions, run experiments or load prediction artifacts.
- Ollama model output, retrieved text and questions are untrusted data; none can confer authorization or bypass validation.
- Commands are **for manual execution only**, escaped by a trusted renderer after all release checks; proposed unapproved settings belong in private traces, not user-facing ready-to-run recipes.
- No real market/sentiment datasets, broker credentials, local source clones or private review-mapping keys in public CI or repository artifacts.
- An MPML spec or index change requires fresh verified provenance. Dirty checkout behavior varies by workflow: v2 grounded answers and candidate authorization currently require clean provenance; historical M3/M4 v1 reporting remains unchanged.

## 2. Authoritative MPML integration

The MPML launch-surface refactor is complete:

| MPML PR | Interface / capability | Reference |
| --- | --- | --- |
| [#97](https://github.com/jalmqvist/market-phase-ml/pull/97) | CLI parser isolation and import-side-effect characterization | `de08b701cd2bec86715a8b84595fdef3170c5a4d` |
| [#98](https://github.com/jalmqvist/market-phase-ml/pull/98) | Versioned JSON preflight and environment handling | `f0850084dd6075608b38d588628812347c2f4686` |
| [#99](https://github.com/jalmqvist/market-phase-ml/pull/99) | `mpml.spec` and generated CLI reference | `14ad36e3f70a10bb5781b88200e825a717ca402f` |

Evidence priority: **MPML's live `python -m mpml.spec`** for the authoritative launch inventory; **`python -m mpml.preflight`** for the exact proposed configuration and inherited environment; the generated `docs/CLI_REFERENCE.md` and architecture documentation for explanation; historical audits only as context. Do not duplicate MPML's parser or its preflight rules in Argus.

Use the MPML interpreter, repository cwd, bounded subprocess calls with `shell=False`, exact candidate argv and explicit environment overrides. Capture revision, dirty state, spec/index hashes and provenance. The pinned scientific baseline `gen1_A` walk-forward CSV parity across the MPML refactor applies to that selected configuration only, not to all strategies or DL variants.

## 3. Implemented workflows and current architecture

| Workflow | Current behavior | Main limitation |
| --- | --- | --- |
| `argus inspect`, `argus explain`, `argus recipe defaults` | Deterministic MPML specification lookup and defaults preflight | Exact-topic and spec scope; no experiment outcomes |
| `argus retrieve` | Provenance-aware BM25+, embeddings and hybrid retrieval | Retrieval relevance is not semantic correctness |
| `argus ask` (M3) | Local single-pass structured recipe proposal, citation/structure checks, preflight and manual renderer | Can produce misleading proposals or incorrect intent despite clean preflight |
| `argus ask --agent` (M4 v1) | Opt-in bounded LangGraph with explicit-intent gate and at most three reserved generation calls | Anchored intent coverage gate withheld even many valid natural-language requests |
| `argus ask --agent-v2` (M4v2-1) | Opt-in deterministic, source-verified explanatory answer path | Narrow informational routing; **never** releases candidate settings or commands |
| `v2_intent.py` (M4v2-2A) | Offline compositional extraction with spans, unresolved material and separate candidate checking | Bounded grammar; `enforced` does not prove complete intent |
| `v2_authorization.py` (M4v2-2B) | Offline candidate and trusted-observation evaluation, bound to settings, request, source/index and inherited env | Trusted live producers, full-intent verification and release checks **not integrated** |

**Important:** There is **no v2 recipe-generation/release path in production yet**. Offline eligibility is not a reusable authorization token. M3 and M4 v1 remain available for historical comparability and are not silently replaced by v2.

The versioned `argus-response-v2.0` contract separates `response_kind`, `answer_status`, `recipe_status`, `intent_coverage` and `material_constraints_status`. `command` and public `settings` are null except for an independently authorized validated recipe. See [response contract](docs/architecture/M4_V2_RESPONSE_CONTRACT.md), [M4 v2 design](docs/architecture/ARGUS_M4_V2_DESIGN.md) and [offline evaluation catalog](eval/m4v2/README.md).

## 4. Completed milestones and evidence

| Milestone | Status and evidence |
| --- | --- |
| **M0** Foundation | Complete. Packaging, CLI/config, restricted bridge, ADRs and CI. [PR #2](https://github.com/jalmqvist/argus-cli/pull/2). |
| **M1** MPML deterministic lookup | Complete. `inspect`, `explain`, defaults recipe and provenance. [PR #3](https://github.com/jalmqvist/argus-cli/pull/3). |
| **M2** Retrieval | Complete. Structured spec, indexed documents, lexical/embedding/hybrid ranking and index verification. [PR #4](https://github.com/jalmqvist/argus-cli/pull/4). |
| **M2.5** Retrieval evaluation | Complete. Frozen 20-question MPML retrieval benchmark; results in `eval/retrieval/`. |
| **M3** Local generation | Complete. Structured single-pass local Ollama recipe workflow and preflight. [PR #7](https://github.com/jalmqvist/argus-cli/pull/7). |
| **M3.5** Baseline evaluation | Complete. Frozen 20-case, three-model evaluation. [PR #8](https://github.com/jalmqvist/argus-cli/pull/8), [PR #9](https://github.com/jalmqvist/argus-cli/pull/9). |
| **M4A/B** Bounded agent | Complete. M4 v1 LangGraph design, opt-in orchestration, repair and offline gates. See [ADR 0004](docs/adr/0004-bounded-langgraph-orchestration.md). |
| **M4C** Paired and independent evaluation | Complete. Frozen 20-case regression reference; independent 26-question holdout split into 12 mechanically scored and 14 blindly reviewed cases. Findings in `docs/evaluation/`. |
| **M4v2-0** Response/routing contracts | Complete. Isolated typed contracts and synthetic acceptance cases. [PR #22](https://github.com/jalmqvist/argus-cli/pull/22). |
| **M4v2-1** Explanatory answer path | Complete. Opt-in deterministic cited answers, clean source/index verification, no model/preflight/command. [PR #23](https://github.com/jalmqvist/argus-cli/pull/23). |
| **M4v2-2A** Compositional intent | Complete. Offline requirement extraction, explicit unresolved spans and independent candidate consistency. [PR #24](https://github.com/jalmqvist/argus-cli/pull/24). |
| **M4v2-2B** Offline authorization boundary | Complete. Bound offline structural/evidence/material/preflight observations and mutation tests. [PR #25](https://github.com/jalmqvist/argus-cli/pull/25). |

### M3/M4C evaluation conclusions (historical, not v2 performance)

- M3.5 frozen 20: Qwen **12 pass / 7 fail / 1 review**, Gemma **11 / 8 / 1**, Llama **6 / 14 / 0**. Clean preflight sometimes coincided with wrong intent.
- M4 v1 versus M3 on the frozen 20: M4 v1 **9 pass / 11 fail**, M3 **12 pass / 7 fail / 1 review**. Historical comparison is a development/regression reference, not an independent holdout.
- Independent mechanical holdout (**12 questions**): M3 **7 pass / 4 fail / 1 review**; M4 v1 **0 pass / 12 fail**, with zero model calls. All M4 requests were stopped by deterministic intent coverage before generation/preflight.
- Independent manual-only subset (**14 questions**, blinded then unblinded): M3 **2 correct / 6 partial / 6 incorrect**; M4 v1 **0 correct / 0 partial / 14 incorrect**, all early abstentions without substantive explanations. Do **not** pool manual scores with machine pass rates or rank by dimension-point sums that award safety credits to abstention.
- These 26 independent cases have now been exposed for diagnostic analysis. Preserve the frozen reports, gold and grading methodology. They are **not** an untouched holdout for M4 v2.

See [M4C-3 machine findings](docs/evaluation/M4C_3_HOLDOUT_PAIRED_FINDINGS.md), [M4C-4 blind grade audit](docs/evaluation/M4C_4B_BLINDED_GRADE_AUDIT.md) and [M4C-4 combined findings](docs/evaluation/M4C_4_UNBLINDED_AND_COMBINED_FINDINGS.md).

### M4 v2 development measurements (synthetic only)

| Milestone | Recorded synthetic result | Interpretation limit |
| --- | --- | --- |
| v2-0 | 23 acceptance cases; 254 offline tests at PR creation | Contract and injected-observation consistency, **not** routing quality |
| v2-1 | 23/23 synthetic expected routes, 5 grounded answers, 18 withheld; 296 offline tests after routing correction | Bounded deterministic explanation coverage, **not** independent holdout improvement |
| v2-2A | 33/33 requirement precision and recall, 26/26 coverage labels; 0/11 false enforced; 0/21 false candidate acceptances; 0/12 false rejections; 302 offline tests | Synthetic grammar characterization, **not** semantic completeness |
| v2-2B | 39/39 blocker sets, 2 synthetic eligible and 37 withheld (six with unresolved material intent); 13/13 invalidating mutations blocked; 361 offline tests | Evaluates **supplied trusted observations**, not live authorization performance |

Counts are recorded snapshots of milestone validation runs, **not cumulative current test totals** and not estimates of real-world rates.

## 5. Forward roadmap — prioritized sequence

### M4v2-2C1 — Trusted live adapter integration (**next**)

**Goal:** Connect verified MPML source/index, exact candidate validation, citation resolution/support, inherited environment capture and authoritative preflight observations to `v2_authorization.evaluate()` using trusted in-process adapters. Begin with **fixed, sanitized candidate inputs**, not model generation.

**Requirements**

- Freeze one candidate and request interpretation, spec snapshot, evidence ID set and inherited environment; bind every producer observation to the same hashes.
- Use existing structure and preflight interfaces rather than reimplementing MPML parsing; prevent stale or model-authored observation records from asserting `trusted_adapter` authority.
- Define conservative deterministic support attestations for settings and values, including defaults-only. Citation mention alone is insufficient proof of semantics.
- Preserve full MPML preflight diagnostics; keep accepted-with-warnings distinct from warnings-only.
- Recheck source/index and relevant environment before final eligibility evaluation.
- **No command rendering or release, no Ollama calls and no experiment execution.** If the live source or adapter is unavailable, test the failure path offline with mocks.

**Exit evidence:** offline integration and adversarial tests for mismatched snapshots, settings, environment and evidence; real-MPML read-only local smoke test by the maintainer when feasible; exact candidate/provenance logs with no secrets; no unsafe releases.

### M4v2-2C2 — Material-intent completeness and effective-configuration study

**Goal:** Measure which naturally phrased MPML launch requests can be **independently** verified as complete and exactly represented. This is a research gate, **not** an assumed solved problem.

- Establish a reviewed taxonomy: explicit complete requests, incomplete/implicit requirements, ambiguous references, mixed answer/recipe, invalid exact values, unsupported capabilities and inferred defaults.
- Analyze false `enforced` interpretations and false acceptance of extra/omitted settings, especially negation, order, roles, env-only controls, precedence and inherited values.
- Compare purely deterministic coverage, targeted clarification and (if justified) **advisory** model-assisted interpretation. A model's own confidence, second opinion or self-check is never sufficient authorization.
- Define a conservative class of requests eligible for an independent completeness assessment; others remain unresolved and may receive a grounded explanation without a command.
- Use separately labeled new development cases and adversarial mutations; report exact denominators, false completeness, false withholding and unresolved rates.

**Exit decision:** an auditable trusted process can verify a useful subset of requests with **zero false authorization in the tested scenarios**, or the roadmap explicitly narrows v2 recipe release to proven subclasses. Do not promote generic `coverage=enforced` to `material_intent=verified`.

### M4v2-2C3 — Bounded local candidate generation and eventual manual release

**Prerequisites:** successful C1 integration and a defensible C2 completeness policy. Integrate Ollama as an **untrusted proposer** only. Reuse fixed retrieved evidence, structural checks, exact intent and environment checks and authoritative preflight, with fresh provenance at release. Introduce the trusted renderer only after all v2 gates pass.

- Keep M3/M4 v1 available and unchanged.
- Every attempted candidate must traverse the same validated snapshot and full release pipeline. No arbitrary shell instructions or hidden rewriting of invalid requests.
- Set and enforce a total model-call and time budget before adding interpretation or repair; preserve attempts, failure classifications and duplicate-candidate stopping.
- Report correct manual commands separately from accurate explanations and exact preflight rejections.

**Exit evidence:** controlled local recipe tests on new development cases, no command-release invariant violations, measured completion and false withholding—not just preflight pass count.

### M4v2-3 — Bounded repair and comparative development evaluation

Introduce classified repairs only for recoverable schema/representation/support errors, never to substitute a requested value or bypass uncertainty. Use transparent total call accounting. Compare M3, M4 v1 and v2 on **development/regression** cases under matched source, index, model digest and environment. Record initial/final outcomes, answer quality, command correctness, false withholding, abstentions, warnings, p50/p95 latency and all blocked releases. Keep machine and human grading regimes separate.

### M4v2-4 — New independent holdout and promotion decision

Commission separately authored and reviewed MPML questions, with provenance, fixed gold alternatives and a preregistered split between machine-scored recipes and human-reviewed factual answers. Freeze raw bytes and scoring policy **before** testing v2. Label as a new holdout version; do not modify M4C `holdout-v1`. Evaluate matched M3, M4 v1 and v2. Require defensible supported-task completion and false-withholding improvement with **zero observed command-release invariant violations**; report small-sample uncertainty rather than claiming universal safety.

### M5 — Portfolio release (later)

After an independent evaluation, prepare a reproducible fresh-clone demo, readable architecture diagram, local Ollama setup, model/ablation comparison and documented limitations. Public CI remains synthetic and must not require private MPML data or multi-GB models. Additional source adapters (MSML/BSVE/MRML) require separate ADRs and integration tests.

## 6. Evaluation discipline and promotion gates

Report **separately**:

1. **Answer quality:** supported factual claims, correct/partial/incorrect adjudication, evidence binding, meaningful limitations and unsupported capability responses.
2. **Recipe quality:** exact argv/env, complete preserved request, valid/invalid requested values, authoritative preflight, candidate release correctness and warnings.
3. **Coverage:** route classification, generation/preflight reachability, meaningful task completion, correct versus unnecessary withholding, unknown material requirements.
4. **Safety:** any wrong released command, evidence or provenance bypass, unsafe action, invented flag, false DL activation or command leakage. Zero observed violations is an acceptance criterion, not proof of zero population risk.
5. **Operations:** reserved/actual model calls, repair counts, end-to-end wall time, failures and timeouts (including abstentions), source/model/index hashes.

An accepted preflight is **necessary but insufficient** for recipe release. An `enforced` extractor label and candidate consistency are **necessary checks only within their defined scope**, not independent proof of full user intent. A successful answer with no command is valid in the v2 explanation contract and should not be judged against the recipe scorer. Material intent, effective configuration and evidence support must come from trusted independent procedures rather than from model assertion.

## 7. Repository, privacy and environment policy

Use Python 3.12, `pytest`, Ruff and GitHub Actions. Keep Argus's `argus` CLI local-first, allowlisted and read-only. Source integrations use each repository's interpreter and cwd, pinned spec and index; pass exact environment overrides to the preflight subprocess. Ollama runs locally when needed and has no access to arbitrary tools or broker operations. Embedding indices, raw prompts with sensitive data, private files and review A/B keys are not committed. CI relies on sanitized fixtures and mocks. Keep `MPML_REPO` and `MPML_PYTHON` as external configuration and do not vendor MPML code or data.

## 8. High-risk failure modes and mitigations

| Risk | Mitigation |
| --- | --- |
| Narrow language patterns cause false withholding | Separate explanation routing, compositional intent, coverage studies and clarification; measure task completion rather than regex coverage alone |
| `enforced` is mistaken for semantic completeness | Independent material-intent gate defaults to unresolved; adversarial tests for missed implicit constraints |
| Preflight accepts a wrong but syntactically valid candidate | Exact settings, independent intent/effective-configuration assessment, immutable provenance and fresh preflight |
| Candidate, preflight or evidence reflects different snapshots | Bind original request, argv/env, evidence IDs, source/spec/index and inherited env to trusted fingerprints; recheck before release |
| Citations mention a flag but do not support the proposed value | Require setting-level support attestations from verified evidence; do not equate retrieval with entailment |
| DL activation or artifact loading is claimed without proof | Preserve diagnostic semantics; never equate parser/preflight success with runtime activation |
| Model output or document injection attempts to bypass rules | No model authority, allowlisted read-only interfaces, independent validation and no arbitrary shell calls |
| Frozen holdout becomes iterative development data | Preserve archived findings; create a separately authored, frozen independent v2 holdout |

## 9. Definition of done for the MPML MVP

- Documented MPML configuration questions can yield verified, cited explanation-only answers without producing a command.
- For a supported, complete manual launch request, a candidate may be released **only** after all independent gates pass; otherwise return a grounded rejection/limitation or abstain without a runnable command.
- Local generation and any repair are bounded, auditable, reproducible and never execute experiments.
- A fresh-clone reviewer can run tests using public sanitized fixtures, examine exact schemas, and reproduce the local workflow with their own MPML checkout and local model.
- An independently frozen v2 evaluation demonstrates useful completion and no observed safety-gate bypass; all uncertainty and failures remain visible.

## 10. References and implementation workflow

- [M4 v2 architecture design](docs/architecture/ARGUS_M4_V2_DESIGN.md) — **historical design baseline**; its original “proposed/not implemented” and untracked-file statements are superseded by this roadmap and merged PRs #22–25.
- [M4 v2 response contract](docs/architecture/M4_V2_RESPONSE_CONTRACT.md)
- [M4v2-2A extraction study](eval/m4v2/INTENT_DEVELOPMENT.md)
- [M4v2-2B authorization study](eval/m4v2/AUTHORIZATION_DEVELOPMENT.md)
- [M4C-3 and M4C-4 findings](docs/evaluation/)
- [M4 v1 orchestration ADR](docs/adr/0004-bounded-langgraph-orchestration.md)
- `docs/prompts/` and `eval/` for milestone prompts, fixtures and scorer provenance.

Prefer **one reviewable PR per milestone**, with offline green tests, factual scope notes and separately archived local live-run evidence. Do not modify completed historical findings to improve apparent post-change results.
