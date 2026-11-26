# M4C-3 — Independent holdout paired evaluation (Qwen2.5-Coder 7B)

## Executive finding

**The frozen 12-case mechanical holdout exposes a deterministic intent-coverage bottleneck in M4 v1.** The M4 agent made zero generation calls and abstained on all 12 questions. M3 single-pass passed seven cases (six validated recipes plus one authoritative rejection), failed four and produced one abstention marked for human review. M4 has no new passes. This evaluates only the 12 machine-scoreable cases, not the other 14 independently authored manual-only questions.

## Source files and manifest parity

| Evidence | Value |
|---|---|
| M3 report SHA-256 | `19b129b0c45191b56c7969c5721e1aa4edccf5226a3edbb127cfc2ba603cd03f` |
| M4 report SHA-256 | `80df895276a8d791ea1bfc2c064c536b4e7a0c5eb7f0e15a1601f72e68e123b3` |
| Frozen fixture SHA-256 | `1e4fc365bc907e5d3aeb2af4c8e8aeeb489e1b592451e9fbbf3e9ccb4a94974e` |
| Pinned MPML SHA | `14ad36e3f70a10bb5781b88200e825a717ca402f` |
| Argus SHA | `bfbad2d37ee61bb63e926f0fca34021b8585d90a` |
| Index SHA-256 | `08d5ef289cc367251a475316f43a0f91bfb3202957d0866a72eec3e33f8d4f06` |
| Model digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |

Both reports are `complete_full`, 12/12 selected questions, from the identical fixture; 17/17 examined shared manifest fields match, including all implementation hashes. Workflow intentionally differs (single-pass vs m4-langgraph-v1). Temperature 0, seed 42, num_ctx 8192, num_predict 1100, hybrid retrieval top-5. No timeouts or missing responses are reported.

## Primary scored outcomes

| Metric | M3 single-pass | M4 agent |
|---|---:|---:|
| Pass | 7 | 0 |
| Fail | 4 | 12 |
| Review | 1 | 0 |
| Valid commands released | 6 | 0 |
| Authoritative rejection passing gold | 1 | 0 |
| Abstentions | 2 | 12 |
| Model calls | 12 | 0 |
| Repair calls | Not applicable | 0 |
| Withheld/no command | 6 | 12 |
| Generation p50 (s) | 4.676 | Not available (0 calls) |
| Wall-clock p50 (s) | 8.4168 | 1.4256 |
| Wall-clock p95 (s) | 12.6754 | 1.5205 |

**Interpretation:** M4’s shorter wall-clock latency results from short-circuiting before model generation, not faster end-to-end resolution of successful requests. No evidence of successful repair or its failure on this holdout exists because the repair loop was never entered.

## Paired case audit

| ID | Question focus | M3 scored result / observed behavior | M4 scored result / coverage |
|---|---|---|---|
| q001 | Variant C, seed 817, output path | pass: validated; recipe released | fail: early abstention (not_covered) |
| q003 | Reactive-JPY surface via CLI | pass: validated; recipe released | fail: early abstention (unresolved) |
| q005 | Two strategy selections | pass: validated; recipe released | fail: early abstention (not_covered) |
| q006 | Unknown strategy XYZ7 | review: abstained; no recipe | fail: early abstention (not_covered) |
| q007 | PhaseAware TF/MR representatives | pass: validated; recipe released | fail: early abstention (not_covered) |
| q008 | Wrong-family PhaseAware TF | pass: rejected; argv proposed but withheld | fail: early abstention (unresolved) |
| q009 | Variant D with gen2 hint | fail: abstained; no recipe | fail: early abstention (not_covered) |
| q010 | Top-3 and pair file | pass: validated; recipe released | fail: early abstention (not_covered) |
| q011 | Invalid top-zero | fail: rejected; no recipe | fail: early abstention (not_covered) |
| q013 | Debug fold diagnostics | pass: validated; recipe released | fail: early abstention (not_covered) |
| q020 | Start/end date environment | fail: rejected; no recipe | fail: early abstention (not_covered) |
| q026 | Invalid surface overriding env | fail: rejected; no recipe | fail: early abstention (unresolved) |

### M3 case-level failures and pending review

- `q006` — abstained, no command; frozen scorer labels **review** and `abstention=correct`. The explanation acknowledges missing evidence but does not explicitly mention the known unsupported registry ID. Assess rationale manually, without retroactively changing frozen scores.
- `q009` — abstained despite authoritative preflight supporting variant D + gen2. Model cited insufficient evidence; frozen score fail. The question also specifically says “from the available reference,” which does not enumerate the mapping; distinguish source-evidence caution from recipe-generation requirements.
- `q011` — explained correctly that zero is invalid, but returned a `rejected` disposition without the requested `--recommendation-top-n 0` candidate or actual preflight; structural validation failed. A partial semantic answer, not a scored pass.
- `q020` — asserted no supported CLI or environment date settings, contrary to published `MPML_START_DATE` and `MPML_END_DATE` controls; structural validation failed.
- `q026` — explained that `unknown` is not a valid surface but omitted the requested CLI/env candidate, so did not match observed `ARGPARSE`; structural validation failed.

### M4 gate behavior

- All 12 outputs have `verification=abstained`, `argv=null`, `env=null`, `command=null`, `preflight=null`, `structural_validation=not_run`, `preflight_validation=not_run`, `model_calls=0`, `repair_count=0`.
- Coverage classifications: `not_covered` for nine cases; `unresolved` for `q003`, `q008`, `q026`.
- The three `unresolved` cases say an explicit requirement is outside supported patterns; other nine state that the request is outside deterministic intent coverage. No specific missing argument or corrective instruction is supplied.
- The independent gate released no incorrect command. This is safe withholding, but cannot demonstrate discrimination between safe and unsafe requests because **all** requests were withheld.
- q006 includes an acceptable gold abstention alternative, but M4’s early abstention is scored fail despite its non-release: the scorer’s early-abstention treatment and insufficiency of the generic rationale require separate semantic adjudication. This may modestly change a human-reviewed success count, but cannot explain away the inability to fulfill the straightforward valid requests.

## What this establishes

1. The M4 design as implemented is not adequate for unseen, naturally phrased MPML launch requests under the current deterministic coverage gate, even though several are simple supported flag combinations.
2. The failure occurs **before** generative reasoning and preflight; prompting Qwen differently or increasing the repair budget will not fix this particular bottleneck unless coverage routing changes.
3. M3 achieved higher measured task completion on this holdout; its failed outputs also expose correctness and structural weaknesses. Do not equate M3’s 7 scored passes with reliable overall performance on arbitrary requests.
4. The frozen 12-case mechanical subset and the remaining 14 manually scored questions measure different capabilities; do not aggregate without a predefined rubric.
5. This is one frozen set and one deterministic model configuration, not a population-wide statistical claim.

## Recommended next sequence

1. **Archive these raw reports and the frozen M4C-3 findings without changing the fixture.** These 12 questions are now exposed development evidence; do not reuse them as a future untouched holdout.
2. **Conduct the pre-specified manual review for the 14 other questions**, preferably blinded to workflow identity, with side-by-side anonymous responses and criteria from `docs/evaluation/M4C_2B_MANUAL_ONLY_CASES.md`. These require independent response capture and cannot be inferred from the 12-case reports.
3. **Diagnose deterministic intent routing on a development branch.** Instrument feature detection/coverage flags and analyze why even `--debug`, `--strategy` x2 and date env questions were early-rejected. Keep independent gate and read-only safety controls.
4. Design M4 v2 as **bounded capability-aware routing** rather than a universal early gate: either robust parsing for supported patterns or a constrained generative proposal with post-generation independent intent/preflight validation. Avoid directly training against these 12 holdout questions and calling the result independent.
5. Measure any revised design first on new development cases and later on a separately frozen genuinely unseen set. Record candidate release correctness and completion separately.

## Boundaries

No live MPML run, broker order, model invocation or preflight re-execution was performed in this audit. Scored outcomes and timing values are read from the two uploaded run reports; conclusions about gate behavior are derived from recorded report fields.
