# Argus CLI — Implementation Plan and Research Roadmap

**Status:** Updated 2026-11-27 · MPML-first, local-first, read-only · M4v2-3A/B/C development completed · next: v0.1.0rc1 release preparation and maintainer-local acceptance; independent M4v2-4 evaluation and redesign follow the preview

## 1. Purpose, scope and success criteria

Argus is a **local, privacy-preserving, read-only research assistant** for understanding how to configure and manually launch experiments in MPML. It combines authoritative MPML configuration interfaces, retrieval, optional local LLM generation, structured validation and reproducible evaluation. It **does not execute experiments or trading orders**. MSML, BSVE and MRML remain possible future source adapters, not current MVP dependencies.

The product distinguishes three useful outcomes:

1. **Grounded explanation:** factual, cited MPML setting guidance; no executable command.
2. **Qualified configuration guidance:** describe supported settings, observed preflight findings, missing information and unresolved limitations without publishing an unapproved, assembled, ready-to-run command or complete copyable argv/env recipe. Descriptions remain subject to independent factual/evidence checks, not model assertion.
3. **Verified manual launch recipe:** exact ordered argv and environment overrides, released only after independent evidence, structural, full material-intent, effective-configuration, provenance and authoritative MPML preflight gates succeed. A passing preflight **alone does not establish intent correctness**, execution, DL activation or artifact loading.

**Near-term success** is not simply more answered questions. It is greater completion of genuinely supported tasks without incorrect command release, while preserving honest withholding when evidence or intent remains unresolved. Separate explanatory-answer completion from recipe correctness and report false withholding, incorrect commands, uncertainty, calls and latency.

### MVP engineering priorities

- **Release a truthful, working preview before broader optimization:** deliver installable, source-grounded, read-only MPML inspection, retrieval, preflight and qualified v2 advisory functionality as `v0.1.0rc1` after clean-install/CI/local acceptance checks. Do not equate release readiness with general natural-language recipe correctness or complete intent certification. See [release scope and gates](docs/releases/V0_1_0_RC1_SCOPE.md).
- **Usability before comprehensiveness:** first ship a helpful opt-in v2 assistant that answers grounded questions and explains why some recipes cannot yet be certified; measure unnecessary withholding as well as unsafe releases.
- **Fixed hardware budget:** maintain practical operation on the maintainer's NVIDIA GTX 1070 with **8 GB VRAM**. Keep the existing local `qwen2.5-coder:7b` baseline; no larger model, second verifier model, GPU upgrade, or always-on multi-pass inference required for MVP. Prefer one generation attempt, no automatic repair initially; measure real latency and memory rather than assume a model fits fully in VRAM.
- **Do not weaken release claims:** `validated` still requires all trusted recipe gates. When those gates fail, offer independently grounded, explicitly limited help, not a disguised runnable recipe. Keep model-authored candidates private until release.

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
| `argus ask --agent-v2` (M4v2-1/C3) | Deterministic cited answers, or one local Qwen proposal with trusted validation and qualified explanation | Natural-language and evidence coverage incomplete; no v2 command release |
| `v2_intent.py` (M4v2-2A) | Offline compositional extraction with spans, unresolved material and separate candidate checking | Bounded grammar; `enforced` does not prove complete intent |
| `v2_authorization.py` (M4v2-2B) | Offline candidate and trusted-observation evaluation, bound to settings, request, source/index and inherited env | Full material-intent verification and release checks are **not established** |
| `v2_live_validation.py` (M4v2-2C1/C2A) | Trusted fixed-candidate validation via real MPML spec/index and read-only preflight; per-selector seed/variant precedence observations | Full material-intent and aggregate effective-configuration gates unresolved; no v2 command release |
| `eval/m4v2/run_development.py` (M4v2-3A) | Private first-attempt candidate evaluation, retrieval/citation attribution and local timing | Developer-authored fixture; human grading and independent generalization remain open |

**Important:** V2 now has an **untrusted recipe-proposal path**, but **no independently authorized v2 recipe-release path**. The public v2 response keeps `settings` and `command` null. Offline eligibility is not a reusable authorization token. M3 and M4 v1 remain available for historical comparability and are not silently replaced by v2.

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
| **M4v2-2C1** Trusted live integration | Complete. Fixed-candidate trusted bridge with captured environment and redacted diagnostics [PR #27](https://github.com/jalmqvist/argus-cli/pull/27). Maintainer-local real-MPML smoke accepted; only material-intent and effective-configuration blockers remained. Evidence in [LIVE_VALIDATION.md](eval/m4v2/LIVE_VALIDATION.md), archived via [PR #28](https://github.com/jalmqvist/argus-cli/pull/28). |
| **M4v2-2C2A** Narrow effective configuration | Complete. Verified seed and canonical variant precedence; eight maintainer-local real-MPML smoke cases passed. [PR #30](https://github.com/jalmqvist/argus-cli/pull/30). |
| **M4v2-2C3** One-shot local proposal workflow | Complete. Deterministic explanations plus one local Qwen proposal, trusted checks, private candidate and qualified response; no command release. [PR #31](https://github.com/jalmqvist/argus-cli/pull/31). |
| **M4v2-3A** First-attempt local evaluation harness | Complete. 14 developer-authored cases, exact candidate scoring, evidence attribution and private capture. [PR #32](https://github.com/jalmqvist/argus-cli/pull/32). |
| **M4v2-3B** Baseline findings | Initial descriptive review complete. Three correct and four incorrect candidates, one exact-invalid-request, one manual review, five not-applicable; see [local findings](eval/m4v2/FIRST_ATTEMPT_FINDINGS_3B.md). Human gold/answer adjudication is outstanding. |

### M3/M4C evaluation conclusions (historical, not v2 performance)

- M3.5 frozen 20: Qwen **12 pass / 7 fail / 1 review**, Gemma **11 / 8 / 1**, Llama **6 / 14 / 0**. Clean preflight sometimes coincided with wrong intent.
- M4 v1 versus M3 on the frozen 20: M4 v1 **9 pass / 11 fail**, M3 **12 pass / 7 fail / 1 review**. Historical comparison is a development/regression reference, not an independent holdout.
- Independent mechanical holdout (**12 questions**): M3 **7 pass / 4 fail / 1 review**; M4 v1 **0 pass / 12 fail**, with zero model calls. All M4 requests were stopped by deterministic intent coverage before generation/preflight.
- Independent manual-only subset (**14 questions**, blinded then unblinded): M3 **2 correct / 6 partial / 6 incorrect**; M4 v1 **0 correct / 0 partial / 14 incorrect**, all early abstentions without substantive explanations. Do **not** pool manual scores with machine pass rates or rank by dimension-point sums that award safety credits to abstention.
- These 26 independent cases have now been exposed for diagnostic analysis. Preserve the frozen reports, gold and grading methodology. They are **not** an untouched holdout for M4 v2.

See [M4C-3 machine findings](docs/evaluation/M4C_3_HOLDOUT_PAIRED_FINDINGS.md), [M4C-4 blind grade audit](docs/evaluation/M4C_4B_BLINDED_GRADE_AUDIT.md) and [M4C-4 combined findings](docs/evaluation/M4C_4_UNBLINDED_AND_COMBINED_FINDINGS.md).

### M4 v2 development measurements (offline synthetic checks and local results separated)

| Milestone | Recorded synthetic result | Interpretation limit |
| --- | --- | --- |
| v2-0 | 23 acceptance cases; 254 offline tests at PR creation | Contract and injected-observation consistency, **not** routing quality |
| v2-1 | 23/23 synthetic expected routes, 5 grounded answers, 18 withheld; 296 offline tests after routing correction | Bounded deterministic explanation coverage, **not** independent holdout improvement |
| v2-2A | 33/33 requirement precision and recall, 26/26 coverage labels; 0/11 false enforced; 0/21 false candidate acceptances; 0/12 false rejections; 302 offline tests | Synthetic grammar characterization, **not** semantic completeness |
| v2-2B | 39/39 blocker sets, 2 synthetic eligible and 37 withheld (six with unresolved material intent); 13/13 invalidating mutations blocked; 361 offline tests | Evaluates **supplied trusted observations**, not live authorization performance |

Counts are recorded snapshots of milestone validation runs, **not cumulative current test totals** and not estimates of real-world rates.

**Actual local M4v2-3A baseline (developer-authored, not an independent holdout):** 14 complete cases; eight model attempts; candidate grades 3 correct, 4 incorrect, 1 exact-invalid-request, 1 needs-manual-review, 5 not-applicable; five accepted MPML preflights; zero recipes released. Generation median/p95 7.113/9.135 seconds (8 attempts); total median/p95 7.934/12.260 seconds (14 cases). The fixture's gold alternatives and human answer/usefulness scores still need independent review. See [M4v2-3B findings](eval/m4v2/FIRST_ATTEMPT_FINDINGS_3B.md).

## 5. Forward roadmap — prioritized sequence

### v0.1.0rc1 — Read-only developer preview (**next release checkpoint; not yet published**)

**Goal:** Publish an installable, accurately scoped working version without rushing redesign or relaxing command-release gates. [Release scope, acceptance gates and post-preview priorities](docs/releases/V0_1_0_RC1_SCOPE.md) are the governing checklist.

- **Release preparation:** clean up onboarding/README to recommend `argus ask --agent-v2` for grounded/qualified assistance while explicitly labeling default M3 `argus ask` and M4 v1 `--agent` as legacy/experimental; do not silently change old mode behavior. Align package metadata and intended `v0.1.0rc1` Git tag, prepare build, clean-install and release notes.
- **Release blockers:** public synthetic CI/tests and Ruff; successful wheel/sdist build and installed CLI entrypoint; maintainer-local smoke of pinned clean MPML spec, inspect/explain, lexical index and retrieve, read-only explicit preflight, deterministic v2 answer and one local-Qwen v2 assessment. Confirm `command=null`/`settings=null` in v2 and no experiments or broker actions. Document exact evidence and hashes before tagging.
- **Publication rule:** release-preparation PR first, then reviewer-approved verified GitHub pre-release/tag. No release label or claim that checks passed ahead of evidence. PyPI publication is outside this checkpoint without separate approval.
- **Claims:** working local read-only developer preview; **not** certified general natural-language manual recipes. Report 5/7 exact-correct first-attempt supported configurations in the developer-authored paired regression with sample/denominator limitations, not as holdout success. Document environment-only and `ACTIVE_PAIRS` failures, plus incomplete material-intent and aggregate effective-configuration certification.

**After the preview:** diagnose the two errors, independently review answer usefulness/false withholding and gold alternatives, and run a separately authored/frozen M4v2-4 evaluation. Treat later broader redesign and a stable `v0.1.0` decision as evidence-led, not deadline-driven.

### M4v2-2C1 — Trusted live adapter integration (**complete**)

The fixed-candidate live validation adapter is merged ([PR #27](https://github.com/jalmqvist/argus-cli/pull/27)). The documented maintainer-local read-only smoke on pinned MPML revision `14ad36e3…` verified provenance, environment, structure, citations and support, and returned preflight `accepted` (exit 0). Only `material_intent` and `effective_configuration` remained unresolved, as designed. [Recorded observations](eval/m4v2/LIVE_VALIDATION.md) are not an LLM or generalization evaluation.

### M4v2-2C2A — Minimal effective-configuration verification (**complete**)

**Goal:** Build a deterministic, bounded resolver for **common** documented MPML launch selectors using the pinned spec, exact candidate argv/env and captured inherited environment. Report value, winning channel/precedence and an evidence basis only where explicitly supported by the spec; otherwise report `unresolved` with reasons.

- Begin with a narrow, documented allowlist (for example variant, seed and output-directory precedence where the published spec genuinely supports the interpretation). Verify real spec shape before selecting targets. Do not infer defaults or unspecified runtime behavior from parser defaults alone.
- Account for CLI > explicit env > inherited env > documented fallback *only when that precedence is published*. Preserve strings and distinguish absent, empty, whitespace and invalid values per documented semantics; do not silently normalize candidate values.
- Keep source/spec/index and environment binding intact; do not use model-produced observations as authority.
- Make the result independently testable with synthetic precedence/edge-case fixtures; optionally compare a small number of cases with read-only real-MPML preflight. Preflight acceptance is not evidence that every effective setting was resolved.
- **No new model calls, no broad intent oracle, no new command release.** Unresolved effective values must remain unresolved; the separate complete-intent gate is unchanged.

**Exit evidence:** scoped effective-value resolution with exact evidence/provenance, adversarial tests for precedence and inherited-env drift, and a clearly enumerated unsupported surface.

### M4v2-2C3 — First usable v2 answer/candidate workflow (**complete**)

**Goal:** Connect existing local Ollama (`qwen2.5-coder:7b`) as a one-shot, **untrusted proposer**, preserving the previous deterministic explanatory route, verified MPML evidence and trusted fixed-candidate checks. Prioritize a useful opt-in user experience on 8 GB VRAM rather than broad semantic certification.

- Route supported questions to a grounded answer without requiring command eligibility. For recipe requests, propose a structured candidate, run the existing structural/evidence/preflight/intent checks and return a **grounded, qualified explanation** when the complete-command gates remain unresolved; do not expose an unapproved complete candidate as a runnable or copyable recipe.
- Release a command **only** if all existing full material-intent, effective-configuration and release gates are independently verified; absent that capability, no v2 recipe release yet. Do not change the meaning of `validated`.
- Start with **one** local model invocation and **no automatic repair**, bounded timeouts and explicit call accounting. No additional inference model or hardware upgrade required.
- Preserve M3, M4 v1 and deterministic v2-1 behavior unchanged. Track separate `answer_delivered`, `candidate_proposed`, `preflight_attempted`, `recipe_withheld`, `recipe_released`, error and latency counts. Never treat a nice-sounding explanation as claim-level validation.
- Develop new, varied user questions and evaluate actual task usefulness, false withholding, incorrect settings and failure attribution on the maintainer's GTX 1070.

**Exit evidence:** a working opt-in v2 end-to-end conversational workflow that provides substantive, appropriately qualified answers and safe candidate diagnostics on actual local hardware, even if `recipe_released=0`. Do not advertise validated recipe output until independently supported.

### M4v2-2C2B — Material-intent completeness study (**parallel/follow-on; not an MVP prerequisite for qualified answers**)

Use actual C3 failures to study which natural-language request classes can have their complete material intent independently verified. Compare bounded deterministic representations, targeted clarification and advisory model interpretation; no model self-certification. Measure false-completeness versus unnecessary-withholding rates on new development cases. Promote only a defensible, bounded subset to independently verified recipe eligibility; the rest still receive grounded qualified guidance. Broader coverage work is incremental, not a blocker to the first useful answer/candidate workflow.

### M4v2-3 — Practical development evaluation and evidence-led improvements (**3A/B/C complete; further work after preview**)

**3A (complete):** The maintainer-local first-attempt harness ran 14 developer-authored cases using the existing GTX 1070/Qwen setup with reproducible source/model/index hashes and independent candidate scoring. **3B (initial descriptive review complete):** [Findings](eval/m4v2/FIRST_ATTEMPT_FINDINGS_3B.md) identify a false routing exclusion, correct model candidates with incomplete seed evidence, incorrect environment/pair/PhaseAware proposals, and generic response limitations. Human gold review and factual/usefulness adjudication remain open; do not describe them as completed scores.

**3C (complete; paired local development regression):** The same 14 developer-authored cases were rerun under identical MPML spec/index, Qwen digest and fixture hashes after targeted routing, retrieval, seed-type evidence, prompt and qualified-response changes. Exact-correct supported configuration candidates increased from 3/7 to **5/7**; incorrect candidates fell from 4 to **2**; both invalid-exact requests were preserved and rejected structurally rather than substituted. Generation attempts rose 8→9; accepted read-only preflights 5→6; commands released **0** in both runs. Generation median was 7.113→6.804 s (different number of calls); total median 7.934→8.100 s. See [paired 3C findings](eval/m4v2/PAIRED_FINDINGS_3C.md). These are **paired development** measurements and do not isolate the effect of retrieval versus prompt changes or establish generalization.

**Next restart checkpoint (not yet implemented):** Diagnose the two persistent errors—environment-only requests that still receive extra CLI settings, and missing `ACTIVE_PAIRS` pair filtering. Independently review gold alternatives, factual answer quality, user usefulness and unnecessary withholding; these review outcomes remain unresolved. Only then decide whether a narrow follow-up is warranted before a separately authored/frozen M4v2-4 holdout. Maintain one local Qwen call, bounded eight-excerpt evidence, no automatic repair and no verified v2 command release until all independent gates exist and pass.

Only consider classified repair or larger-model ablations if subsequent failure evidence and practical latency justify them. Compare M3, M4 v1 and v2 on explicitly labeled development/regression cases under matched conditions as appropriate; never reuse exposed M4C cases as fresh holdout evidence. Independent promotion still requires M4v2-4.

### M4v2-4 — New independent holdout and promotion decision (**after v0.1.0rc1**)

Commission separately authored and reviewed MPML questions, with provenance, fixed gold alternatives and a preregistered split between machine-scored recipes and human-reviewed factual answers. Freeze raw bytes and scoring policy **before** testing v2. Label as a new holdout version; do not modify M4C `holdout-v1`. Evaluate matched M3, M4 v1 and v2. Require defensible supported-task completion and false-withholding improvement with **zero observed command-release invariant violations**; report small-sample uncertainty rather than claiming universal safety.

### M5 — Stable release and portfolio polish (later)

The `v0.1.0rc1` read-only preview is the earlier release milestone; M5 is a **separate stable-promotion and portfolio-quality** checkpoint, not a prerequisite for the candidate. Following independent evaluation, refine the fresh-clone demo, architecture diagram, local Ollama setup and limitations for the 8 GB VRAM target. Larger-model ablations are optional, not a release prerequisite. Public CI remains synthetic and must not require private MPML data or multi-GB models. Additional source adapters (MSML/BSVE/MRML) require separate ADRs and integration tests.

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

**Preview (`v0.1.0rc1`) and stable promotion have different gates.** The preview requires the clean-install, CI, read-only local source and v2 smoke checks in [release scope](docs/releases/V0_1_0_RC1_SCOPE.md), plus accurate capability/limitation documentation. It does **not** claim general verified natural-language recipe release or require a new independent holdout before its first publication. The stronger targets below remain appropriate for later stable promotion and continuous research.

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
- [M4v2-3A local evaluation method](eval/m4v2/FIRST_ATTEMPT_DEVELOPMENT.md)
- [M4v2-3B local findings](eval/m4v2/FIRST_ATTEMPT_FINDINGS_3B.md)
- [M4v2-3C paired local findings and restart point](eval/m4v2/PAIRED_FINDINGS_3C.md)
- [v0.1.0rc1 preview scope and release gates](docs/releases/V0_1_0_RC1_SCOPE.md)
- [M4C-3 and M4C-4 findings](docs/evaluation/)
- [M4 v1 orchestration ADR](docs/adr/0004-bounded-langgraph-orchestration.md)
- `docs/prompts/` and `eval/` for milestone prompts, fixtures and scorer provenance.

Prefer **one reviewable PR per milestone**, with offline green tests, factual scope notes and separately archived local live-run evidence. Do not modify completed historical findings to improve apparent post-change results.
