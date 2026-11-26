# M4C-4B — Blinded Manual Review Audit

Date: 2026-11-26

**Status:** Reviewer deliverables audited, still blinded. Do not assign responses to M3 or M4 until the private key is supplied and the review is sealed.

## Source fingerprints

- `review.json` SHA-256: `cb85ae4e4ce46551977ebc3e13e14254447a554e44a8bf0efa6722634b2c52bc`
- `blind_grades.json` SHA-256: `cf9c399c37d5a3253d53e667e0bfce6bc6f6964ea14187751b5421bb4e58ed1b`
- `blind_review_notes.md` SHA-256: `d1f20916df1f06bcf0ff9597b41a692ee191a86e5bd543910ac31c365e5bbff9`

## Automated audit

- All 14 packet IDs match the 14 grading IDs, in the same order.
- All 28 responses have five integer scores in the inclusive range 0–2.
- All 28 responses have an allowed overall classification, a nonempty rationale and supporting evidence.
- Published summary totals independently reproduce from `blind_grades.json`.
- This audit checks structure and internal arithmetic; it does not constitute a second independent substantive grading.

## Results by response label

| Measure | Response A | Response B |
|---|---:|---:|
| Correct | 1 | 1 |
| Partially correct | 4 | 2 |
| Incorrect | 9 | 11 |
| Unassessable | 0 | 0 |
| Factual / 28 | 8 | 5 |
| Completion / 28 | 7 | 8 |
| Configuration / 28 | 8 | 5 |
| Epistemic / 28 | 18 | 19 |
| Safety / 28 | 23 | 20 |
| Descriptive sum / 140 | 64 | 57 |

## Paired case classifications

| ID | Response A | Response B |
|---|---|---|
| q002 | incorrect | correct |
| q004 | incorrect | incorrect |
| q012 | partially_correct | incorrect |
| q014 | incorrect | incorrect |
| q015 | incorrect | incorrect |
| q016 | incorrect | incorrect |
| q017 | incorrect | incorrect |
| q018 | partially_correct | incorrect |
| q019 | incorrect | partially_correct |
| q021 | partially_correct | incorrect |
| q022 | incorrect | incorrect |
| q023 | correct | incorrect |
| q024 | incorrect | partially_correct |
| q025 | partially_correct | incorrect |

## Methodological qualifications

- The independent reviewer noted that the rubric did not prescribe a weighted composite, classification threshold or significance test. The summed dimensions are descriptive only.
- The reviewer declared conventions for explanation-free abstention, withheld-but-invalid proposals, and mixed prose/configuration. These conventions should be archived; they are not a substitute for a fully pre-specified decision rule.
- The packet is a projection of final structured Argus responses. It cannot reconstruct missing explanations or determine precisely how rejected proposals appeared to an end user.
- Workflow-label blinding is imperfect because response behavior itself can reveal implementation style.
- No evaluator identity attribution can be made from these files alone. Do not attempt to infer private mappings from response patterns.
- No independent replication of the reviewer's domain judgments has been performed.

## Next step

Preserve the exact reviewed packet, grades, notes and their digests. After the grading is sealed, use the **private** `reports/local/generation/manual/keys/review-01.json` strictly locally for the A/B to workflow mapping; do not send it to the independent reviewer. Produce a paired, case-level M3/M4 report with separate accuracy, completion and safety dimensions. Retain all original files unchanged.
