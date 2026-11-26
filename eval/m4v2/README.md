# M4 v2 offline acceptance and evaluation

[`acceptance-v1.json`](acceptance-v1.json) contains newly authored synthetic development cases. Each case records a question, expected advisory route, synthetic gate observations, expected release eligibility and a prose review expectation. The offline tests inject the expected route and trusted observations into the schema. They test consistent decisions and rejected payloads; they do not measure routing accuracy, validate real MPML options or grade explanations. Observations omitted in a case use the synthetic defaults in the test helper.

Run from the repository root with the project's development and LLM extras installed.

```sh
python -m pytest -q tests/test_v2_contract.py
```

The completed 26-question M4C holdout is exposed diagnostic evidence. Keep its machine and human findings separate, and use a new independently authored and frozen holdout for claims about v2 generalization. Historical reports, fixtures and scorers stay on their original contracts. [Machine findings](../../docs/evaluation/M4C_3_HOLDOUT_PAIRED_FINDINGS.md) · [Blinded review audit](../../docs/evaluation/M4C_4B_BLINDED_GRADE_AUDIT.md) · [Combined findings](../../docs/evaluation/M4C_4_UNBLINDED_AND_COMBINED_FINDINGS.md)

## Future evaluation

| Measure | Machine-verifiable | Human review |
| --- | --- | --- |
| Answer completion and grounding | Answer presence and status, citation IDs, provenance and declared limitations | Correct/partial/incorrect completion, accuracy of claims, citation support and relevance, and whether prose supplies unauthorized launch instructions |
| Recipe correctness and explicit intent | Match frozen accepted argv/env alternatives, expected dispositions, recorded constraints and diagnostic codes | Resolve predeclared cases where natural-language equivalence or full intent cannot be scored mechanically |
| Routing coverage and false withholding | Report route matrix against gold routes and fractions reaching answer, candidate generation and preflight. Separate unsupported, ambiguous and infrastructure-failed cases | Identify independently answerable or release-eligible requests incorrectly withheld, and adjudicate ambiguous multi-part requests |
| Incorrect command releases | Null-command invariant, gate record, settings fingerprint, exact tokens and provenance; count releases violating any applicable gate or gold expectation | Inspect any suspected unsupported or unsafe behavior missing from machine assertions |
| Preflight outcomes | Record unrun, unavailable, rejected, warnings-only, accepted and accepted-with-warnings separately | Review what warnings mean for the requested outcome without inferring execution |
| Calls, repair and latency | Count reserved and actual calls separately, including failed calls. Record initial and final attempt results, repair count and termination. Report p50/p95 end-to-end latency with timeouts and partial runs visible | Review whether a repair actually recovered intent or merely passed structure/preflight |

Pre-register denominators and the grading rules by route. For mixed requests report both task outcomes; a grounded answer with a withheld recipe can complete the answer portion. Keep infrastructure failures and review-pending cases visible. Report incorrect releases both as a count and against the number of released commands, with zero releases clearly identified. Preserve reproducibility metadata so an offline evaluator can trace disagreements without rerunning local models.

See the [response and routing contract](../../docs/architecture/M4_V2_RESPONSE_CONTRACT.md).

See the [offline intent extraction fixture and results](INTENT_DEVELOPMENT.md)
for M4v2-2A.
