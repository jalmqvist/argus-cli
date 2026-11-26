# M3 generation smoke evaluation

This initial fixture covers two explicit launch intents and two requests that
should abstain. It is separate from the frozen M2.5 retrieval benchmark.
The expected argv and overrides for the launch cases are checked exactly,
along with verification status. The abstention cases check that Argus renders
no command.

Use a clean MPML checkout at `14ad36e3f70a10bb5781b88200e825a717ca402f` and
verify its interpreter can run both `mpml.spec` and `mpml.preflight`. Run from the
Argus root after building the hybrid index with `nomic-embed-text` and setting
`MPML_REPO` and `MPML_PYTHON`. Use an environment without MPML launch overrides
for comparable results. [Local setup and model instructions](../../README.md#ask-for-a-cited-mpml-recipe)

```bash
python eval/generation/smoke.py
```

The runner uses a 300-second generation timeout for CPU inference. It captures
structured outcomes and elapsed time and leaves every command as text. Use
`--case strategy-and-pair` to rerun the README example on its own.

## Recorded smoke outcomes

All four cases matched their frozen expectations using `qwen2.5-coder:7b` on
Ollama 0.40.18 with CPU inference and the pinned 139-chunk MPML index. Both launch
candidates passed real MPML preflight. Both requests for unsupported or unverified
capabilities abstained.

| Case | Verification | Preflight | Command rendered |
| --- | --- | --- | --- |
| MR32 on USDJPY | Validated | Passed | Yes |
| Set seed to 123 | Validated | Passed | Yes |
| Place a live broker order | Abstained | Skipped | No |
| Prove DL activation and artifact loading | Abstained | Skipped | No |

An initial prompt run added an unrelated PhaseAware option to the MR32 request.
MPML rejected it after the preflight environment was configured. The recorded run
uses the revised prompt and presents the retrieved spec entries first. The small
fixture measures these specific requests and does not estimate general model
reliability. The recorded wall times include CPU inference and any local queue
wait. [Measured results and provenance](results.json)

## M3.5 single-pass reliability baseline

The final M3.5 set freezes 20 sanitized questions against the same MPML revision
used above. The four historical smoke questions and results remain available for
development and debugging. Their scores are separate from the M3.5 baseline.
M2.5 continues to measure retrieval independently. [Frozen M3.5 cases](baseline-v1.json)

Gold answers were authored from the published MPML spec and preflight behavior
before model comparisons. The fixture covers valid launches, precise precedence
requests, multiple settings, invalid selectors, unsupported capabilities, and
cases where certainty is unavailable. Each question lists allowed outcomes.
Candidate outcomes specify the exact argv, overrides, and diagnostic codes.
Some invalid requests allow either an explicit abstention or the specified
preflight rejection.

- `--flag=value` and `--flag value` compare equally. Override key order is irrelevant.
  All values compare exactly, with differences such as CSV whitespace allowed
  only where the fixture lists an alternative. Argument order and multiplicity
  matter unless an equivalent order is listed explicitly.
- The intent score checks the selected settings separately from preflight. Missing
  and additional options and overrides are reported against the closest eligible
  gold alternative. A clean preflight with incorrect settings still fails the case.
- A permitted abstention with no rendered command and a reason is counted as a
  correct disposition. Its outcome remains `review` so a human can verify the
  reason. Free-text explanations, evidence relevance, and runtime behavior require
  independent review.
- Citation checks use the production validation result and compare resolved citations
  against the recorded index metadata. Offline scoring checks identity and provenance.
  Relevance and semantic entailment are outside this automated score.
- Diagnostic comparisons use exact code counts regardless of order. Missing
  feedback, malformed diagnostics, failures, and timeouts are visible in the report.

### Reproduce on a local machine

Use the repo root and its Python environment with the `llm` extra installed. Configure
the clean MPML revision in the fixture, unset inherited MPML overrides, and keep the
same `indexes/mpml.json` across comparisons. Use an already installed generation
model and a loopback Ollama instance with cloud features disabled. Build the
hybrid index with the existing `argus index --embed nomic-embed-text` command if needed.

```bash
python -m eval.generation.baseline run qwen-hybrid --model qwen2.5-coder:7b
python -m eval.generation.baseline run llama-hybrid --model llama3.1:8b
python -m eval.generation.baseline run gemma-hybrid --model gemma4:e2b

python -m eval.generation.baseline run qwen-lexical --model qwen2.5-coder:7b --retrieval lexical
python -m eval.generation.baseline run qwen-debug --case strategy-and-pair --case dl-proof
python -m eval.generation.baseline score qwen-hybrid
```

A run identifier selects a gitignored JSON file under `reports/local/generation/`.
Use a separate ID for each model, retrieval mode, or subset. Repeating the same
command resumes the selected cases, skipping every saved attempt, including
rejections and timeouts. To retry a recorded outcome, use a new identifier.
A single writer holds a lock and each attempt is committed by an atomic replace.
An interrupted active case may be retried. The run rejects manifest changes,
including changes to selection, model digests, index, source snapshot, generation
settings, source configuration, Argus implementation, or inherited environment
fingerprint. Keep the same working directory, checkout, interpreter, and environment
when resuming. Environment values are not included in the manifest.

The report contains each raw Argus response, generation and total wall time,
aggregate counts, and per-case scores. Generation timing wraps the existing
generation call in the evaluation subprocess, including local model lookup and
response validation. A subprocess timeout can leave generation latency unavailable.
The default generation timeout is 300 seconds and the wall timeout is 660 seconds.
Both are explicit report settings and can be changed with `--timeout` and
`--wall-timeout`. The offline `score` command recomputes metrics from the raw report
and frozen questions without Ollama or MPML. `complete_full` means every frozen case
has a recorded attempt. `complete_subset` and `partial` are labeled separately.
Completion counts attempts, including errors, and makes no claim about their quality.

The production workflow requires retrieved citations and abstains before generation
when evidence is empty. A no-retrieval run would therefore measure that guard.
This benchmark compares hybrid and lexical retrieval through the same `argus ask`
path. M3.5 includes no real-model results. The maintainer runs the comparisons locally.

## M4C-1 paired development-set evaluation

The same frozen 20 cases serve as a development and regression reference for
M4. They informed the graph design. The historical M3.5 results remain a
single-pass baseline, and the independent holdout is a separate future
evaluation. [M4 evaluation protocol](../../docs/evaluation/M4_EVALUATION_SPEC.md)

Use the pinned clean `market-phase-ml-argus-benchmark` worktree, the existing
index built for that source, and a consistent launch environment. Install the
`llm` and `agent` extras and use the same locally installed Qwen digest in both
arms. The example gives both arms the same outer timeout, with room for up to
three generation attempts in the agent arm.

```bash
python -m pip install -e '.[llm,agent]'
python -m eval.generation.baseline run qwen-m3-paired --model qwen2.5-coder:7b --wall-timeout 1200
python -m eval.generation.baseline run qwen-m4-paired --workflow agent --model qwen2.5-coder:7b --wall-timeout 1200

python -m eval.generation.baseline score qwen-m4-paired
python -m eval.generation.baseline compare qwen-m3-paired qwen-m4-paired
```

Repeat the exact run command to resume. Agent runs use `argus ask --agent`.
Each new report records the workflow, and the agent manifest adds the
LangGraph version, workflow ID, repair policy and call cap. Use distinct IDs
and keep the reports under the ignored local directory. Resume checks the
full manifest, including implementation hashes, and refuses to append under
changed provenance. Old reports remain scoreable, even when their original
runner version is needed to resume them. The Argus dirty flag is recorded
alongside implementation hashes.

`score` and `compare` read saved JSON and the frozen fixture without Ollama or
MPML. You can compare a saved historical `qwen-hybrid` report against a completed
agent run too. Comparison requires identical selected case IDs and the frozen
dataset hash. It refuses incomplete runs, labels matched subsets, and flags
different source, index or retrieval provenance. Use
`--allow-provenance-mismatch` only for an explicitly reported exploratory
comparison. Model/settings, runtime, implementation and available machine and
environment differences or unknowns are reported separately. Machine metadata
does not establish that the Ollama backend or system load matched.

### Reading the results

- The historical scorer still supplies pass, fail, review and error. A valid
  model abstention retains human review. An eligible early deterministic
  abstention without a candidate is marked separately as a review candidate.
  Its historical score is left intact. An abstention with no gold alternative
  is tracked separately.
- Validated recipe coverage counts rendered, launch-validated recipes.
  Gold intent, explicit-intent violations and command release are measured
  independently. An exact diagnostic rejection can earn credit where permitted
  by the original gold.
- Agent metrics track initial and final structure, intent coverage and violations,
  call cap breaches, call counts, repair outcomes, repeated-candidate stops and
  budget exhaustion. A transition from failed to passing structure is reported
  separately from recovery to a gold-scored pass after repair.
- Per-attempt generation times come from the agent. End-to-end timings use the
  benchmark subprocess wall clock for both arms. An outer timeout can leave
  the final response and model-call count unknown. Historical single-pass call
  counts are inferred from the presence of generation timing when a report exists.
- Comparison reports per-case transitions, new passes, regressions, and
  wrong recipes withheld without a new pass. Preflight-passed gold intent
  mismatches count final cases in both arms. M4's separate count uses
  explicit constraint violations across attempts.
- Reports retain the CLI's final JSON and exported attempt diagnostics. Earlier
  candidate argv/env are unavailable, so the evaluator cannot establish candidate
  equality or changes across attempts. A repeated stop comes from the graph's
  stated stop reason. Matching validation codes alone do not establish repetition.
  The runner retains no bridge stderr or additional raw model responses.

No M4 benchmark outcomes are included with this infrastructure.

## Independent holdout fixtures

Use `--dataset` on `run`, `score`, and `compare`. The default is
`baseline-v1`, including for historical reports with no recorded fixture ID.
A future frozen `holdout-v1` fixture would live at
`eval/generation/fixtures/holdout-v1.json`. Register unblinded fixtures with a
`development-vN` ID. No independent fixture is supplied by this change.
[Fixture contract and authoring protocol](../../docs/evaluation/M4C_HOLDOUT_PROTOCOL.md)

After authoring and freezing a fixture, use the pinned MPML source and its
verified index. For example, once `holdout-v1` is registered:

```bash
python -m eval.generation.baseline run qwen-holdout-m3 --dataset holdout-v1 --model qwen2.5-coder:7b --wall-timeout 1200
python -m eval.generation.baseline run qwen-holdout-m4 --dataset holdout-v1 --workflow agent --model qwen2.5-coder:7b --wall-timeout 1200

python -m eval.generation.baseline score qwen-holdout-m4 --dataset holdout-v1
python -m eval.generation.baseline compare qwen-holdout-m3 qwen-holdout-m4 --dataset holdout-v1
```

Repeat the same run command to resume. Use a distinct run ID for each fixture
and workflow. A report pins the fixture ID, version, and SHA-256 of its exact
bytes. Matching case IDs alone cannot make reports compatible. The comparison
provenance override applies to source, index and retrieval settings. Fixture
identity, bytes and selected case IDs must always match. An older runner
version may still be needed to resume an old run under its original manifest.

## M4C-4A paired manual response capture

The separate `manual_capture` runner reads the 14 manual-only IDs and original
question strings from the archived provisional JSON. It checks both frozen
file digests and confirms that these cases and the 12 registered cases
partition the original 26. It performs no scoring or adjudication.
[Manual review criteria](../../docs/evaluation/M4C_2B_MANUAL_ONLY_CASES.md)

Run from the Argus root with the pinned MPML checkout and verified existing
index configured through `MPML_REPO` and `MPML_PYTHON`. Install the existing
`llm` and `agent` extras for live capture and use the same local model, index,
settings and environment for both arms.

```bash
python -m eval.generation.manual_capture run manual-m3-01 --workflow single-pass
python -m eval.generation.manual_capture run manual-m4-01 --workflow agent
python -m eval.generation.manual_capture packet manual-m3-01 manual-m4-01 review-01
```

The first two commands run inference locally. Repeat the exact command with
the same run ID to resume after interruption. The runner saves each completed
attempt atomically, including timeouts and unavailable reports. Use a new
run ID to rerun recorded attempts or change provenance. Reports pin the exact
archived question-source and frozen scored-fixture fingerprints, MPML SHA and
spec hash, index and model digests, retrieval and generation settings, Argus
revision, implementation hashes and environment fingerprint. Raw structured
reports, error categories, and timings are retained locally.

All capture output is gitignored under `reports/local/generation/manual/`:

| Location | Use |
| --- | --- |
| `runs/<run-id>.json` | Private raw capture, manifest and resume state. |
| `packets/<packet-id>/review.json` | Share only this file with the reviewer, alongside the manual review criteria. |
| `keys/<packet-id>.json` | Private assignment, random seed, and exact input fingerprints. Keep this file for reproducibility. |

The packet command works offline on two complete, provenance-compatible
captures and assigns Response A/B independently per case using a private
random seed and HMAC-SHA256. Repeating the packet command with the same
ID, key and captured bytes regenerates the same packet bytes. Use a new
packet ID if either report changes. Completion means every question was
attempted. The packet marks captures that lack an Argus JSON response.

The packet preserves explanation and uncertainty when available, ordered
settings, citations, final verification and preflight findings. It projects
these fields from final reports only. Workflow identifiers in prose and known
extractor boilerplate are neutralized. Raw command strings, implementation
metadata, stop reasons, intermediate attempts, timing, raw errors, and
prior benchmark scores stay outside the packet. Proposed argv and env are
preserved as data. Reviewers may still infer the workflow from substantive
response behavior, including different abstention patterns.

An early abstention or invalid candidate can leave the Argus explanation
field empty. The packet preserves that absence. It has no way to recover
model text that Argus did not export. Review using the existing criteria and
keep any assessment separate from the raw captures and private key.
