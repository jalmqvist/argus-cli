# M4v2-3C evidence-led development regression

The [3B findings](FIRST_ATTEMPT_FINDINGS_3B.md) remain the recorded baseline.
The fixture, gold alternatives and historical scoring stay fixed.

- **Routing.** The broad reference guard previously treated “this configuration”
  as missing context even when the sentence specified a strategy. A narrow
  self-contained selection cue now permits a proposal. Missing prior pair
  references still stop before inference and ask the user to name the pair.
- **Retrieval.** The eight lexical excerpts previously missed some directly
  relevant structured records. Exact request flags and environment keys,
  narrow setting cues, and published precedence peers now prioritize matching
  verified spec entries within the same eight-excerpt budget. Lexical results
  fill the remaining slots. Evidence offered to the model and evidence it
  actually cites are recorded separately. No model citation is added later.
- **Seed evidence.** C1 previously supported selected defaults or enumerated
  choices. A cited seed record can now support an integer under the documented
  parser rule when the pinned spec also confirms seed type, precedence and
  fallback semantics. This includes non-default values and parser-accepted
  negative or large integers. It does not certify downstream random-number
  generator limits. An empty environment override can select the published
  fallback without being a typed integer. Effective selector precedence,
  authoritative MPML preflight and complete intent remain separate findings.
- **Substitution and guidance.** A short v2-only prompt addition asks the model
  to preserve explicit channels, roles and exact values and use abstention when
  unsupported. The response can explain a documented role or variant mismatch,
  an omitted pair override, an explicit environment-only conflict, or why
  preflight was skipped. These observations do not rewrite the candidate or
  promote partial interpretation to complete intent. The release gate and
  one-call budget are unchanged.

## Maintainer-local paired rerun

Use the same pinned checkout, index digest, model digest and generation settings
as the baseline where available. Run from the repository root with the existing
local Qwen model and an unused output directory outside Git worktrees.

```sh
python -m eval.m4v2.run_development \
  --config sources.yaml \
  --output "$HOME/argus-m4v2-first-attempt-3c"
```

The runner records new implementation hashes. Compare the 14 case IDs to the
original private 3B results as a **paired development regression**. Record any
provenance difference. Compare generation reachability, exact candidate grades,
substitutions, records retrieved and cited, and exact-value seed support.
Review preflight outcomes separately from factual-answer usefulness and
unnecessary withholding. Compare model calls, wall/generation latency and
released-command counts. A higher preflight acceptance count is insufficient
to conclude that first-attempt correctness improved.

No real-model rerun was performed for this PR. Remaining work includes
independent human review of answer usefulness and an untouched evaluation before
generalization claims. Broader parser rules, retries and complete-intent
verification were left outside 3C.
