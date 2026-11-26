# M4v2-2C1 trusted live validation

`argus_cli.v2_live_validation.assess_fixed_candidate(question, settings, source)`
assesses a fixed MPML candidate through existing read-only interfaces. The
function is an internal Python entry point. Existing CLI workflows retain
their current dispatch and reports.

## Observation producers

- `verified_index` verifies the live source, published spec and index. The adapter captures canonical spec bytes, the clean source revision, spec and index digests, and pinned evidence IDs. It verifies the snapshot again after preflight and checks the index digest at the end. An unavailable or dirty initial snapshot returns a provenance blocker with no evaluation. Drift after capture preserves the bound observations for inspection and adds a blocker.
- The adapter takes a private copy of the exact candidate and uses the existing argument validator and published setting shapes. The intent checker separately records covered constraints, violations and unresolved requirements. Structurally invalid and out-of-scope candidates skip the probe.
- Lexical retrieval selects evidence from the verified index. Only exact pinned `mpml/spec.py` rows matching the authoritative structured record can attest channel and value support. CLI explicit choices, published zero-argument boolean flags and selected typed defaults can qualify. The adapter can resolve an evidence ID without finding setting support. Free-form paths, undocumented values and global defaults-only behavior stay unsupported by this attestation policy. The current spec does not provide a structured global defaults record, and empty overrides do not establish the inherited environment's effective behavior.
- `mpml.preflight` receives the configured interpreter and working directory, exact ordered argv, and exact explicit overrides applied to a frozen copy of the process environment. The bridge uses the live process environment by default for existing callers. The bound fingerprint covers the captured inherited environment plus the candidate fingerprint. A changed or unavailable environment blocks assessment, and a pre-probe change skips invocation. The checks compare observations at boundaries and cannot detect a transient edit that is reverted between reads.
- The existing bridge classifies preflight. The assessment retains exit code, issue code, source, severity and message for well-formed observations. It distinguishes acceptance with warnings from warnings without acceptance. Inherited values and candidate argv/env values appearing in diagnostic text are redacted and flagged. The report omits inherited environment values, bridge stderr, unapproved candidate argv/env and command text. Keep the internal environment fingerprint within trusted tooling.
- The adapter constructs gate observations in process. It supplies no independent material-intent or effective-configuration verification. Both statuses remain unresolved, including for an exact candidate accepted by preflight.

## Offline tests

```sh
python -m pytest -q tests/test_v2_live_validation.py tests/test_mpml_bridge.py
```

Synthetic spec and index data exercise the real bridge call boundary with
mock subprocess responses. Tests cover rejected and malformed inputs,
provenance and environment drift, replay, citation tampering, diagnostic
redaction, and dispatch compatibility for all three existing `ask` modes.
No real MPML checkout or market data is needed.

## Optional maintainer smoke test

Use a configured MPML interpreter, a clean checkout and a current local index.
Run from the Argus repo with the `llm` extra installed. Select an identifier
published by your MPML strategy registry. The example uses `MR32`; update
both the question and the candidate if it is absent.

```sh
python - <<'PYTHON'
from pathlib import Path

from argus_cli.config import load_sources
from argus_cli.v2_contract import Settings
from argus_cli.v2_live_validation import assess_fixed_candidate

source = load_sources(Path("sources.yaml"))["mpml"]
report = assess_fixed_candidate(
    "Use strategy MR32.",
    Settings(argv=["--strategy", "MR32"], env={}),
    source,
)
print("Candidate fingerprint:", report.candidate_sha256)
print("Coverage, provenance, environment:", report.coverage, report.final_provenance, report.environment)
print("Preflight exit:", report.preflight_exit_code)
print("Blockers:", report.blockers)
if result := report.evaluation:
    print("Snapshot:", result.binding.snapshot)
    print("Structure, citations, support:", result.structure_valid, result.citations_resolved, result.setting_evidence_valid)
    print("Preflight:", result.preflight.outcome)
    print("Material intent, effective configuration:", result.material_intent, result.effective_configuration)
    print("Diagnostic codes:", [issue.code for issue in report.preflight_issues])
PYTHON
```

Expect both intent and effective-configuration blockers even if the probe
accepts the candidate. Other fields depend on the checkout, index and inherited
process settings. The optional smoke test was not run for this milestone.
M4v2-2C2 owns independent assessment of full material intent and effective
configuration. A future release path also needs fresh verification at its
actual release boundary.
