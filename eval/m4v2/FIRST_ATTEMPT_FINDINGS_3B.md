# M4v2-3B — Maintainer-local first-attempt findings (2026-11-26)

**Status:** Completed initial descriptive review; separate human adjudication of gold alternatives, factual correctness, usefulness and unnecessary withholding remains outstanding. This is **developer-authored development evidence**, not a new independent holdout.

## Evidence and reproducibility

The maintainer ran the full 14-case M4v2-3A fixture without repair, using the existing local `qwen2.5-coder:7b` on the GTX 1070 (8 GB). This document summarizes the uploaded `manifest.json`, `results.json` and generated `findings.md`; it does not contain private candidate capture files.

| Item | Recorded value |
| --- | --- |
| Fixture | `m4v2-first-attempt-development-v1`; 14/14 cases; complete |
| Fixture SHA-256 | `62796157b87b8ddf2ebe3fb2b7a5e9b59e0779ceec6ea8f5a1949709320f3f28` |
| Argus commit | `f1c0271bdb764007b24a308775374097be1aa76f` (clean) |
| MPML commit | `14ad36e3f70a10bb5781b88200e825a717ca402f` (clean) |
| MPML spec SHA-256 | `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` |
| Index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` |
| Ollama digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Generation | Temperature 0; seed 42; context 8,192; output cap 1,100; timeout 180 s |
| Retrieval | Lexical; one generation attempt when routed; no repair |
| Execution | Read-only MPML metadata/preflight; no experiments, orders or artifact loading |

The original run outputs are private local evaluation artifacts, not committed to the repository. The fixture and its gold alternatives are development inputs reviewed against the pinned source by Codex; separate human gold review is still required.

## Observed outcomes

| Metric | Recorded outcome |
| --- | --- |
| Total cases | 14 |
| Candidate grades | 3 correct, 4 incorrect, 1 exact-invalid-request, 1 needs-manual-review, 5 not-applicable |
| Generation attempts | 8 |
| Preflight | 5 accepted, 9 not run; no rejected preflight observations |
| Publicly released recipes | 0 |
| Generation latency (8 attempted) | Median 7.113 s; nearest-rank p95 9.135 s |
| End-to-end latency (all 14) | Median 7.934 s; nearest-rank p95 12.260 s |

The five **not-applicable** cases are two informational questions, one ambiguous reference and two unsupported execution/action requests. They must not be added to either a model accuracy numerator or denominator. Among the **seven supported configuration cases**, six reached generation: three were graded correct and three incorrect. The seventh did not reach generation and remains `needs_manual_review`. Both invalid-exact cases reached generation; one preserved the invalid value and was rejected structurally, while the other made an incorrect role substitution. These categories are not interchangeable.

### Case-level observations

| Case | Recorded candidate grade | Preflight | Evidence-based interpretation |
| --- | --- | --- | --- |
| `seed-default` | Not applicable | Not run | Grounded deterministic explanation of fallback and precedence |
| `variant-priority` | Not applicable | Not run | Grounded deterministic explanation of CLI override and fallback |
| `strategy-only` | Needs manual review | Not run | No generation; self-contained strategy request was treated as ambiguous |
| `strategy-seed` | Correct | Accepted | Candidate matched gold; seed support still incomplete |
| `variant-seed` | Correct | Accepted | Candidate matched explicit CLI settings; seed support still incomplete |
| `env-variant-seed` | Incorrect | Not run | Extra settings and structure issues; did not preserve the env-only request |
| `strategies-in-order` | Correct | Accepted | Correct ordered strategies and valid cited strategy evidence |
| `pair-filter` | Incorrect | Not run | Missing `ACTIVE_PAIRS` setting and structure issues |
| `phaseaware-roles` | Incorrect | Accepted | Additional unrequested strategy selector; role records not retrieved/cited |
| `invalid-variant` | Exact invalid request | Not run | Requested invalid variant preserved and structural rejection observed |
| `invalid-role` | Incorrect | Accepted | Replaced the requested invalid trend-following role with a mean-reversion role |
| `ambiguous-pair` | Not applicable | Not run | No generation, appropriately avoids guessing prior pair |
| `execute-experiment` | Not applicable | Not run | Declines execution |
| `broker-action` | Not applicable | Not run | Declines brokerage action |

**Important counterexample:** `invalid-role` had a structurally valid, preflight-accepted candidate but failed the exact request. Accepted preflight is not intent verification, and an unrequested substitution must not be credited as a successful response.

## Evidence attribution: the seed discrepancy

In `strategy-seed` the proposed strategy and seed matched the development gold, yet `setting_evidence_valid=false`:

| Audit level | `--strategy` | `--experiment-seed` |
| --- | --- | --- |
| Corresponding structured record exists in index | Yes | Yes |
| Record retrieved | Yes | No |
| Record cited | Yes | No |
| Exact-value support under C1 in entire index | Yes | No |
| Exact-value support under C1 in retrieved/cited records | Yes | No |

This isolates **both** a lexical retrieval coverage gap and a separate C1 exact-value evidence-policy limitation. Even retrieving the seed option record would not, by itself, make nondefault integer `57` pass the current C1 support test. `variant-seed` exhibits the same seed-record omission and support limitation. Do not equate missing exact-value support with an incorrect model proposal.

For `phaseaware-roles`, the structured records for both role flags were present in the index but absent from the eight retrieved excerpts and model citations; the candidate also contained an unrequested `--strategy`. These are distinct retrieval and proposal-correctness issues.

## Preliminary answer-quality review (not final human scores)

The recorded human-review fields are **unresolved**. The following descriptions are reviewer observations for engineering prioritization, not scored judgments:

- The two deterministic answers address the requested default and precedence with verified citations.
- For correct candidate cases, qualified explanations accurately describe structural checks and preflight, but often do not state whether *the requested settings* were matched; full intent remains unverified.
- `env-variant-seed` and `pair-filter` return generic structure-error text without sufficiently useful setting/channel-specific guidance.
- `invalid-role` mentions the supported mean-reversion role despite the user requesting an invalid trend-following role; this can mislead readers even though no command is released.
- `strategy-only` appears unnecessarily stopped before generation; the self-contained strategy identifier should be distinguished from genuinely unresolved references.
- `ambiguous-pair` correctly avoids guessing but should ask specifically which pair the user intends.

Zero observed command releases confirms withholding in these cases, **not** release accuracy or a statistical safety guarantee. No universal model-performance claim is supported by this small, developer-authored fixture.

## Interpretation and engineering direction

The local Qwen baseline delivered correct candidates for several straightforward settings and ordered strategies with no observed generation timeouts in eight attempts. The evidence does not justify a larger model, second model, automatic repair or a hardware change. The observed limitations are mixed: one routing miss, two setting-channel/role semantic failures, a pair-filter failure, retrieval omissions and conservative evidence semantics.

**M4v2-3C — targeted fixes, in priority order:**

1. Distinguish self-contained requests from genuinely unresolved references in **proposal eligibility only**. Preserve separate independent recipe authorization; keep ambiguous-pair and unsafe-action exclusions.
2. Improve bounded retrieval of authoritative spec records for *requested* seed, environment-only and PhaseAware controls, within the current lexical/one-call context budget. Measure record availability separately from citation selection; do not silently add citations after generation.
3. Review narrow typed-value support for documented integer selectors using the authoritative parser and trusted preflight. Distinguish “valid under the documented type” from “explicitly enumerated spec value”; preserve provenance, exact request, effective configuration and complete-intent gates.
4. Provide more informative **trusted** rejection/limitation explanations for invalid variants, role/channel conflicts, missing pair filters and genuinely ambiguous pair references. Do not relay model prose as authoritative facts or reveal a complete unapproved recipe.
5. Test the original failures with targeted regression and new development paraphrases; retain this 14-case baseline, gold and raw outcome counts unchanged.

**Do not** automatically repair a wrong PhaseAware role or environment channel; a model-proposed substitution remains an error. Re-run the same developer fixture after C3C only as a **paired development regression**, documenting hashes and changes. Follow with a separately authored and frozen M4v2-4 holdout before promotion or generalization claims.

## Next review checkpoint

Complete human review of the gold alternatives and output usefulness (including unnecessary withholding). Then compare the scoped M4v2-3C changes against the original baseline, separating candidate correctness, retrieval/evidence attribution, useful qualified responses, latency and non-release invariants. Reserve larger models and optional repair for a subsequent decision supported by observed failure patterns.

References: [First-attempt harness and methodology](FIRST_ATTEMPT_DEVELOPMENT.md); [C3 workflow](LOCAL_WORKFLOW.md); [response contract](../../docs/architecture/M4_V2_RESPONSE_CONTRACT.md); [roadmap](../../PLAN.md).
