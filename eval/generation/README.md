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
