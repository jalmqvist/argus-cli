# Argus CLI — M3.5 Single-Pass Generation Baseline: Findings

**Date:** 2026-11-25  
**Status:** Completed empirical baseline; findings for M4 planning  
**Scope:** Read-only MPML launch-recipe assistant; no execution of generated experiments or broker operations  
**Evidence:** `benchmark.tgz` containing `qwen-hybrid.json`, `gemma-hybrid.json`, `llama-hybrid.json`, and `qwen-debug.json`; frozen 20-case `eval/generation/baseline-v1.json` in argus-cli PR #8.  
**Related milestones:** M2.5 retrieval evaluation; M3 structured generation; planned M4 bounded LangGraph orchestration.

## 1. Executive summary

M3.5 measures the **single-pass** performance of three local Ollama language models on 20 frozen MPML launch-configuration questions using the same hybrid retrieval index and deterministic Argus validators. All 60 full-benchmark attempts completed without wall-clock timeouts.

| Outcome | Qwen2.5-Coder 7B | Gemma4 E2B | Llama3.1 8B |
|---|---:|---:|---:|
| Pass | **12/20 (60%)** | 11/20 (55%) | 6/20 (30%) |
| Fail | 7/20 (35%) | 8/20 (40%) | 14/20 (70%) |
| Human review | 1/20 (5%) | 1/20 (5%) | 0/20 |
| Structural validation passed | 16/20 | 14/20 | 12/20 |
| MPML preflight passed | 13/20 | 11/20 | 9/20 |
| Preflight passed **despite wrong intent** | 3 | 2 | 4 |
| Generator/citation rejections | 4 | 6 | 8 |
| Correct diagnostic-code comparison | 19/20 | See case-level report | See case-level report |

**Principal finding:** deterministic MPML preflight is necessary but insufficient for user-intent correctness. All three models sometimes produced valid settings that contradicted explicit requirements. The existing deterministic boundaries successfully intercepted many malformed or unsupported candidates, but a valid command is not necessarily a faithful command.

**Model selection:** Qwen is the strongest initial M4 development baseline **on this dataset**, narrowly outperforming Gemma while exhibiting the lowest observed median latency. The sample is small, deliberately constructed, and not sufficient to establish universal model superiority.

**Shared difficulty:** `multi-strategy`, `pair-list`, `phaseaware-wrong-role`, `strict-dl-boolean`, `artifact-alias`, and `unsupported-order` failed for all three models. These cover repeated strategy flags, pair filtering without unsolicited strategies, preserving an invalid requested role, strict boolean interpretation and abstention, environment-versus-flag distinctions, and refusal of unsupported brokerage functionality.

## 2. Research question and methodology

### 2.1 Research questions

1. Can a single-pass model generate a schema-valid, cited MPML configuration candidate?
2. Does authoritative MPML preflight accept that candidate?
3. Does the proposed configuration actually preserve the user's **stated intent**?
4. When a request is unsupported or underdetermined, does the model decline or return an explicitly permitted preflight rejection?
5. What are the latency and failure patterns relevant to a future bounded repair agent?

### 2.2 Design

- **Fixture:** 20 frozen, public, sanitized questions, including valid selectors, precedence, multi-setting requests, PhaseAware constraints, DL semantics, contradictions, unspecified information, and unsupported broker actions.
- **Gold standards:** explicit accepted `argv` / environment override alternatives, expected verification disposition, and expected preflight diagnostic codes. The scorer treats `--flag=value` and `--flag value` as equivalent; additional equivalences must be enumerated.
- **Pipeline:** current Argus M3 `ask` path → hybrid retrieval → single local model generation → structural and evidence validation → MPML preflight when eligible → deterministic offline scoring.
- **Outcomes:** `pass`, `fail`, or `review`. An accepted abstention with an explanation is marked `review` until its reasoning is checked. Review is not included in pass counts.
- **No execution:** returned shell commands are recommendations for manual use; no experiments or broker actions are executed.
- **Data policy:** the earlier Qwen one-case `qwen-debug.json` is a **smoke test**, not an additional benchmark question and not part of the 20-case scores.

**Interpretation note:** The baseline's `intent_match` is a comparison with enumerated gold recipes, not a general natural-language entailment oracle. Citation validity verifies grounded source identity/production checks, not whether the cited material semantically proves every explanation. A recorded `pass` does not prove runtime execution or trading behavior.

## 3. Provenance and comparability

All three full runs record:

| Parameter | Recorded value |
|---|---|
| MPML revision | `14ad36e3f70a10bb5781b88200e825a717ca402f` |
| MPML source state | `dirty: false` in all three full-run manifests |
| MPML spec SHA-256 | `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` |
| Frozen dataset SHA-256 | `3812cc04d0d738403432e5443501716edf11518cf32f054aa3b2a1835c824751` |
| Retrieval index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` |
| Retrieval | Hybrid, top 5; `nomic-embed-text` |
| Embedding-model digest | `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f` |
| Generation settings | temperature `0`, seed `42`, context `8192`, prediction limit `1100`, generation timeout `300s` |
| Ollama | `0.40.15` |
| Argus HEAD | `f22ae330ae3946984bf0368faaca835d1e4c833e` |

Generation model digests are recorded individually in the full JSON manifests. The dataset, index, source, model-generation settings, environment fingerprint, and Argus implementation-file hashes match across the three runs; the model choice differs as intended.

**Working-tree qualification:** the Qwen full-run manifest records Argus `dirty: false`, while Gemma and Llama record `dirty: true`. The maintainer identified this as benchmark-generated log/output files in the cloned worktree, **not a source-code change or an error**. Recorded implementation-file hashes match across runs; the indicator alone is not a reason to reject the comparison or rerun the benchmarks. Retain the dirty flag as provenance rather than silently altering it. MPML's *separate pinned source worktree* remained clean for all full runs.

**No retrieval-mode ablation:** this archive contains hybrid full runs only. There are no lexical full-run results and no no-retrieval evaluation. M2.5 retrieval metrics should not be mixed into M3.5 generation accuracy.

## 4. Aggregate model performance

### 4.1 Quality and validation

| Metric | Qwen | Gemma | Llama |
|---|---:|---:|---:|
| Completed attempts | 20 | 20 | 20 |
| Pass | 12 | 11 | 6 |
| Fail | 7 | 8 | 14 |
| Review | 1 | 1 | 0 |
| Structural validation passed | 16 | 14 | 12 |
| Structural validation failed | 4 | 6 | 8 |
| Preflight passed | 13 | 11 | 9 |
| Preflight failed | 2 | 2 | 3 |
| Preflight not run | 5 | 7 | 8 |
| Preflight passed with wrong intent | **3** | **2** | **4** |
| Candidate rejection | 4 | 6 | 6 |
| Citation rejection | 0 | 0 | 2 |
| Citation valid | 16 | 14 | 12 |
| Citation invalid | 0 | 0 | 2 |
| Citation not evaluated | 4 | 6 | 6 |
| Correct abstention, pending review | 1 | 1 | 0 |

The `preflight passed with wrong intent` metric is diagnostic of a genuine gap: the MPML specification verifies allowed configurations, not whether a particular configuration fulfills the user's natural-language request. These cases should motivate intent checks *before* releasing a recipe, not merely additional retries after parser errors.

### 4.2 Local inference latency

| Timing | Qwen | Gemma | Llama |
|---|---:|---:|---:|
| Generation p50 | **4.49 s** | 6.76 s | 5.24 s |
| Generation p95 | 5.68 s | 10.03 s | 7.22 s |
| End-to-end p50 | **8.39 s** | 10.41 s | 8.77 s |
| End-to-end p95 | **9.36 s** | 14.40 s | 16.11 s |

The benchmark records 20 timing samples per model. These are observed local measurements, not guarantees of deterministic latency or estimates for other machines. The earlier single-case Qwen debug run took **16.98 s generation / 21.10 s total**, illustrating possible variation and warmup effects; it is not pooled with the full-run distribution. A repair loop is likely to incur additional model-call latency, so M4 should report end-to-end wall time and repair-attempt count, not only the final response quality.

## 5. Case-level comparison

Legend: **P** = pass, **F** = fail, **R** = human review.

| Frozen case | Qwen | Gemma | Llama |
|---|:---:|:---:|:---:|
| `strategy-and-pair` | P | F | P |
| `explicit-seed` | P | P | F |
| `seed-env` | P | P | F |
| `seed-precedence` | P | P | P |
| `variant-env` | P | P | F |
| `variant-precedence` | P | P | P |
| `variant-and-seed` | P | P | P |
| **`multi-strategy`** | **F** | **F** | **F** |
| **`pair-list`** | **F** | **F** | **F** |
| `surface` | P | P | F |
| `surface-precedence` | P | P | P |
| `phaseaware-roles` | P | P | F |
| **`phaseaware-wrong-role`** | **F** | **F** | **F** |
| **`strict-dl-boolean`** | **F** | **F** | **F** |
| **`artifact-alias`** | **F** | **F** | **F** |
| `dl-proof` | R | F | F |
| `contradictory-generation` | P | P | F |
| `unspecified-strategy` | F | R | F |
| `unknown-strategy` | P | P | P |
| **`unsupported-order`** | **F** | **F** | **F** |

**Pattern:** basic selections, precedence and known-invalid strategy diagnostics were relatively robust for Qwen and Gemma. Shared failures concentrated in exact constraint preservation, representation of environment settings, and safe abstention. Llama additionally duplicated settings across CLI/env, invented unsupported selectors, and incurred citation failures.

## 6. Raw-response findings and failure taxonomy

The following examples are drawn from the archived `attempts[*].report` fields and compared with the frozen case expectations. Distinguish the model's **reported reasoning** from verified MPML behavior.

### 6.1 Structural representation errors: repairable candidates

**`artifact-alias` (all models failed).** The user requested DL off, an explicitly empty primary artifact path, and a legacy cube-path override. Qwen generated:

```text
argv = ["--DL_SIGNALS_CUBE_PATH", "example-cube.parquet"]
env  = {"DL_PREDICTION_ARTIFACT_PATH": ""}
```

The validator rejected the invented command-line flag (`Unknown flag or unexpected argument`). A faithful answer would use environment overrides—including `DL_SIGNALS_ENABLED=false` and `DL_SIGNALS_CUBE_PATH=example-cube.parquet`—with an empty `DL_PREDICTION_ARTIFACT_PATH`, and preserve the expected alias-suppression warning. Gemma similarly placed `DL_SIGNALS_CUBE_PATH=...` into `argv`; Llama proposed unsupported DL flags. This class plausibly benefits from structured repair grounded in the **flag/environment inventory**.

**`multi-strategy` (all failed, for different reasons).** Qwen asserted that the requested repeated `--strategy` launch was invalid and generated an invalid abstention (no uncertainty reason). Gemma used `--phaseaware-tf TF4 --phaseaware-mr MR32`, confusing PhaseAware representatives with explicit evaluation strategy selection; MPML preflight passed, but intent failed. Llama mixed `--strategy TF4` with a PhaseAware flag and unsupported environment overrides. The correct representation is two ordered `--strategy` occurrences. Repair needs to respect the original task, not merely produce a parseable command.

**`strategy-and-pair` (Gemma only).** Gemma appended `ACTIVE_PAIRS=USDJPY` to `argv` rather than setting it in `env`, causing a structural rejection. This is a clear command/environment separation failure.

**`pair-list` (all failed).** Qwen correctly set `ACTIVE_PAIRS=USDJPY,EURUSD` but injected `--strategy MR1 --strategy MR2` although defaults were requested. Gemma generated an empty string `argv` element, causing structural rejection despite a correct pair override. Llama supplied numerous unnecessary or invalid strategy flags (including currency pairs used as strategies) and reversed the specified pair order. This case combines candidate normalization and explicit-intent checks.

### 6.2 Valid configurations that silently change intent: preflight alone cannot repair

**`phaseaware-wrong-role` (all failed).** The request explicitly insisted on MR32 as the *trend-following* PhaseAware representative and prohibited substitution. Qwen and Gemma changed this to `--phaseaware-mr MR32`, which MPML accepted but violated the request. Llama also substituted the mean-reversion role and added an unsupported `PHASEAWARE_MR` override. The appropriate response is abstention or an exact attempted `--phaseaware-tf MR32` rejected with `PHASEAWARE_ROLE_INVALID`. An agent that only retries on preflight errors would miss the valid-but-wrong Qwen/Gemma outputs.

**`unspecified-strategy` (Qwen and Llama failed; Gemma requires human review).** The user supplied no strategy identifier and explicitly said not to pick others. Qwen invented `--phaseaware-mr MR2 --phaseaware-tf TF3`, passing preflight. Llama invented representatives and additional environment settings; citations were rejected. Gemma abstained with the correct missing-information explanation, marked `review`. This case demonstrates the need to retain information sufficiency, not derive a purported prior user choice from retrieved documentation.

**`pair-list` (Qwen) and simple cases (Llama).** Qwen's extra strategy flags survived preflight. Llama's `explicit-seed`, `seed-env`, `variant-env`, and `surface` sometimes specified both a CLI flag and environment override when the question required just one interface. Although accepted by MPML, they violated explicit user constraints.

### 6.3 Correct safety reasoning with an invalid abstention contract

**`strict-dl-boolean` (all failed).** Qwen and Gemma correctly explained that `DL_SIGNALS_ENABLED=1` does **not** enable DL, but produced empty `argv`/`env` without the nonempty uncertainty field required for abstention, yielding `An abstention requires empty argv/env and a reason`. Llama incorrectly stated that `1` enables DL and attempted to put Python code in launch arguments. A structural repair can address Qwen/Gemma's representation issue, while Llama's error requires factual correction from source evidence.

**`unsupported-order` (all failed).** Qwen and Gemma correctly described live broker orders as unsupported by the MPML launch surface, but again generated invalid abstentions without the required uncertainty reason. Llama invented a purported broker-data flag rather than declining the brokerage request. The structural validator rejected the invalid proposals. A bounded abstention-normalization path could help without fabricating an order API.

### 6.4 Correctly handled invalid requests and permitted rejections

**`contradictory-generation`:** Qwen and Gemma provided the requested incompatible `gen2`/variant-A combination and received the expected `GENERATION_VARIANT_MISMATCH`. Llama also received that diagnostic but added an unwanted `EXPERIMENT_VARIANT=A` override, so its case failed on intent.

**`unknown-strategy`:** all three supplied the requested invalid `ZZ999` strategy and received the expected `STRATEGY_UNKNOWN` rejection; the frozen fixture explicitly permits this route rather than requiring a pure abstention.

**`dl-proof`:** Qwen abstained with a nonempty uncertainty list and stated that preflight cannot prove DL activation and artifact loading; this is correctly categorized as **human review**, not an automated pass. Gemma and Llama generated unsupported commands or selectors, which were rejected.

## 7. Interpretation: what is established, and what is not

### Supported by the data

1. The three complete hybrid evaluations ran on the same frozen dataset/index/source and produced 60 saved attempts.
2. Qwen produced the strongest *observed* pass count and median latency among the three local configurations.
3. All three models encountered six common failures, so model substitution alone does not resolve these cases within this setup.
4. Existing structural and citation validation intercepted malformed flags, unsupported environment names, and unsupported citations.
5. Successful preflight did not ensure intent adherence: the reports explicitly identify 3 Qwen, 2 Gemma and 4 Llama cases where preflight passed with mismatched intent.
6. Some incorrect abstentions were **format failures despite a correct textual explanation**, which suggests a targeted recovery mechanism may have value.

### Not established / limitations

- **No causal attribution to retrieval, prompting or model weights.** This was not a controlled ablation of those components. Individual raw outputs support diagnostic hypotheses, not proven causes.
- **Small curated question set.** Results describe these 20 source-authored tasks, not general robustness or out-of-distribution performance. Some requests use flag/env names explicitly, potentially favoring models familiar with CLI syntax.
- **Scorer strictness.** Equivalent representations not enumerated in the fixture may be scored as failures. Conversely, mechanically passing recipes can still include misleading prose. All nontrivial failures and abstention explanations merit manual inspection.
- **Review cases unresolved.** Neither Qwen's `dl-proof` nor Gemma's `unspecified-strategy` should be silently counted as a pass without documenting human adjudication.
- **Citation semantic strength unmeasured.** Source identity and production validation do not entail full substantive support for the model's description.
- **No independent repeated-seed runs or confidence intervals.** Scores and latency are descriptive; deterministic generation settings alone do not prove bitwise-repeatability.
- **No actual experiment execution.** Validity is based on CLI/launch semantics and preflight, not completed strategy evaluation, runtime DL loading, or trading results.
- **No full lexical/no-retrieval generation control.** The relative role of retrieval mode in these failures is not measured.

## 8. Implications for M4: evidence-driven architecture

### 8.1 Separate three validation boundaries

**Boundary A — Candidate and evidence structure:** validate schemas, legal CLI flags, env names, argument encoding, citation IDs, and abstention fields. For abstentions, explicitly require a reason. Structured errors should identify the illegal field/value. Retain fail-closed handling.

**Boundary B — Authoritative MPML preflight:** pass the exact validated candidate and overrides to the existing MPML preflight adapter; preserve issue codes and warnings unchanged. A rejected candidate may be an appropriate final answer **only** where the user requested an invalid configuration or the permitted response policy makes rejection informative. Do not run experiments.

**Boundary C — Explicit user-intent preservation:** independently inspect checkable requirements **even when preflight passes**, including requested strategy list/order, pair list/order, exact CLI-vs-env placement, forbidden extra selectors, invalid-role non-substitution, and absent identifying information. Do not assume full natural-language entailment can be solved deterministically in the first M4 iteration. Keep unverified semantic claims visibly unverified.

### 8.2 Bounded orchestration

A defensible first LangGraph state machine is:

```text
retrieve evidence
    -> generate candidate
    -> structural/citation validation
    -> MPML preflight (only if structurally valid)
    -> explicit intent checks
    -> validated recipe / bounded repair / abstention
```

Proposed limits: **at most two repair attempts**, with total model calls and elapsed time recorded. Every repair should carry the original user request, relevant source evidence, the previous candidate, and specific deterministic rejection/intent issues. A repair must not merely turn an invalid request into a valid **different** request. Exhausted or unresolvable cases abstain with an explanation and no command.

### 8.3 Prioritized recovery candidates

| Priority | Cases | Proposed mechanism | Main caution |
|---|---|---|---|
| P0 | `strict-dl-boolean`, `unsupported-order` | Correct abstention schema/uncertainty, retain refusal | Do not manufacture a supported capability |
| P0 | `phaseaware-wrong-role`, `unspecified-strategy`, `pair-list` | Deterministic check of explicit constraints; abstain or re-evaluate | MPML preflight can accept the wrong intent |
| P1 | `artifact-alias`, `strategy-and-pair` | CLI/env inventory-aware repair | Must preserve original requested variables/values |
| P1 | `multi-strategy` | Validate repeated flag semantics and list order | Do not replace evaluation strategy selection with PhaseAware roles |
| P2 | Model-specific extra settings/citation failures | Minimality and grounding checks | Avoid overfitting to the frozen 20-case set |

### 8.4 Evaluation design for M4

Retain the **unchanged M3.5 single-pass fixture and runner** as the historical baseline. Make new M4 results separately identifiable by implementation SHA, model-call count, repair cap, and graph version. Compare per-case transitions (`fail→pass`, `review→pass`, `pass→fail`) and explicitly track newly introduced regressions. Report strict pass/review/fail counts, structural/preflight/intent distinctions, and end-to-end p50/p95 latency.

Because implementation decisions are now informed by the frozen 20 questions, any post-M4 gains on that set are **development-set gains**, not an unbiased independent generalization estimate. Add a separately authored, previously unseen holdout set before claiming broader reliability improvement. Avoid adjusting gold expectations after seeing model outputs just to improve scores.

## 9. Recommended decision and immediate follow-up

**Decision:** Preserve M3.5 as a completed, versioned single-pass baseline. Use **Qwen2.5-Coder 7B** as the initial M4 candidate because of its observed quality/latency balance, while retaining Gemma/Llama as comparison evidence and possible later ablations.

**Next implementation:** M4 should be a **bounded, read-only LangGraph workflow** with structural repair, authoritative MPML preflight, and explicit intent-preservation checks. Prioritize recovery of observed classes of failures rather than adding a generic unrestricted agent loop. Do not alter MPML launch semantics, run experiments, or expand to broker execution.

**Documentation/reproducibility:** retain the four raw JSON reports outside tracked source where possible; record the benchmark-generated worktree dirty flag as expected output rather than a failed data-integrity check; keep the frozen evaluation set and implementation provenance unchanged. No benchmark rerun is needed solely because of the dirty flag.

---

### Appendix A — Full-run artifact inventory

| Artifact | Scope | Outcome |
|---|---|---|
| `reports/local/generation/qwen-hybrid.json` | 20 cases, hybrid | 12 pass / 7 fail / 1 review |
| `reports/local/generation/gemma-hybrid.json` | 20 cases, hybrid | 11 pass / 8 fail / 1 review |
| `reports/local/generation/llama-hybrid.json` | 20 cases, hybrid | 6 pass / 14 fail / 0 review |
| `reports/local/generation/qwen-debug.json` | One-case diagnostic subset | 1 pass; excluded from totals |

### Appendix B — Reproduction commands

From the Argus repository root, using the pinned, clean MPML worktree and a freshly validated hybrid index:

```bash
python -m eval.generation.baseline run qwen-hybrid --model qwen2.5-coder:7b
python -m eval.generation.baseline run gemma-hybrid --model gemma4:e2b
python -m eval.generation.baseline run llama-hybrid --model llama3.1:8b

python -m eval.generation.baseline score qwen-hybrid
python -m eval.generation.baseline score gemma-hybrid
python -m eval.generation.baseline score llama-hybrid
```

Existing run IDs resume compatible partial runs; use new run IDs for independent replicates. The reports themselves, not this prose summary, are the canonical per-attempt evidence.
