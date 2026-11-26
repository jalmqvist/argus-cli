# M4v2-3C — Paired maintainer-local development findings (2026-11-26)

**Status:** Completed paired descriptive analysis and documentation. M4v2-3C engineering and first local regression are a good pause-point. Human adjudication of gold alternatives, answer factuality/usefulness and unnecessary withholding remains **unresolved**. This is a repeat of developer-authored development cases, **not** an independent holdout.

## Provenance and comparability

This document compares the original M4v2-3B local run with the maintainer's full M4v2-3C rerun, using the original 14 case IDs and unchanged gold/fixture bytes. The separately supplied manifests and scored results are the source of the measurements below; no private candidate artifacts are included in this repository.

| Property | M4v2-3B baseline | M4v2-3C rerun |
| --- | --- | --- |
| Argus revision (clean) | `f1c0271bdb764007b24a308775374097be1aa76f` | `74b5f8c7d54cb368d1c49c3aeba677bc92837417` |
| Fixture | `m4v2-first-attempt-development-v1` | Same, 14/14 complete |
| Fixture SHA-256 | `62796157b87b8ddf2ebe3fb2b7a5e9b59e0779ceec6ea8f5a1949709320f3f28` | Same |
| MPML source | `14ad36e3f70a10bb5781b88200e825a717ca402f` | Same, clean |
| MPML spec SHA-256 | `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` | Same |
| Index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` | Same |
| Model and digest | `qwen2.5-coder:7b`, `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` | Same |
| Generation settings | Temperature 0; seed 42; context 8,192; output cap 1,100; timeout 180 s | Same |
| Retrieval | Lexical; up to eight excerpts | Lexical plus verified spec prioritization; same eight-excerpt cap |
| Hardware | Maintainer's GTX 1070 (8 GB) | Same |

Changes in 3C include routing, retrieval prioritization, a narrow typed-seed evidence rule, a short v2-only prompt clarification, and trusted failure explanations. Because these changed together, the results **do not identify the causal contribution of each change**.

## Paired outcomes

| Measure | Baseline 3B | Rerun 3C | Difference |
| --- | ---: | ---: | ---: |
| Completed cases | 14 | 14 | 0 |
| Supported configuration cases | 7 | 7 | 0 |
| Supported configuration requests reaching generation | 6 | 7 | +1 |
| First-attempt candidate graded correct | 3 | 5 | +2 |
| Candidate graded incorrect | 4 | 2 | -2 |
| Exact invalid request preserved and rejected structurally | 1 | 2 | +1 |
| Needs manual review / no candidate | 1 | 0 | -1 |
| Candidate not applicable | 5 | 5 | 0 |
| Generation attempts | 8 | 9 | +1 |
| Accepted read-only preflights | 5 | 6 | +1 |
| Preflight not run | 9 | 8 | -1 |
| Publicly released recipes | 0 | 0 | 0 |
| Generation median (attempts only) | 7.113 s (n=8) | 6.804 s (n=9) | -0.309 s |
| Generation nearest-rank p95 | 9.135 s | 9.153 s | +0.018 s |
| End-to-end median (all 14) | 7.934 s | 8.100 s | +0.166 s |
| End-to-end nearest-rank p95 | 12.260 s | 12.266 s | +0.006 s |

**Denominators and meaning:** The seven supported configuration requests are distinct from the two invalid-exact requests, two factual questions, one ambiguous reference and two unsupported execution/action requests. The five `not_applicable` grades do not measure model recipe accuracy. All seven supported configuration requests now reached generation; five were graded exact-correct and two incorrect using the fixed development gold. The invalid-exact cases measure preservation of the specified invalid request, **not** valid recipe creation. Counts are outcomes in this small development fixture, not population success rates.

The marginal difference in overall median reflects a changed set of generated cases as well as timing variation. No observed inference timeouts or additional model calls occurred in the reported completed cases. Generation latency is broadly similar; do not conclude that 3C makes inference faster.

### Case-by-case changes

| Case | 3B | 3C | Observation |
| --- | --- | --- | --- |
| `seed-default` | Not applicable | Not applicable | Deterministic grounded default/precedence answer retained |
| `variant-priority` | Not applicable | Not applicable | Deterministic grounded precedence answer retained |
| `strategy-only` | No proposal; needs review | **Correct**, preflight accepted | Self-contained request now reaches one generation attempt |
| `strategy-seed` | Correct; seed evidence unsupported | **Correct**, seed record retrieved/cited/supported | Both retrieval and typed evidence-policy gaps addressed for this case |
| `variant-seed` | Correct; seed evidence unsupported | **Correct**, seed record retrieved/cited/supported | Same seed improvement; CLI winning channels confirmed |
| `env-variant-seed` | Incorrect; structure failed | **Incorrect**; structure and preflight pass | Still adds two unrequested CLI settings to environment-only request |
| `strategies-in-order` | Correct | **Correct** | Ordered strategy selection preserved |
| `pair-filter` | Incorrect | **Incorrect** | `ACTIVE_PAIRS` remains omitted; two structural issues, no preflight |
| `phaseaware-roles` | Incorrect; extra `--strategy` | **Correct**; preflight accepted | Both requested role records retrieved/cited/supported; unwanted extra removed |
| `invalid-variant` | Exact invalid request | Exact invalid request | Invalid `Z` preserved and rejected structurally |
| `invalid-role` | Incorrect role substitution; accepted preflight | **Exact invalid request**, no preflight | Invalid requested trend-following role preserved rather than silently shifted to mean-reversion |
| `ambiguous-pair` | No proposal | No proposal | Clarification now specifically asks which currency pair(s) |
| `execute-experiment` | Not applicable | Not applicable | Execution correctly declined before inference |
| `broker-action` | Not applicable | Not applicable | Broker action correctly declined before inference |

The `invalid-role` comparison is particularly informative. The old preflight-accepted proposal was semantically wrong; the new proposal preserved the requested invalid role and was blocked before preflight. Preflight success is not a measure of preserved user intent.

## Independent evidence versus model proposal correctness

**Seed cases:** The `strategy-seed` and `variant-seed` records now show the `--experiment-seed` spec entry present in the pinned index, retrieved, and cited, with `value_supported_in_index`, `value_supported_in_retrieval` and `value_supported_in_citations` all true. The workflow reports `typed_seed_support=true`, `setting_evidence_valid=true`, and an accepted preflight. This verifies narrow documented integer-parser support for the candidate value; it **does not** independently verify complete user intent, all effective configuration or downstream runtime numeric bounds.

**PhaseAware roles:** The correct `phaseaware-roles` candidate cites both `--phaseaware-tf` and `--phaseaware-mr` records; both pass the structured exact-value support audit. Preflight accepted, but full intent and aggregate effective configuration remain unresolved.

**Environment-only failure:** The `env-variant-seed` candidate is still scored incorrect because two unrequested CLI settings accompany the specified environment-only overrides. All four relevant setting records were retrieved. The `EXPERIMENT_SEED` environment record was **not cited**, despite being retrieved; `EXPERIMENT_VARIANT` was cited but not attested by C1's current exact-value policy. Structure and preflight acceptance do not repair the channel mismatch. The improved public explanation correctly identifies the CLI/environment conflict without releasing a candidate.

**Pair-filter failure:** `pair-filter` remains incorrect: the scorer reports `ACTIVE_PAIRS` missing, two candidate structural issues, and no preflight. Its evidence audit contains an empty `settings` mapping because no recognized setting was extracted from the candidate. **This mapping does not prove that the correct `ACTIVE_PAIRS` record was absent from the model's retrieval context.** Follow-up diagnosis should inspect the trusted retrieval trace or perform a targeted deterministic retrieval audit; the private candidate need not be published.

All proposal cases still have `material_intent=unresolved` and `effective_configuration=unresolved`. None of the new typed support or better retrieval findings implies authorization to release a manual command.

## Preliminary response usefulness (not adjudicated grades)

The 3C public responses now distinguish an explicit environment-only channel conflict, the omitted `ACTIVE_PAIRS` override, invalid experiment variant, invalid PhaseAware trend-following role, and a missing pair reference. This is a meaningful improvement over generic structure errors. The two deterministic informational answers remain grounded and readable.

Nevertheless, even correct proposal cases mostly explain checks, cited setting categories, source precedence, and why the recipe is withheld; they do not establish full task satisfaction. `env-variant-seed` describes its channel conflict despite preflight acceptance, which is an important truthful qualification. `pair-filter` offers a relevant diagnostic but not a working setting. All human factual correctness/usefulness/unnecessary-withholding fields in the uploaded results remain **unresolved**. These observations must not be rebranded as final human grades or a demonstrated false-withholding improvement.

## Decisions and pause-point

**M4v2-3C is complete as a targeted development intervention.** Relative to the recorded baseline, five of seven supported configuration requests now receive first-attempt exact-correct candidates, versus three previously, and both invalid-exact requests are preserved rather than substituted. Hardware timings remain practical on the GTX 1070. These are **paired development** observations under a model/prompt/retrieval implementation change, not independent efficacy or safety estimates.

Continue to preserve:

- Existing `qwen2.5-coder:7b`, eight-excerpt budget and at most one generation attempt; no repair or extra verifier model yet.
- Read-only metadata/preflight only; no experiments, orders or private market data in CI.
- Public `command=null` and `settings=null` until **all** independent material-intent, effective-configuration, evidence, provenance and preflight gates are available and pass.
- Original fixture and both raw local result sets unchanged; do not alter the development gold to raise apparent accuracy.

### Recommended restart order

1. **Small targeted diagnosis:** inspect the environment-only channel mismatch and `ACTIVE_PAIRS` omission, distinguishing prompt candidate behavior, setting retrieval/citation, exact-value evidence and intent checking. Do not patch by silently substituting settings.
2. **Human review:** independently check the development gold where necessary and score factual correctness, practical answer usefulness and unnecessary withholding; preserve unresolved cases rather than force numeric grades.
3. **Decision checkpoint:** consider a very small follow-up only if the two failure mechanisms are well characterized. Re-run any changes against the fixed fixture as development regression, never relabel as holdout.
4. **M4v2-4 later:** commission a separately authored, frozen independent evaluation before any promotion/generalization claims. A broader material-intent and complete effective-configuration study remains a separate release-enabling workstream, not a prerequisite for limited explanations.

**No current evidence requires a larger model, additional automatic generation/repair passes or an accelerated recipe-release effort.**

References: [3B baseline findings](FIRST_ATTEMPT_FINDINGS_3B.md), [3C implementation/regression procedure](EVIDENCE_REGRESSION_3C.md), [M4v2-3A harness](FIRST_ATTEMPT_DEVELOPMENT.md), [roadmap](../../PLAN.md).
