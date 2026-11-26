# M4C-4 — Unblinded manual evaluation and combined independent holdout findings

Date: 2026-11-26. **No production changes or model tuning are included.**

## Status and provenance

- The private A/B assignment was independently recomputed from its recorded seed using HMAC-SHA256 with case IDs. All 14 assignments match the private key exactly. The raw seed and per-case private mapping are intentionally **not reproduced** here.
- The assignment key pins the archived question source digest `c7f920cd3d01b90cdbdd9ad11b9102708d9d1575a10dbcd6b8180f48020fd247` and two original raw capture digests. The original 14-case raw captures were **not supplied** here, so their byte-level SHA-256 bindings could not be independently recomputed. The blinded packet, grades, and mapping are consistent.
- All 14 IDs and all 28 scores matched across review packet and grade file. Every grade includes five 0–2 dimensions, an overall classification, rationale and evidence. The review was performed before the key was shared.
- The reviewer report is a **single workflow-label-blinded assessment**; abstention patterns may reveal workflow identity. It is not a double-blind or replicated evaluation.

## Unblinded manual results (14 questions)

| Measure | M3 single-pass | M4 agent |
| --- | ---: | ---: |
| Fully correct | 2 | 0 |
| Partially correct | 6 | 0 |
| Incorrect | 6 | 14 |
| User-facing explanations present | 14 | 0 |
| Abstentions | 2 | 14 |
| Commands available for manual use | 5 | 0 |
| Preflight `passed` | 6 | 0 |
| Five-dimension descriptive sum (max 140) | 58 | 63 |

### Scores by dimension (maximum 28 per arm)

| Dimension | M3 | M4 |
| --- | ---: | ---: |
| Factual | 13 | 0 |
| Completion | 15 | 0 |
| Configuration | 6 | 7 |
| Epistemic | 9 | 28 |
| Safety | 15 | 28 |

**Important:** The 5-dimension sum is not a preregistered composite performance metric. M4 obtains safety and epistemic points through withholding, even though it fails to answer every question. Therefore do not rank systems by the total score.

### Complete per-case classification

| ID | M3 | M4 | M3 dimension sum | M4 dimension sum |
| --- | --- | --- | ---: | ---: |
| `q002` | Correct | Incorrect | 10/10 | 5/10 |
| `q004` | Incorrect | Incorrect | 3/10 | 4/10 |
| `q012` | Partial | Incorrect | 4/10 | 4/10 |
| `q014` | Incorrect | Incorrect | 1/10 | 4/10 |
| `q015` | Incorrect | Incorrect | 3/10 | 5/10 |
| `q016` | Incorrect | Incorrect | 1/10 | 5/10 |
| `q017` | Incorrect | Incorrect | 2/10 | 5/10 |
| `q018` | Partial | Incorrect | 4/10 | 5/10 |
| `q019` | Partial | Incorrect | 5/10 | 4/10 |
| `q021` | Partial | Incorrect | 8/10 | 5/10 |
| `q022` | Incorrect | Incorrect | 1/10 | 4/10 |
| `q023` | Correct | Incorrect | 10/10 | 5/10 |
| `q024` | Partial | Incorrect | 4/10 | 4/10 |
| `q025` | Partial | Incorrect | 2/10 | 4/10 |

### Qualitative reading

- **M3:** correct on `q002` (variant and seed precedence) and `q023` (source-edit-only spread/slippage). Partial on `q012`, `q018`, `q019`, `q021`, `q024`, and `q025`. Wrong or materially incomplete on the other six. Five command recipes were made available for manual use, but several suggested configurations were unsafe or semantically wrong (notably `q016`, `q018`, `q022`, `q025`).
- **M4:** all 14 answers are early abstentions without a user-facing explanation, and no commands were released. This scores well on withholding but demonstrates no explanatory capability or ability to distinguish answerable questions.
- The grader penalized visible incorrect proposals even when not released. This is a graded user-facing response, not solely an execution-safety benchmark.

## Combined 26-question holdout — keep the two scoring regimes distinct

| Scope | M3 | M4 |
| --- | --- | --- |
| 12 machine-scoreable, frozen scorer | 7 pass, 4 fail, 1 review | 0 pass, 12 fail |
| 14 manual, independent overall judgments | 2 correct, 6 partial, 6 incorrect | 0 correct, 0 partial, 14 incorrect |
| Entire independent question inventory | 26/26 evaluated through separate protocols | 26/26 evaluated through separate protocols |

The machine scorer and human judgments are **not interchangeable**; no combined pass percentage is reported. The machine M4 arm made zero model calls, withholding all 12 commands; the manual M4 arm yielded 14 abstentions with null explanations. Thus M4 never demonstrated generative or repair behavior on the independent holdout. M3 shows meaningful coverage but still invents settings or misuses environment overrides on several questions.

## Interpretation and engineering next steps

1. Preserve the frozen holdout, gold and all original reports. This holdout has now been consumed for diagnosing M4; do not use repeated post-change results as fresh independent evidence.
2. Treat M4 intent coverage and response routing as the first architecture issue. Separate **answering read-only launch semantics** from **releasing verified commands**. A request may deserve a documented explanation even when no command is safe.
3. Preserve command-release safety and authoritative read-only preflight, while allowing constrained candidate generation or evidence-grounded explanation through an appropriately gated path. This is a design hypothesis, not a validated improvement.
4. Add development fixtures (separate from this holdout) for unambiguous supported intents, invalid configurations, source-edit-only questions, precedence and DL warnings. Include negative controls and explicit no-command explanations.
5. Build a fresh independent post-change evaluation before claiming M4 v2 improvement. Record separate metrics for completion, release safety, false withholding, incorrect released commands and repair success.

## Integrity fingerprints (SHA-256)

| File | SHA-256 |
| --- | --- |
| `review.json` | `cb85ae4e4ce46551977ebc3e13e14254447a554e44a8bf0efa6722634b2c52bc` |
| `blind_grades.json` | `cf9c399c37d5a3253d53e667e0bfce6bc6f6964ea14187751b5421bb4e58ed1b` |
| `blind_review_notes.md` | `d1f20916df1f06bcf0ff9597b41a692ee191a86e5bd543910ac31c365e5bbff9` |
| `review-01.json` | `8195e046e9e4355b56d90c8735a6ce2222e09c7ccad749c4265cd56f7c6efc13` |
| `qwen-holdout-m3.json` | `19b129b0c45191b56c7969c5721e1aa4edccf5226a3edbb127cfc2ba603cd03f` |
| `qwen-holdout-m4.json` | `80df895276a8d791ea1bfc2c064c536b4e7a0c5eb7f0e15a1601f72e68e123b3` |

The private key file hash is recorded for local integrity only. **Do not commit or distribute the private assignment file**. The report intentionally omits the seed and per-question mapping. Raw manual-run SHA-256 values recorded inside that key cannot be verified without the two original raw capture JSON files.

## Other caveats

- The independent reviewer had no earlier benchmark results but had both response columns, meaning methodological blinding was limited to workflow labels.
- The reviewer resolved several scoring-convention ambiguities (e.g. configuration points for concept-only questions and safety points for withheld malformed candidates) during grading, without a second independently replicated audit.
- Preflight success validates a concrete launch surface only. It does not establish artifact loading, actual execution or satisfaction of the user’s broader intent.
- Most importantly, absence of an M4 generation attempt is a deterministic gate outcome, not a direct measurement of Qwen’s ability in an agent workflow if allowed to generate.
