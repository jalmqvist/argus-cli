# v0.1.0rc1 — Read-only developer preview: release scope and acceptance

**Status:** Release preparation is under review. Maintainer-local acceptance, tagging and publication remain pending. See the [acceptance checklist](V0_1_0_RC1_ACCEPTANCE.md).

## Decision and positioning

Ship an installable, clearly limited **MPML-first, local, read-only research CLI assistant**, not a production-ready natural-language launch recipe generator. The objective is a usable baseline from which further evaluation and redesign can proceed without a release deadline. **Do not** relax authorization, fabricate verification, or expand LLM/hardware requirements to make the preview appear more capable.

### Supported preview capabilities

- Inspect the authoritative MPML CLI specification and explain documented flags, environment keys, precedence, defaults and published diagnostics.
- Run the allowlisted **read-only** MPML preflight interface on explicit candidate argv/env. Preflight acceptance means launch-surface acceptance, **not** intent satisfaction, execution, DL activation, artifact loading or strategy correctness.
- Build a local verified lexical index and retrieve cited MPML evidence. Embedding/hybrid experiments remain optional, not part of the v2 quickstart requirements.
- Use **`argus ask --agent-v2`** for deterministic grounded answers (no Ollama call for supported informational questions) and one-shot local Qwen configuration assessment with qualified explanations. **V2 does not release an assembled manual command or full public candidate settings.**
- Keep `argus ask` (M3, current default) and `argus ask --agent` (M4 v1) for compatibility and historical experiments, clearly labeled as legacy/experimental with materially different command-release behavior. **Do not silently rebind or change these entrypoints** during the release-prep PR.

**Not supported/claimed:** independent verification of arbitrary natural-language material intent or complete effective configuration; verified v2 recipes; MPML experiment execution; broker actions; proof of actual model/strategy success. An accepted preflight is never authorization by itself.

## Recorded engineering evidence, not generalization

The pinned, developer-authored 14-case M4v2-3A/B/C fixture used a clean MPML source/spec/index and local `qwen2.5-coder:7b` on GTX 1070 (8 GB). In a same-fixture paired development rerun, exact-correct candidates on the **seven supported configuration cases** went **3/7 → 5/7**; incorrect candidate grades went 4 → 2; both invalid-exact cases preserved the requested invalid option and failed structural verification. Nine generation attempts had median generation **6.804 s** and p95 **9.153 s**; total median over all 14 cases **8.100 s**. **No v2 commands were released.** See [paired findings](../../eval/m4v2/PAIRED_FINDINGS_3C.md). These are small, exposed development samples, not independent holdout results or evidence of release safety across unseen requests. Human factual/usefulness ratings remain unresolved.

Known recurring first-proposal errors: environment-only requests may be answered with extra CLI selectors despite explicit channel constraints, and `ACTIVE_PAIRS` requests may omit the pair-filter override. The current checks withhold a v2 recipe rather than silently release those candidates. Future work will investigate causes before tuning or introducing repairs.

## Release candidate acceptance gates (all must be documented)

1. **Packaging and metadata:** Align distributable project version and Git tag as **`0.1.0rc1` / `v0.1.0rc1`** (PEP 440 package version). Build wheel and sdist; verify installed `argus` entrypoint and optional dependency handling in a fresh Python 3.12 environment. MPML checkout, local private configs and index files must not be packaged. Avoid a PyPI publication unless specifically approved.
2. **Offline CI:** Full tests, Ruff check and packaging/build smoke tests pass. Public CI runs with synthetic fixtures only—no private datasets, real MPML clone, broker credentials, Ollama or GPU. Keep a clean commit, exact test numbers, and build evidence.
3. **Maintainer-local acceptance:** With the pinned clean MPML checkout, its interpreter, correctly configured sources and verified local index: run `argus doctor`, `argus spec`, `argus inspect`, `argus explain`, `argus retrieve`, explicit `argus preflight`, one v2 deterministic question, and one v2 Qwen configuration question. Confirm source/spec/index hashes and expected JSON contracts; confirm v2 public `command=null` and `settings=null`, preflight is read-only, no experiment is run, and the model-call budget is at most one on the proposal path.
4. **User documentation:** A fresh-clone user can install the package, set MPML source/interpreter paths, build a lexical index and understand the distinction between v2 advisory behavior and historical M3/M4 command-generating modes. State limitations and troubleshooting, including the need to rebuild a stale index.
5. **Publication:** Only after gate evidence is reviewed, create a matching annotated tag and GitHub **pre-release**, with tested Git SHA, installation commands and known limitations. No tag or published release as part of the scope/documentation PR or before the maintainer-local smoke. If a gate fails, hold publication and fix the smallest blocker.

## Development priorities after the candidate

- **Focused diagnosis:** environment-only channel fidelity and `ACTIVE_PAIRS` omission; distinguish retrieved/cited evidence from actual candidate setting selection. Preserve the existing fixed development results.
- **Practical usefulness:** independently review gold alternatives, factual correctness, actionability of qualified responses and unnecessary withholding. Measure **candidate correctness** separately from **user task completion**.
- **Independent evaluation:** newly authored, frozen M4v2-4 holdout, predeclared scoring/denominators and matched source/model conditions. The exposed M4C and 14-case development questions are not fresh holdouts.
- **Future release eligibility:** bounded material-intent completeness and independently verified effective configuration for a restricted subset, then optional verified recipe publication. No model self-certification or silent candidate substitution.
- **Optional later ablations:** repairs, larger models, broader source adapters, design changes only when justified by findings. No deadline-driven redesign.

## Release-decision record

A working **read-only preview** can be valuable with imperfect model proposals **provided** packaging, deterministic functionality, local integration and public non-release invariants pass the release checks. Failed core smoke tests are **blockers**. The two disclosed model-generation errors and absence of certified v2 recipes are **known preview limitations**, not grounds to claim maturity. Completion of a release candidate is separate from the later stable `v0.1.0` promotion decision.
