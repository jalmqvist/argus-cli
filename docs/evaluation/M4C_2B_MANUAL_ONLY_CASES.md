# M4C-2B manual-only cases

These 14 questions are preserved verbatim in the archived provisional draft.
The registered fixture scores the other 12 cases. The current
scorer compares exact candidate settings and dispositions. A human needs to
check the following answers. Probe settings document a test condition, not
settings that the user supplied.
[Provisional questions](M4C_2B_HOLDOUT_V1_PROVISIONAL.json)

| ID | Human adjudication |
| --- | --- |
| q002 | Explain that CLI variant E wins over inherited B and seed 19 comes from the environment when the CLI seed is absent. The mixed candidate passed preflight. The reported settings follow from the documented precedence, since preflight does not print them. |
| q004 | Explain that `ACTIVE_PAIRS=EURUSD` must reach the process before the import-time selection. The published reference does not list all pairs. The live probe accepted EURUSD without `ACTIVE_PAIRS_UNKNOWN`. Review that distinction as well as the proposed override. |
| q012 | The CLI export flag exists. The default launch scope accepted the flag. The probe with only TF4 rejected it with `TIMELINE_NEEDS_DYNAMIC_SELECTOR` because the selector is inactive for that scope. Do not assume that omission of a selector option means the selector is inactive. |
| q014 | The default is true. `MPML_AUTO_ANALYZE=false` disables analysis. `0`, `no` and `off` are also false under the documented loose parser. All four settings cleared preflight. The default explanation needs review. |
| q015 | The spec enables DL only for case-insensitive exact text `true`. The inherited `yes` value parses false. The exact probe exited 0 with `ENV_BOOL_PARSED_FALSE` at warning severity, so the MPML launch-surface disposition is validated with warnings. Argus's conservative withholding for a nonempty enable value other than `false` is a separate policy. No Argus outcome was measured. |
| q016 | An empty-but-set primary suppresses the legacy alias. The probe emitted `DL_ALIAS_SUPPRESSED`. This establishes that the alias is ignored. It leaves actual runtime artifact resolution unverified. The user supplied no concrete legacy path. |
| q017 | A missing explicit artifact path emitted no issues with DL unset and `DL_ARTIFACT_PATH_MISSING` as a warning with DL set to `true`. Both exited 0. MPML preflight returns diagnostics. A clean or warning-only result does not establish artifact loading, DL activation, or a safe recommendation from Argus. |
| q018 | Set `ACTIVE_PAIRS` before Python starts. The documented filter is import-timed. Later metadata reads can differ from the earlier snapshot. The reference does not promise that late environment changes update selection. No late-import experiment was run. |
| q019 | Use `MPML_DATA_SOURCE=broker_csv` and `MPML_BROKER_DATA_DIR` for the caller's input location. The illustrative prior path cleared preflight, which did not verify its accessibility or read data. The question supplies no directory, so review a template or request for the path. |
| q021 | Preflight rejected `--output-dir .` with `OUTPUT_DIR_EXISTS`. Explain that this existing path is rejected and a fresh target is needed. The user supplied no concrete directory and the probe created nothing. |
| q022 | Use `MPML_RUNS_ROOT` as the parent for generated directories when no explicit output path is selected. `MPML_OUTPUT_DIR` sets an explicit directory and takes precedence over that default parent. With both keys set, preflight rejected the existing path named by `MPML_OUTPUT_DIR`. No generated path was created. |
| q023 | Spread and slippage appear under source-edit-only settings. The requested CLI/env capability is absent. Empty argv/env passed preflight, so the proposed authoritative rejection is unsupported by the probe. Review a factual explanation or a refusal to supply launch settings. |
| q024 | Configure `MPML_SELECTOR_TRACE_PATH`, `MPML_SELECTOR_TRACE_PAIR`, and `MPML_SELECTOR_TRACE_TIMESTAMP`. The reference lists environment diagnostic controls and no corresponding CLI flag. The user supplies none of the three values. An illustrative preflight success confirms neither that the trace is written nor that Argus accepts diagnostic-scope overrides. |
| q025 | `RUN_WALKFORWARD` is source-edit-only. `--recommendations-per-pair` requests output from pair-scoped walk-forward evidence. The export flag passed a probe, which does not establish that it enables walk-forward evaluation. Review both parts of the answer. |
