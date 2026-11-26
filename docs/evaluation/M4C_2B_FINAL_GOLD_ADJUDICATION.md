# M4C-2B final gold adjudication

**Freeze blocked pending receipt of the recovered manifest.** The maintainer
supplied the recovered authoring ZIP and reported that its three members had
been independently checked against the sidecar. This workspace has the ZIP.
The original sidecar and distribution record are needed for local verification
before registration.

All **26** questions are preserved in the draft. **12** have machine-scoreable
alternatives and **14** require manual adjudication. The draft is outside the
registered fixture directory, with classification pending and a null bundle
digest. No `holdout-v1` fixture is registered. No question has been deleted.
[Provisional draft](M4C_2B_HOLDOUT_V1_PROVISIONAL.json) · [Manual review criteria](M4C_2B_MANUAL_ONLY_CASES.md)

## Provenance and question parity

- All four source-file sizes and SHA-256 digests matched the handoff manifest.
  The authoritative question file digest is
  `7040266e9cd81dc0dbf4c4e65f4f2a787a14f656479cfd850c6495f5b585db5c`.
  The proposed gold digest is
  `6981d7fde7f48497fb5c7f7203ec2e158c7279e6b41828aada75e0f560922de7`.
  The audit digest is
  `f48dd654284b12e20a9842159a266a6e2eef7cd2b01f9e3963406b1514479851`.
  The reviewer instructions digest is
  `2e640b8678dce81a89d7fcac57e6b82473e708c9880131320f50eb383479e3a3`.
- All 17 question strings in the provisional review exactly matched the author's
  strings. The narrative audit has all 26 IDs as headings and contains summaries,
  so there are no full question strings there to compare. The nine omitted
  cases were q004, q009, q012, q016, q017, q018, q021, q022 and q025.
  The provisional JSON contained 12 `validated` and five `rejected` cases.
  Its audit summary incorrectly counted q026 as validated.
- MPML was clean at `14ad36e3f70a10bb5781b88200e825a717ca402f` before and
  after the checks. The existing pinned checkout in this workspace was named
  `market-phase-ml`. The dedicated worktree name in the handoff was unavailable.
  The checkout's canonical spec and CLI reference SHA-256 values matched the
  review hashes
  `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` and
  `d139c6a5828eadaddde64d28ed89509045700b841c8625336fc6e61855586dff`.
- The local existing index recorded that MPML SHA, clean state and spec hash.
  Its exact-byte SHA-256 was
  `e14155c3c8d69f0a2c86d98a6de1be1759bb100091124b5122890ff92d205735`.
  This is the local index fingerprint, distinct from the archived M3.5 index
  fingerprint. No query, embedding or index rebuild was performed.
- The author `mpml-independent-author-2026` disclosed seeing only the spec,
  reference and author instructions, with no prior Argus evaluation material.
  The reviewer `grok-independent-reviewer-m4c-2026` disclosed using only the
  author questions, spec, reference and reviewer instructions in a fresh
  context, without earlier Argus outputs or evaluations. These are supplied
  disclosures, not independently verified distribution records. This
  coordinator had access to the Argus implementation and prior findings.
  Coordinator adjudication does not count as a blinded review.

## Recovered authoring archive

The ZIP `m4c2b_author_source_bundle.zip` passed its CRC integrity check.
Its exact SHA-256 matched the maintainer's supplied digest.

```text
fd182f7be653094e7fe02d755899828430e790d20291de27139741db97504424
```

| ZIP member | Bytes | Locally computed SHA-256 |
| --- | ---: | --- |
| `cli_spec.json` | 24512 | `fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a` |
| `CLI_REFERENCE.md` | 13932 | `d139c6a5828eadaddde64d28ed89509045700b841c8625336fc6e61855586dff` |
| `AUTHOR_INSTRUCTIONS.md` | 2540 | `a8fee59b494ff24a8d8a1c6a967f113390bcd7256045e4bbf968ca1dc05115db` |

The spec and CLI reference are byte-identical to the pinned MPML checkout.
The recovered instructions name this ZIP and limit the author to those three
members, consistent with the author's disclosure. These checks establish the
recovered archive's contents. The maintainer's independent sidecar comparison
is reported provenance. Local comparison against the original sidecar and
verification of the distribution record remain pending.

## Disposition inventory

**Observed** means the actual pinned MPML preflight returned the stated exit
status and issues. **Spec** means a rule documented in the pinned reference.
**Judgment** records an interpretation of the question or scorer's coverage.
Preflight acceptance is evidence about launch validation only.

| ID | Disposition | Gold decision and evidence |
| --- | --- | --- |
| q001 | Machine | Variant C, seed 817, output `pilot-c`. All six orders of the independent flags passed with exit 0 and no issues. Add the four previously unlisted orders. The path remained absent afterward. |
| q002 | Manual | The exact prior probe exited 0 without issues. CLI variant E wins and inherited seed 19 applies by documented precedence. The output does not establish those effective settings through preflight alone. |
| q003 | Machine | Keep `--behavioral-surface reactive_jpy`, observed exit 0 with no issues. An env-only alternative also passed. Remove it from gold because the CLI candidate demonstrates the capability the question asks about. |
| q004 | Manual | Promote the support finding, not a machine gold label. `ACTIVE_PAIRS=EURUSD` exited 0 without `ACTIVE_PAIRS_UNKNOWN`. The reference identifies the override but does not list the supported universe. Human review covers that distinction. |
| q005 | Machine | Keep TF4 and MR42 as two `--strategy` flags. Both orders exited 0 without issues. The question sets a per-run scope and specifies no order. |
| q006 | Machine | Keep exact `--strategy XYZ7`, observed exit 1 with `STRATEGY_UNKNOWN`. A bare abstention is also permissible pending review of its reason, since no valid launch exists for that exact ID. |
| q007 | Machine | Keep `--phaseaware-tf TF3` and `--phaseaware-mr MR5`. Both orders exited 0 without issues. |
| q008 | Machine | Keep the exact requested TF role for MR2. It exited 1 with `PHASEAWARE_ROLE_INVALID`. A different role would answer a different question. |
| q009 | Machine | Add variant D with the gen2 consistency hint in both orders. Both exited 0 without issues. Attribute confirmation to the exact preflight observations. The published reference alone states the consistency requirement without mapping D to a generation. |
| q010 | Machine | Keep `--recommendation-top-n 3` and `--recommendations-per-pair`. Both orders exited 0 without issues. |
| q011 | Machine | Keep the exact zero candidate. Exit 1 with `TOP_N_NOT_POSITIVE` establishes the expected rejection. |
| q012 | Manual | Flag alone in the default scope exited 0 with no issues. Adding `--strategy TF4` exited 1 with `TIMELINE_NEEDS_DYNAMIC_SELECTOR`. The answer depends on scope, so a single unconditional disposition is inadequate. |
| q013 | Machine | Keep `--debug`. It exited 0 with no issues. The spec documents detailed fold diagnostics. |
| q014 | Manual | All four proposed disable values exited 0 without issues. The documented default and loose-boolean behavior require explanation. |
| q015 | Manual | Correct the provisional disposition. Exact `yes` exited 0 with `ENV_BOOL_PARSED_FALSE` at warning severity. Strict semantics mean DL is off. Argus command withholding is a separate guard. |
| q016 | Manual | Empty primary plus a synthetic legacy path exited 0 with `DL_ALIAS_SUPPRESSED`. This proves the preflight condition, not which artifact a later launch would load. |
| q017 | Manual | A missing probe path without DL enabled yielded no issues. Adding `DL_SIGNALS_ENABLED=true` yielded `DL_ARTIFACT_PATH_MISSING` as a warning. Both exited 0. Neither establishes a valid runtime result. |
| q018 | Manual | The spec marks `ACTIVE_PAIRS` as import-timed and notes later environment reads. No late-mutation behavior was tested. |
| q019 | Manual | The proposed broker CSV override and illustrative path exited 0. Remove that path from gold because the question supplies none and the probe does not check input data. |
| q020 | Machine | Keep exact `MPML_START_DATE=2018-01-01` and `MPML_END_DATE=2024-12-31`. Probe exited 0 without issues. |
| q021 | Manual | Existing-directory probe `--output-dir .` exited 1 with `OUTPUT_DIR_EXISTS`. The answer is a safety explanation about reuse, without a user-supplied concrete path. |
| q022 | Manual | Runs-root-only probe exited 0. Adding `MPML_OUTPUT_DIR=.` exited 1 with `OUTPUT_DIR_EXISTS` attributed to `MPML_OUTPUT_DIR`. The specified parent and override semantics are explanatory. |
| q023 | Manual | Remove the proposed empty authoritative rejection. Empty argv/env actually exited 0. Spread and slippage are source-edit-only per the spec. |
| q024 | Manual | The reviewer's illustrative trace configuration exited 0. Remove invented path, pair and timestamp from gold. The three documented keys are diagnostic-scoped and the question supplies no values. |
| q025 | Manual | The export flag alone exited 0. The spec lists walk-forward enablement as source-edit-only. The probe cannot establish that the flag enables the underlying evaluation. |
| q026 | Machine | Retain rejection and the exact CLI/env settings. Replace `SURFACE_UNKNOWN` with the observed `ARGPARSE` error. Exit 2 occurs at argument parsing. The documented CLI precedence is an explanation, not an observed fallback run. |

The mechanical subset is smaller than the 26-question authored set. Any
later comparison should report its denominator separately and account for the
manual inventory. Machine credit cannot establish whether explanatory prose
was correct.

## Read-only checks

Ran **41** invocations of the pinned interpreter's `-m mpml.preflight` in the
pinned checkout. Used a cleared process environment with only a minimal PATH,
locale, disabled bytecode writes, and scratch cache settings before applying
each case's exact env overrides. Each invocation used a token list with a
90-second timeout. No commands were handed to a shell or executed as launches.
The q001 output folder, q017 missing artifact and q022 probe runs root remained
absent. The existing directory for q021 and q022 was `.`.

For machine-scored candidates, the draft lists exact tokens and overrides for
each observed combination. Bare q006 abstention is a human-review alternative
and had no invocation. The clean probes had JSON `{"schema_version":1,"issues":[]}`.
Representative manual clean probes were q002's CLI E with the stated B/19
environment, q003's `BEHAVIORAL_SURFACE=reactive_jpy`, q004's
`ACTIVE_PAIRS=EURUSD`, q012's default-scope timeline flag, q014's four proposed
boolean values, q017's missing file with DL unset, q019 and q024's supplied
illustrative configurations, q022's `MPML_RUNS_ROOT=m4c-probe-runs`, q023's empty
candidate and q025's recommendation flag. Illustrative inputs are probes only.

All nonempty diagnostic outputs are recorded below. Each row is the issue
object as returned by MPML, with its question ID and process exit code added.

```jsonl
{"id": "q006", "exit_code": 1, "code": "STRATEGY_UNKNOWN", "severity": "error", "source": "--strategy", "message": "Configuration error: unknown strategy ID(s) ['XYZ7']. Available: ['MR1', 'MR2', 'MR3', 'MR32', 'MR42', 'MR5', 'TF1', 'TF2', 'TF3', 'TF4', 'TF5']"}
{"id": "q008", "exit_code": 1, "code": "PHASEAWARE_ROLE_INVALID", "severity": "error", "source": "PhaseAware configuration", "message": "Configuration error: --phaseaware-tf must reference a TrendFollowing strategy, got 'MR2' (family='MeanReversion')."}
{"id": "q011", "exit_code": 1, "code": "TOP_N_NOT_POSITIVE", "severity": "error", "source": "--recommendation-top-n", "message": "top_n must be a positive integer, got 0"}
{"id": "q012", "exit_code": 1, "code": "TIMELINE_NEEDS_DYNAMIC_SELECTOR", "severity": "error", "source": "--export-dl-conditional-portfolio-timeline", "message": "The dynamic selector is inactive for this evaluation scope."}
{"id": "q015", "exit_code": 0, "code": "ENV_BOOL_PARSED_FALSE", "severity": "warning", "source": "DL_SIGNALS_ENABLED", "message": "DL_SIGNALS_ENABLED is parsed as false; use 'true' to enable DL signals."}
{"id": "q016", "exit_code": 0, "code": "DL_ALIAS_SUPPRESSED", "severity": "warning", "source": "DL_PREDICTION_ARTIFACT_PATH", "message": "DL_PREDICTION_ARTIFACT_PATH is set, so DL_SIGNALS_CUBE_PATH is suppressed."}
{"id": "q017", "exit_code": 0, "code": "DL_ARTIFACT_PATH_MISSING", "severity": "warning", "source": "DL_PREDICTION_ARTIFACT_PATH", "message": "Explicit DL prediction artifact path does not exist: 'm4c-2b-preflight-missing-artifact.parquet'."}
{"id": "q021", "exit_code": 1, "code": "OUTPUT_DIR_EXISTS", "severity": "error", "source": "--output-dir", "message": "Output directory already exists: .."}
{"id": "q022", "exit_code": 1, "code": "OUTPUT_DIR_EXISTS", "severity": "error", "source": "MPML_OUTPUT_DIR", "message": "Output directory already exists: .."}
{"id": "q026", "exit_code": 2, "code": "ARGPARSE", "severity": "error", "source": "argv", "message": "argument --behavioral-surface: invalid choice: 'unknown' (choose from persistent, reactive_jpy, trend_vol)"}
```

## Freeze procedure after the blocker is resolved

1. Obtain the original coordinator distribution record and digest of the exact
   bundle supplied to the author. Verify that record against the disclosures,
   including the author instructions. Record any prior exposure or uncertainty.
   If blinding cannot be established, classify a future fixture as a
   development set. Obtain the source bundle digest for that registration as
   well.
2. Confirm the machine-only denominator and manual review plan. Set the
   final fixture identity, version, and honest provenance. Keep all manual
   questions in their inventory. Validate the final machine subset through
   the registered loader and recheck question parity against the author file.
3. Commit the exact fixture bytes before model evaluation. Record the commit,
   version, and digest from
   `sha256sum eval/generation/fixtures/<fixture-id>.json`. Any later change
   requires a distinct ID, version and digest. [Holdout protocol](M4C_HOLDOUT_PROTOCOL.md)

No Argus M3/M4 benchmark, Ollama inference, or MPML experiment was run.

## Offline verification

```text
Question parity: 26/26 exact UTF-8 strings; 12 machine, 14 manual.
Merged validator: provisional machine-case payload is structurally valid.
Registered loader rejects incomplete provenance: Fixture provenance must declare classification 'blinded_holdout'
Every executable gold alternative matches an observed preflight result.
Historical baseline SHA-256 unchanged.
Provisional draft SHA-256: c7f920cd3d01b90cdbdd9ad11b9102708d9d1575a10dbcd6b8180f48020fd247
```

The schema check exercised the merged case validator without making a provenance
claim. The registered loader check used a temporary fixture directory and left
the provisional bytes intact. The digest above identifies the provisional
draft. There is no frozen-fixture digest.

- `python -m pytest -q` reported `211 passed in 4.21s`.
- `ruff check src tests eval` reported `All checks passed!`.
- `git diff --check` exited 0 with no output.
