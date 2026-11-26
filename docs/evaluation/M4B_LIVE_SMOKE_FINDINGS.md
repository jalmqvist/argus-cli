# Argus CLI — M4B Live Integration Smoke-Test Findings

**Date:** 2026-11-26  
**Status:** Completed initial local smoke test; evidence for M4C planning  
**Scope:** Opt-in `argus ask --agent` against a pinned MPML worktree and local Ollama; read-only launch-recipe assistance  
**Implementation:** M4B-2, merged PR [#12](https://github.com/jalmqvist/argus-cli/pull/12)  
**Primary evidence:** `argus-m4-smoke-01.json`, `argus-m4-smoke-02.json`, `argus-m4-smoke-03.json` (local JSON reports; not committed here)

## 1. Executive summary

Three manually selected, real-Ollama smoke tests exercised the opt-in M4 LangGraph path after M4B-2 integration. **One request produced a validated manual recipe on the first attempt; two requests did not produce usable recipes.** All three terminated within the configured maximum of one initial generation call plus two repairs, and no rejected or intent-inconsistent command was released.

| Case | Request focus | Final disposition | Generation calls | Repairs | Wall time | Manual command |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 01 | Evaluate MR32 on USDJPY | `validated` | 1 | 0 | 22.23 s | Released |
| 02 | Evaluate TF4 then MR32 in the same launch | `rejected` | 2 | 1 | 10.19 s | Withheld |
| 03 | Insist on MR32 as PhaseAware trend-following representative | `abstained` | 3 | 2 | 22.42 s | Withheld |

**Principal finding:** The first live test demonstrated the end-to-end integration, while the third demonstrated the independent intent gate detecting a valid-but-unrequested PhaseAware substitution despite successful MPML preflight. **Neither observed repair sequence recovered to a correct final recipe or well-formed requested rejection.** These results support integration and safety observations, not a measured improvement in overall reliability.

## 2. Environment and provenance

All three reports recorded the same configurations and fingerprints:

| Item | Recorded value |
| --- | --- |
| Workflow | `m4-langgraph-v1` |
| Generation model | `qwen2.5-coder:7b` |
| Model digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Retrieval | Hybrid, top 5 |
| Temperature / seed | `0.0` / `42` |
| Context / generation limit | `8192` / `1100` tokens |
| Per-generation timeout setting | `300` seconds |
| MPML source | Dedicated `market-phase-ml-argus-benchmark` worktree |
| MPML Git SHA | `14ad36e3f70a10bb5781b88200e825a717ca402f` |
| MPML source dirty | `false` |
| MPML spec SHA-256 | `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` |
| Retrieval index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` |

These match the pinned MPML specification and retrieval index used in the M3.5 evaluation. The model digest is also consistent across the three smoke reports. The reports do **not** by themselves establish that all other hardware, process-environment or implementation conditions match the historical M3.5 full benchmark. The local worktree path is omitted here for portability; the reports retain the exact original path.

The smoke procedure used existing local Ollama, source verification, retrieval and the authoritative MPML preflight interface. No generated shell command was executed by Argus, and no MPML research experiment or broker action was run. A successful preflight establishes launch-surface validity only, not experiment completion, DL activation, artifact loading or full semantic intent correctness.

## 3. Case findings

### 3.1 Smoke 01 — MR32 on USDJPY: end-to-end success

**Question:** `How do I evaluate MR32 on USDJPY?`

The first candidate supplied exactly:

```json
{"argv": ["--strategy", "MR32"], "env": {"ACTIVE_PAIRS": "USDJPY"}}
```

The graph extracted two source-spanned constraints (strategy `MR32` and pair `USDJPY`), and both were satisfied. Structural and citation validation passed. The two cited entries were `mpml/spec.py / arguments / --strategy` and `mpml/spec.py / env / ACTIVE_PAIRS`. MPML preflight returned exit code `0`, `schema_version: 1` and no issues or warnings. The final disposition was `validated`, with a shell-escaped command marked `manual_execution_only`.

- **Generation:** 16.79 s; **total wall time:** 22.23 s.
- **Calls:** 1 reserved / 1 made; **repairs:** 0.
- **Observation:** The normal live graph path can produce a correctly constrained, cited, preflight-accepted manual recipe without repair.

This single successful case does not measure repair effectiveness or establish broader intent accuracy.

### 3.2 Smoke 02 — ordered repeated strategies: invalid abstention, no recovery

**Question:** `Evaluate TF4 followed by MR32 in the same launch, in that order`

The deterministic extractor correctly identified an ordered, exact `--strategy` constraint with values `TF4`, then `MR32`. However, both generation attempts failed the abstention contract, with validation code `abstention`:

> For abstention, return empty argv and env and a nonempty uncertainty reason.

The first invalid candidate triggered a repair. The second failed the same structural rule; the graph reported `Repeated failed candidate.` and stopped without using the third available call. **Preflight was not invoked for either attempt**, and no command was rendered.

| Attempt | Generation time | Structural result | Preflight | Disposition detail |
| --- | ---: | --- | --- | --- |
| 1 | 4.32 s | Failed: `abstention` | Not run | Repair attempted |
| 2 | 4.43 s | Failed: `abstention` | Not run | Repeated failed candidate; stop |

**Final:** `rejected`, 2 calls, 1 repair, 10.19 s total, `command: null`.

**Interpretation:** Constraint extraction succeeded, but generation and repair failed to produce either the requested repeated strategy selection or a valid abstention. This resembles the `multi-strategy` failure category from M3.5. The repeated-candidate guard avoided another unproductive call in this instance. This is a task-completion failure with safe withholding of output.

### 3.3 Smoke 03 — invalid PhaseAware role: preflight passes, intent gate blocks

**Question:** `Use MR32 as the PhaseAware trend-following representative. Do not substitute another strategy.`

The extractor recorded two requirements: `--phaseaware-tf` must be exactly `MR32`, and `--phaseaware-mr` must be absent. The final candidate shown in the report was:

```json
{"argv": ["--phaseaware-tf", "TF2", "--phaseaware-mr", "MR32"], "env": {}}
```

This is not the requested role assignment. **Every attempt passed structural validation and MPML preflight** (`exit_code: 0`, no issues), yet every attempt failed both extracted intent constraints. The graph therefore withheld the command, performed two repair attempts and stopped on budget exhaustion.

| Attempt | Generation time | Structural result | MPML preflight | Intent result |
| --- | ---: | --- | --- | --- |
| 1 | 4.56 s | Passed | Validated | Both constraints violated |
| 2 | 5.45 s | Passed | Validated | Both constraints violated |
| 3 | 2.83 s | Passed | Validated | Both constraints violated; budget exhausted |

**Final:** `abstained`, 3 calls, 2 repairs, 22.42 s total, `command: null`.

**Interpretation:** This is the strongest safety observation in the smoke set. It reproduces the *category* of the M3.5 `phaseaware-wrong-role` problem: a preflight-accepted configuration can still contradict an explicit instruction. M4's separate intent gate detected and blocked it. The repairs did not achieve faithful representation followed by authoritative rejection, nor a satisfactory abstention from the model.

**Evidence boundary:** The smoke report records the final candidate and per-attempt constraint outcomes, but not the complete `argv`/`env` of the first two attempts. It therefore does **not** establish that the same candidate was repeated three times; only that all three violated the same two constraints.

## 4. Cross-case observations

### Established by these smoke tests

1. The opt-in workflow can run against the pinned local MPML worktree, retrieve grounded evidence, generate a candidate, call real MPML preflight and render a manual command after the required gates (case 01).
2. Constraint extraction correctly captured the explicit strategy/pair request, repeated-strategy order and invalid PhaseAware role demands in these particular wordings.
3. Structural rejection prevented invalid abstention candidates from reaching preflight (case 02).
4. Clean preflight alone did not authorize release when the exact extracted role requirements were violated (case 03).
5. The graph respected the three-call cap and its repeated-failure early termination behavior in the observed paths.
6. No command was released for cases 02 or 03.

### Not established

- A general improvement in answer correctness over M3.5; there is no controlled paired full-set comparison yet.
- Successful repair: both smoke cases invoking repair ended without an accepted requested recipe.
- General natural-language intent coverage: the deterministic extractor intentionally supports narrow patterns and can abstain on otherwise reasonable requests.
- Causal explanation for model failures: neither prompting nor retrieval nor model behavior was experimentally isolated.
- Runtime experiment success, DL activation or trading outcomes: none were exercised.
- General latency or repair-cost distributions: three purposively selected cases are insufficient.

## 5. Evaluation and observability implications for M4C

These initial observations suggest measuring **correct task completion and safety separately**. Replacing a wrong-but-preflight-valid recipe with an abstention is a meaningful safety change, but should not automatically count as a successful answer. Likewise, an invalid abstention blocked by structural validation is not a successful abstention.

For paired M3/M4 evaluation, retain the frozen 20-case M3.5 fixture as a **development/regression reference**, not an independent holdout. Track per-case `pass/fail/review`, valid recipe coverage, correct versus unnecessary abstentions, preflight-passed-but-wrong-intent cases, changes in candidate validity after repair, reserved calls, retries, terminal reasons and wall time. Report `fail → pass`, `pass → fail` and changes to abstention explicitly. An independently authored, separately frozen holdout remains required for broader M4C assessment.

The smoke reports expose an observability limitation: they contain final `argv`/`env` and attempt-level statuses, but not each earlier proposal's argument/environment summary. Before drawing strong conclusions about repair dynamics, consider a **bounded, sanitized per-attempt candidate summary** (or hashes plus tightly scoped field comparisons), without logging untrusted full output, sensitive environment values or arbitrary model text. No runtime change is requested by this document.

The PhaseAware case also motivates examining whether multiple repairs of the same *semantic* constraint violation offer useful coverage gains relative to their latency. The current three-call policy should not be changed solely on these three observations.

## 6. Decision and next steps

**Decision:** Record M4B live integration as demonstrated on a straightforward example, with the independent intent gate and fail-closed routing behaving as designed in the two challenging smoke cases. Do **not** characterize the agent as empirically more accurate or its repair as effective yet.

Next, run the opt-in M4 workflow across the existing frozen 20 questions with the original pinned MPML source/index and comparable model settings. Preserve the historical M3.5 JSON reports and scoring expectations. Inspect per-case transitions and abstention coverage, then use those findings to prioritize narrowly targeted improvements. Prepare a genuinely independent holdout for M4C rather than optimizing against the original 20 and treating it as unseen evidence.

## Appendix — Source report inventory

| Local evidence file | Question | Disposition |
| --- | --- | --- |
| `argus-m4-smoke-01.json` | MR32 on USDJPY | `validated` |
| `argus-m4-smoke-02.json` | Ordered TF4 then MR32 | `rejected` |
| `argus-m4-smoke-03.json` | MR32 demanded as PhaseAware TF representative | `abstained` |

The local JSON reports are the canonical evidence for exact diagnostics, provenance, citations and timings. This document is a descriptive summary; the reports should be retained locally and excluded from Git if they contain machine-specific paths or other local metadata.
