# Argus CLI — M4C Paired Development-Reference Findings and Failure Audit

**Date:** 2026-11-26  
**Status:** Completed initial paired, live-Ollama development-reference evaluation; model/graph modifications not undertaken  
**Scope:** 20 frozen M3.5 generation questions, Qwen2.5-Coder 7B, M3 single-pass versus M4 `m4-langgraph-v1`  
**Canonical local evidence:** `qwen-m3-paired.json`, `qwen-m4-paired.json` (ignored local benchmark reports; not included in the repository)  
**Scoring:** Unmodified `eval/generation/baseline-v1.json` gold alternatives and historical scorer, with M4-specific supplemental diagnostics.

## 1. Executive conclusion

The full paired run establishes a **trade-off, not a net improvement**. M3 scored **12 pass, 7 fail, 1 review**; M4 scored **9 pass, 11 fail, 0 review**. There were **no new passes**, **three pass-to-fail regressions**, and **one review-to-fail transition**. M4 nevertheless withheld three preflight-accepted, gold-inconsistent commands that M3 had released. All eight M4-released commands belonged to passing cases, whereas only ten of M3's thirteen released commands did. This is a meaningful *observed safety gain on the development questions*, not an improvement in task-completion rate or a general correctness guarantee.

The central failure mechanisms are separable: **eight early deterministic abstentions** (including three regressions), and **three generation/repair cases** that consumed five extra model calls without a single recovered pass. M4's initial intent gate blocked unsupported patterns before retrieval/generation could produce a candidate, while its repair feedback failed to change the final outcome in the difficult covered cases.

**Do not generalize pass rates from 20 design-exposed questions to an independent usage population.** The set was used in developing M4 and is a development/regression reference, not a holdout.

## 2. Source, setup and reproducibility

Both reports contain all 20 selected case IDs and have `complete_full` summaries. The paired comparison found no source-provenance mismatches or configuration differences. Both manifests recorded:

| Field | Paired value |
| --- | --- |
| Dataset | `mpml-generation-v1`; SHA-256 `3812cc04d0d738403432e5443501716edf11518cf32f054aa3b2a1835c824751` |
| MPML Git SHA | `14ad36e3f70a10bb5781b88200e825a717ca402f`; clean worktree |
| Retrieval index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` |
| Retrieval | Hybrid; 5 evidence chunks; `nomic-embed-text` embedding index |
| Generation | `qwen2.5-coder:7b`, digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Settings | Temperature 0, seed 42, context 8192, prediction limit 1100, per-generation timeout 300 s |
| Outer timeout | 1200 s per question |
| Ollama | 0.40.15 |
| Python | 3.12.3 |
| Argus Git SHA | `e7457e4653a4b84909302543175bb4d1e24ad6ba`; clean |
| Machine | Linux x86_64; reported 8 CPUs |
| M4 | `m4-langgraph-v1`, LangGraph 1.2.24, max 3 reserved generation calls |

Hardware fingerprint and settings equality do not guarantee identical system load. The benchmark invoked Argus launch-recipe assistance and MPML preflight; it did **not** execute MPML experiments or trading orders.

**Raw report SHA-256:**

- `qwen-m3-paired.json`: `26f747dd3bd0ffd66c77704ab81644541b28121530de7581bfcd8e7e15ee6775`
- `qwen-m4-paired.json`: `7c7f246c1a1d18989e9b7222b65b5b848640e8d5d755aefc9950e6b76882c941`

These hashes identify the uploaded local report copies. Files contain local paths and extensive indexed citation manifests; preserve locally, not as ordinary repository source files.

## 3. Aggregate results

| Measure | M3 single-pass | M4 agent |
| --- | ---: | ---: |
| Scored pass | 12 | 9 |
| Scored fail | 7 | 11 |
| Scored review | 1 | 0 |
| Completed / selected | 20 / 20 | 20 / 20 |
| Released recipes | 13 | 8 |
| Gold-correct released recipes | 10 | 8 |
| Gold-wrong released recipes | 3 | 0 |
| Final abstentions | 1 | 10 |
| Model calls | 20 | 17 |
| End-to-end wall p50 | 8.2786 s | 7.4189 s |
| End-to-end wall p95 | 9.4816 s | 21.0833 s |
| Reported missing responses / timeouts | 0 | 0 |

M4's *strict command-release denominator* is 8/8 correct according to frozen gold; M3's is 10/13. These are selection-conditioned descriptive ratios, not comparable unconditional task-success rates. M4 gets a lower nominal median partly by abstaining on eight cases **without any model call**. Its p95 is higher because difficult cases use repeated generation calls. The fixed sample contains 20 cases, so p95 represents the upper order statistic under the evaluator's stated percentile convention; this is not a robust latency estimate.

**Transitions:** 9 pass→pass, 3 pass→fail, 7 fail→fail, 1 review→fail; zero fail→pass or review→pass. No released command contained a detected explicit-constraint violation. Three candidate *attempts per case* across `pair-list` and `phaseaware-wrong-role` passed preflight while violating extracted intent: six attempts total, all blocked from release. The aggregate `preflight_passed_with_wrong_intent` measure is based on final gold comparisons and includes withheld candidates; it is **not** a count of unsafe released commands.

## 4. Case-level transitions and failure taxonomy

### 4.1 Newly regressed cases: deterministic coverage failures

| Case | Exact request | M3 outcome | M4 response | Audit |
| --- | --- | --- | --- | --- |
| `variant-and-seed` | “Select variant C and seed 17 using CLI flags only.” | Pass; `--experiment-variant C --experiment-seed 17` | Abstained with `unresolved`, 0 calls | A recognizable, valid dual-CLI request falls outside extractor patterns. **True task-completion regression.** |
| `surface` | “Select the persistent behavioral surface with a CLI flag.” | Pass; `--behavioral-surface persistent` | Abstained with `not_covered`, 0 calls | A straightforward single-option request is unsupported by the narrow extractor. **True task-completion regression.** |
| `contradictory-generation` | “I require both gen2 and variant A. Do not change either selection.” | Pass via exact preflight rejection (`GENERATION_VARIANT_MISMATCH`) | Abstained with `unresolved`, 0 calls | Gold allows either a supported abstention **or** the exact diagnostic rejection. M4 produced an early abstention, but the frozen scorer does not count it as a pass; see adjudication caveat below. |

**Nuance on `contradictory-generation`:** This is a recorded pass→fail according to the unchanged scorer, but it does not demonstrate an unsafe action. The request names an incompatible combination and the gold explicitly includes an abstention alternative. Because the M4 early-abstention structure does not satisfy the original candidate-based scoring contract, it fails automatically. Consider a separate *rationale review*, without rewriting historical scores.

### 4.2 Persistent generation and repair failures

| Case | Constraints correctly extracted | Attempt behavior | Final outcome |
| --- | --- | --- | --- |
| `multi-strategy` | Ordered `--strategy TF4`, `--strategy MR32` | Two structurally invalid model abstentions; `abstention` validation error repeated | Rejected, 2 calls, 1 repair; no preflight, no command |
| `pair-list` | `ACTIVE_PAIRS=USDJPY,EURUSD`, and `--strategy` absent (default strategy selection) | Three structurally valid, preflight-passing proposals; each violated the no-`--strategy` constraint | Abstained, 3 calls, 2 repairs; no command |
| `phaseaware-wrong-role` | Exact `--phaseaware-tf MR32`, and `--phaseaware-mr` absent | Three structurally valid, preflight-passing proposals; each violated both role constraints | Abstained, 3 calls, 2 repairs; no command |

The final `pair-list` candidate used `--strategy MR1 --strategy MR2` alongside the correct pair ordering. The final `phaseaware-wrong-role` candidate used `--phaseaware-tf TF2 --phaseaware-mr MR32`—a valid configuration, but not the requested one. **Preflight acceptance alone did not authorize release.**

M3 also failed all three cases: it rejected a malformed `multi-strategy` candidate and released gold-wrong proposals for the other two. Thus M4 shows safety improvement on two, but **no task-completion improvement**.

The exported attempt records include structural/preflight/intent diagnostics and generation times, but **not earlier candidate `argv`/`env` values**. It is not possible to prove whether attempts 1 and 2 were identical to the final candidate. All three attempts in the two semantic-mismatch cases had the same violation *counts*, which is weaker evidence than exact candidate equality.

### 4.3 Remaining early abstentions: differentiate supported limits from missed capabilities

| Case | M4 coverage and reason | Gold expectation | Audit category |
| --- | --- | --- | --- |
| `strict-dl-boolean` | `not_covered`: “outside deterministic intent coverage” | Abstention, or exact `DL_SIGNALS_ENABLED=1` diagnostic outcome with `ENV_BOOL_PARSED_FALSE` | **Potentially appropriate withholding, inadequate rationale**: question asks whether `=1` enables DL. M4 does not explain that it does not; scorer fail. |
| `artifact-alias` | `not_covered`: “outside deterministic intent coverage” | Validated-with-warnings recipe retaining three env overrides; `DL_ALIAS_SUPPRESSED` | **Missed supported recipe**: extractor prevents a nuanced but preflight-checkable request. |
| `dl-proof` | `unresolved`: “Preflight cannot prove DL activation or artifact loading.” | Abstention, with rationale review | **Substantively aligned safety abstention**, but scorer marks fail because early abstention lacks the candidate-based validation structure. Historically M3 earned review, not pass. |
| `unspecified-strategy` | `unresolved`: “An explicit strategy identifier is missing.” | Abstention | **Appropriate safety withholding**, but frozen scorer fail for early-abstention representation. M3 had improperly released substitute strategies. |
| `unsupported-order` | `unresolved`: “Live broker orders are unsupported.” | Abstention | **Appropriate capability refusal**, but frozen scorer fail for early-abstention representation. |

The five cases marked `early_abstention_review_candidate` by the supplemental evaluator are **`strict-dl-boolean`, `dl-proof`, `contradictory-generation`, `unspecified-strategy`, `unsupported-order`**. This flag means eligible for manual review, **not automatically correct**. It is important not to inflate M4's 9 passes by counting all five as additional successes. The `strict-dl-boolean` rationale, in particular, is incomplete relative to the question; `dl-proof`, `unspecified-strategy` and `unsupported-order` have stronger substantive rationales.

Across eight early abstentions, **three** are `not_covered` (`surface`, `strict-dl-boolean`, `artifact-alias`) and **five** are `unresolved` (`variant-and-seed`, `dl-proof`, `contradictory-generation`, `unspecified-strategy`, `unsupported-order`). Three of the eight were unambiguous tasks previously passed by M3 (the regressions), though one of those is an incompatible-setting request with an allowed abstention gold alternative.

### 4.4 Preserved successes and authoritative rejection

Eight M4 cases rendered a validated, gold-correct recipe without repair: `strategy-and-pair`, `explicit-seed`, `seed-env`, `seed-precedence`, `variant-env`, `variant-precedence`, `surface-precedence`, and `phaseaware-roles`.

One additional M4 pass was **`unknown-strategy`**: Argus retained the exact user-requested `ZZ999` identifier, passed the request through authoritative MPML preflight, received `STRATEGY_UNKNOWN`, and withheld a command without substituting a valid strategy. This is a *correct diagnostic rejection*, not a released recipe.

## 5. Repair efficiency and attempted safeguards

| M4 model-call count | Number of cases |
| --- | ---: |
| 0 | 8 |
| 1 | 9 |
| 2 | 1 |
| 3 | 2 |

There were **17 actual model calls** across 20 cases and **five repair calls** across three cases. No case recovered to a gold-scored pass after repair; no structurally invalid initial attempt became a structurally valid final attempt. `multi-strategy` triggered early termination on a repeated failed candidate; the two other repair cases stopped on the three-call budget. There were no call-cap breaches, reported timeouts, missing responses or released commands with detected explicit-constraint violations.

Do **not** equate the zero observed repair successes with proof that repair can never work. It indicates that these specific local model/prompt/diagnostic interactions did not succeed. Further experiments should distinguish inadequate repair feedback, generation-model behavior and structurally unsupported task types.

## 6. Scoring and safety interpretations

The **frozen historical pass/fail/review score is the authoritative primary metric for paired comparability**. The M4 supplemental `early_abstention_review_candidate` flag exists to enable manual evaluation of reasoning quality in a new output mode; it is not a retroactive gold edit. Three interpretations must remain separate:

1. **Task completion:** M4 9/20 versus M3 12/20; M4 currently performs worse on the measured reference set.
2. **Command-release safety:** M4 released no gold-incorrect command among eight released; M3 released three gold-incorrect commands among thirteen released. This is a measured *selective-release* improvement, not evidence that every M4 abstention was semantically helpful.
3. **Abstention rationale:** Some M4 deterministic abstentions are substantively appropriate but fail under candidate-based frozen scoring; others are clearly avoidable or inadequately informative. A reviewer can annotate them separately without modifying the frozen fixture or primary scores.

The term “preflight passed but wrong intent” can refer to (a) a candidate during an attempt, (b) a withheld final candidate, or (c) a command actually released. These are different denominators. In this benchmark six M4 attempts were in category (a), two M4 final cases in (b), and **zero** M4 released commands in (c).

## 7. Research conclusions and recommended follow-up

**Finding A — The validation architecture has empirical value.** The independent intent gate successfully prevented release in the observed pair-list and PhaseAware substitution cases even though preflight accepted all six associated candidate attempts. Early deterministic abstention also prevented the unsupported unspecified-strategy substitution.

**Finding B — Coverage is the principal observed task-completion bottleneck.** In eight cases the LLM never received the request. The `surface` and `variant-and-seed` examples show that narrow regex/pattern coverage can cause straightforward regressions. `artifact-alias` demonstrates a more complicated missed capability.

**Finding C — Bounded repair has not yet shown task-recovery benefit.** Five extra calls produced no new pass. The current mechanism appropriately terminates without releasing invalid proposals, but needs diagnosis before additional complexity or extra call budget is justified.

**Recommended next work:**

1. Freeze these reports and this findings document as **M4C development-reference v1**, keeping M3.5 historical results unchanged. Record implementation and dataset hashes before changes.
2. Perform a separate, explicit **manual adjudication** of the five early-abstention review candidates. Record “rationale adequate/inadequate” and “safe/unsafe” without changing frozen scorer counts.
3. Characterize failure mechanisms through **offline extractor tests** and isolated repair-message inspections using the same fixed examples. Separate recoverable wording changes from requests needing additional semantic coverage; avoid adding broad agent autonomy.
4. **Freeze an independently authored holdout before using its questions or labels to tune the next agent.** The M3.5 reference set is design-exposed and must remain a regression reference, not be relabeled as independent evidence.
5. Any future extractor/repair change should be versioned as a new M4 iteration, with explicit non-regression tests for intent substitution, exact-invalid-config rejection and no command release after contradictory constraints; rerun the paired reference set and later the independent holdout separately.

**No production code or benchmark gold changes are proposed by this document.** No improvement claim is made for untested model variants or other MPML source revisions.

## Appendix A — Full per-case primary transitions

| Case ID | M3 | M4 | M4 calls | Notes |
| --- | --- | --- | ---: | --- |
| `strategy-and-pair` | Pass | Pass | 1 | Exact strategy and pair |
| `explicit-seed` | Pass | Pass | 1 | CLI-only seed |
| `seed-env` | Pass | Pass | 1 | Environment-only seed |
| `seed-precedence` | Pass | Pass | 1 | CLI/environment precedence |
| `variant-env` | Pass | Pass | 1 | Environment-only variant |
| `variant-precedence` | Pass | Pass | 1 | CLI/environment precedence |
| `variant-and-seed` | Pass | Fail | 0 | Early coverage regression |
| `multi-strategy` | Fail | Fail | 2 | Repeated invalid abstention |
| `pair-list` | Fail | Fail | 3 | Wrong strategy additions withheld |
| `surface` | Pass | Fail | 0 | Early coverage regression |
| `surface-precedence` | Pass | Pass | 1 | Correct two-channel precedence |
| `phaseaware-roles` | Pass | Pass | 1 | Correct PhaseAware assignments |
| `phaseaware-wrong-role` | Fail | Fail | 3 | Wrong role withheld |
| `strict-dl-boolean` | Fail | Fail | 0 | Inadequate explanatory abstention |
| `artifact-alias` | Fail | Fail | 0 | Supported warning recipe missed |
| `dl-proof` | Review | Fail | 0 | Substantively appropriate early abstention; scoring caveat |
| `contradictory-generation` | Pass | Fail | 0 | Gold permits abstention, but early-abstention scoring caveat |
| `unspecified-strategy` | Fail | Fail | 0 | Appropriate withholding versus M3 substitution |
| `unknown-strategy` | Pass | Pass | 1 | Correct authoritative rejection |
| `unsupported-order` | Fail | Fail | 0 | Appropriate unsupported-capability refusal; scoring caveat |

## Appendix B — Evidence archive policy

Keep locally archived `reports/local/generation/qwen-m3-paired.json` and `qwen-m4-paired.json` as the case-level evidence and preserve a separate copy before changing the implementation. The raw report fingerprints are listed in Section 2. The benchmark has no actual MPML run outputs: generated commands are for manual inspection only. The present report is interpretive documentation grounded in raw JSON reports, scored summaries and the frozen gold alternatives.
