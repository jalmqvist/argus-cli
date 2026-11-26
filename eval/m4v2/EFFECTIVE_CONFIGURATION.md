# M4v2-2C2A effective configuration

The resolver uses two selectors from MPML schema v1. The source audit covered
`mpml/spec.py`, the CLI declarations and the seed/variant readers at MPML
revision `14ad36e3f70a10bb5781b88200e825a717ca402f`.

| Selector | Published resolution |
| --- | --- |
| Experiment seed | `--experiment-seed` wins. Otherwise use the explicit `EXPERIMENT_SEED` override, or the inherited value when the key is not overridden. The environment integer is stripped as documented. Absent or blank selects fallback 42. An invalid winning value stays unresolved. |
| Experiment variant | `--experiment-variant` wins. Otherwise use explicit `EXPERIMENT_VARIANT`, then inherited, then fallback A if absent. Only exact published canonical choices are resolved. Empty, padded, lowercase and unfamiliar values stay unresolved. |
| Output directory | Unresolved. The specification publishes precedence for selecting an output directory, plus a runtime fallback under `MPML_RUNS_ROOT`. This does not specify a concrete effective path for an arbitrary invocation. |
| Other selectors | Unresolved. No alias expansion, general enum/Boolean conversion, artifact resolution or source-edit-only behavior is inferred. |

Explicit empty environment values replace inherited values. Only the seed spec
documents the blank-to-fallback rule used here. Missing or conflicting
precedence rows, inconsistent fallback data, undocumented semantics and malformed
candidate arguments leave the relevant observation unresolved. The current
schema's semantics text is checked verbatim for these two narrowly scoped rules,
so wording changes require review before the affected selector is resolved.

The standalone function verifies that the supplied binding matches the clean,
trusted spec/index snapshot, request, exact argv/env and inherited environment.
Each observation reports the setting, its winning source and the corresponding
spec headings, or a reason it is unresolved. A resolved value is an observation
about one selector only. Values returned by the standalone resolver are for
trusted in-process use. Do not serialize them into public reports.

The C1 adapter attaches value-free observations after successful final provenance
and environment checks on a structurally valid candidate. Its aggregate
effective-configuration and material-intent gates continue to report unresolved,
including when preflight accepts the candidate. CLI and preflight inputs are
unchanged.

## Optional maintainer smoke test

Use the [C1 procedure](LIVE_VALIDATION.md) on the clean pinned checkout and
verified index. Add `--experiment-seed`, `57` to the fixed candidate's argv and
request seed 57 in the question. In the same process, set
`EXPERIMENT_SEED=58` through an explicit candidate override and inspect the
published spec with `argus explain EXPERIMENT_SEED`. On a matching clean snapshot,
the seed observation should report `independently_verified=True` and
`winner=cli`. Repeat with no CLI seed to check the explicit-env winner. Remove both
and unset the inherited key to check the published fallback. Print only
`report.effective_observations` from the C1 report and the preflight outcome.
Preflight is an MPML launch check. It does not establish the complete effective
configuration. The optional smoke test was not run for C2A.

C3 still needs the bounded local proposal path and a qualified response that
explains preflight and remaining gaps. Full release also needs independent
material-intent and effective-configuration verification.
