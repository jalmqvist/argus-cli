# M4 evaluation specification

## Baseline and paired comparison

Preserve the frozen M3.5 questions, scoring rules and historical single-pass
reports. The 20 questions informed the M4 design and are a **development and
regression reference**. Report results on them separately from an independent
holdout. The completed M3.5 runs used hybrid retrieval and produced 12 pass,
7 fail and 1 review for Qwen, 11 pass, 8 fail and 1 review for Gemma, and 6 pass,
14 fail and 0 review for Llama. [M3.5 findings](M3_5_GENERATION_BASELINE_FINDINGS.md)

Compare default M3 single-pass against opt-in M4 on the same questions. Start
with Qwen2.5-Coder 7B and match model digest, temperature, seed, context and
prediction limits, source snapshot, index, retrieval mode, evidence limit,
embedding digest and relevant environment. Record Ollama version, hardware,
implementation hashes, graph version, deadlines, and repair cap. Document any
unmatched condition. Retain the historical runs as recorded. Use paired M3/M4
runs when settings or hardware prevent a controlled comparison with the archive.
Report coverage and missing/error attempts separately from completed passes.
Keep subset and interrupted runs out of full-set comparisons.

Use the existing gold alternatives and scoring semantics on the reference
set. Project M4's final recipe, disposition, preflight findings and citations
to those fields, with full attempt history retained separately. An early
deterministic abstention can leave preflight uncalled. If the frozen scorer
classifies it differently from an exact diagnostic rejection, report the
transition and explain it without editing the gold. A correct abstention
disposition with an unreviewed rationale remains `review`. If reviewers
adjudicate it, report that outcome separately from the automated counts.
Record each disagreement about equivalence or explanation independently.
[Historical scoring and runner](../../eval/generation/README.md)

## Per-case record and aggregate metrics

| Measure | Record and compare |
| --- | --- |
| Outcome | Counts and rates for pass, fail and human review, with denominators. Publish a paired transition table including fail → pass, review → pass and pass → fail. List each regression with its reason. |
| Structure and evidence | Track schema/option-shape and citation outcomes separately for the first and final candidate. Report candidates blocked before preflight. |
| Preflight | Separate passed, passed with warnings, rejected, unavailable and skipped. Compare diagnostic codes and severities where expected. Preserve attempt-level findings. Count accepted preflights with explicit intent violations. |
| Intent consistency | Compare enforced constraints against gold intent, including missing settings, list/order errors, CLI/env placement, unsupported substitutions and unnecessary additions. Record material ambiguities and extractor coverage. Review both incorrectly extracted and missed constraints independently of candidate generation. |
| Abstention | Report correct, missed and unnecessary abstentions, unsupported capability attempts, and rationale review. Separate an allowed exact diagnostic rejection from an abstention. |
| Repair and time | Record initial outcome, repair reasons, reserved and actual model calls, repair attempts, stop reason and end-to-end wall time per case. Report call-count distribution and p50/p95 wall time using the same percentile convention and hardware for both arms. Include timeouts with explicit labeling and report sample counts. |

Track commands rendered on any case that required withholding. Treat such a
release, a validation bypass, a dropped error, a repair-cap breach, or a runtime
execution as an invariant failure regardless of aggregate quality. M4B can test
all of these offline with scripted model and preflight responses.
[Graph policy](../adr/0004-bounded-langgraph-orchestration.md)

## Independent holdout for M4C

Commission roughly 20–30 new sanitized MPML questions from an author who has
access to the pinned specification and documentation and has not used M4
outputs. Include natural requests as well as exact selectors. Vary wording,
combinations and order, and include negation, defaults, conflicting instructions,
missing identity, role substitutions, unsupported requests and artifact-proof
limits. Avoid paraphrasing the frozen 20 questions as the main source of cases.
Label accepted argv/env alternatives, explicit constraint spans, expected
preflight diagnostics, allowed rejections and abstention criteria. Have a
separate reviewer check labels against the published spec and preflight
contract. The holdout may include unsupported wording to measure abstention
and extractor coverage.

Register a fixture version, digest, provenance and scoring policy before
exposing the cases to model runs or tuning. Keep it separate from M4B
development fixtures until the final assessment. Run both arms on that frozen
holdout, record regressions and review cases, and compare against the reference
set without pooling the two. Changes after inspecting outputs require a new
version and a separately labeled follow-up. M4A defines the protocol. M4C
collects the holdout and reports measured results.
