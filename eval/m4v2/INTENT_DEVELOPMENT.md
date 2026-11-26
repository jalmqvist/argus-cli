# M4v2-2A offline intent extraction

`argus_cli.v2_intent.extract(question, spec, rules)` takes the original text, a caller-verified MPML spec, and optional explicit phrase bindings. The result contains a `RequestAnalysis` and an independent coverage label. The module does no source access. Its vocabulary uses only published flags and launch-selector environment entries, with precedence peers derived from the spec.

## Bounded grammar

- Separate clauses with semicolons, sentence boundaries, newlines, or `and`. Begin a clause with a setting instruction, a launch-recipe introduction, or explicit flag/env syntax. A bare named setting can continue a positive clause joined by `and`. Arbitrary residual text remains unresolved.
- Named settings include strategy, PhaseAware TF/MR, pairs, variant, seed and output directory. A phrase maps to a published setting; a missing mapping or unpublished literal stays unresolved. Named seed, variant and output directory use the CLI channel by default. Explicit environment-only language can select a documented precedence peer. Explicit CLI/env literals keep their own channel.
- An exclusive channel adds a prohibition of the corresponding peer when the spec lists one. When both channels are explicitly requested, keep both settings and their separate values. The checker detects an unrequested CLI override of a required env setting. It does not recompute MPML precedence or effective runtime configuration.
- Strategy lists support commas and local order cues such as `then`, `before` or `in that order`. Repeated explicit strategy selections retain multiplicity. Ordered lists and no-substitution requirements compare exact sequences. Unordered selections compare values and counts. Pair CSV preserves order where explicitly required and normalizes whitespace and case.
- Local negation forbids either an entire setting or named values. Defaults-only means no explicit argv/env overrides. Contradictory clauses keep their recognized requirements and record a gap. Quoted examples, conditionals, ambiguous references and injection cues can make the whole question unresolved rather than licensing a detached clause. Paths with spaces or shell quoting, free-form list conjunctions, and implicit scopes are outside this grammar.

All spans use zero-based Python character offsets and exclusive ends. They identify the exact original clause, including punctuation when present.

## Coverage and candidate consistency

| Coverage | Meaning |
| --- | --- |
| `enforced` | At least one recognized requirement and every clause fits the bounded grammar, with no detected material gap or conflict. |
| `partial` | At least one recognized requirement plus an unresolved clause, scope or conflict. |
| `unresolved` | No reliable launch constraint could be extracted and the input includes a gap or unsupported context. |
| `not_covered` | No launch intent within this grammar, such as an ordinary explanation question. |

Coverage applies only to the explicit grammar. An empty gap list has no authority outside that grammar. In particular, `enforced` does not certify semantic completeness or that an exact requested value is valid.

`check_candidate` reports satisfied, violated and unresolved requirements separately from candidate issues. It recognizes published single-value and zero-argument forms, accepts both split and equals-form CLI values, and flags unknown settings, unsupported shapes, repeated scalar flags and values outside published CLI choices. It leaves full argv/env validation, runtime defaults, pair membership and authoritative preflight to future stages. A candidate can match all recognized requirements while still having unresolved intent or candidate issues. This module has no command-release API.

## Offline development results

Run from the repository root after installing the development and LLM extras.

```sh
python -m pytest -q -s tests/test_v2_intent.py
```

The [versioned fixture](intent-development-v1.json) uses a synthetic spec with published option shapes and synthetic registry identifiers. The test reports case-specific mismatches. Precision and recall require an exact match on target, operator, channel, ordered values and span, with multiplicity counted. A candidate counts as consistent for this fixture only when coverage is enforced and the check reports no violation, unresolved requirement or candidate issue.

| Measure | Result |
| --- | --- |
| Requirement precision | 33/33 predicted |
| Requirement recall | 33/33 labeled |
| Coverage classification | 26/26 exact labels |
| False enforced | 0/11 expected non-enforced |
| Candidate false acceptance | 0/21 expected inconsistent |
| Candidate false rejection | 0/12 expected consistent |
| Unresolved material | 11 spans across 10 cases |

These cases exercise the specified grammar. The exposed independent holdout remains diagnostic evidence, and these numbers provide no estimate of live recipe or holdout performance.

## Questions for M4v2-2B

Decide how to bind a checked candidate to the same verified spec snapshot and authoritative preflight result. Define how any future planner records additional or implicit requirements and how an independent check assesses their completeness. Preserve coverage and consistency as separate inputs to that decision.
