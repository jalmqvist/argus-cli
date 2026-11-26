# M4C independent holdout protocol

The frozen `baseline-v1` questions informed M4 development. Use a separately
authored and frozen fixture to assess generalization. This protocol defines
the procedure and fixture format. It supplies no questions or results.
[Paired runner instructions](../../eval/generation/README.md)

## Restricted source bundle and independent roles

A coordinator prepares a read-only bundle containing the machine-readable
`mpml.spec` output from the pinned clean MPML revision and the published CLI
reference from that revision. Include the source revision, canonical spec
SHA-256, and references to the included document paths. Record a SHA-256 for
the exact bundle distributed to the author. Explain the fixture format and
preflight boundary without examples adapted from existing benchmark cases.

The author works from that bundle alone and must avoid prior benchmark
questions, candidate outputs, traces, repair diagnostics and M4C findings.
Give the author the bundle outside the Argus repository so benchmark files
and evaluation notes are outside their working context. Ask about prior
exposure before assigning the work. Record any exposure or uncertainty.

The author should write approximately 20–30 novel, sanitized MPML launch
questions, with a mix of ordinary phrasing and precise technical requests.
Vary sentence structure and specificity. Consider precedence and CLI/env
placement, ordered and multiple selections, role assignments, negation,
defaults, invalid or contradictory requests, and genuinely missing
information. Include unsupported actions and cases where preflight cannot
establish an experiment outcome, artifact loading, or DL activation. Choose
cases for their relevance to real use. Avoid a quota based on the previous
failure taxonomy. Keep market data, credentials and private paths out of the
fixture. No question requires executing a launch command.

A separate reviewer checks the gold against the pinned spec and authoritative
preflight contract before freezing. Check option spelling, placement,
multiplicity and order, legitimate equivalents, expected diagnostic codes,
and which outcomes should withhold a command. Confirm that extracted spans
point to the original text and that ambiguity is documented. The reviewer
may use the existing read-only preflight to verify exact settings. Actual
experiments and model evaluation are outside this review. Independently
record the reviewer’s role, any prior exposure, and unresolved uncertainty.

Use stable author and reviewer handles or names. Record what each person
could see and when. A loader can check required metadata and distinct
handles. Genuine independence depends on the actual authoring and review
process. When blinding cannot be established, register the fixture as
`development-vN` and record the limitation.

## Fixture contract

Select a dataset by ID. `baseline-v1` is the historical default.
Additional fixtures are registered in
`eval/generation/fixtures/<dataset-id>.json`. IDs use `holdout-vN` or
`development-vN` with a positive version number. The runner accepts IDs
only and refuses symlinked fixture directories and files.

| Field | Contract |
| --- | --- |
| `fixture_id` | Matches the selected file stem. Required for new fixtures. |
| `version` | Nonempty fixture version string. Use a new version for every frozen revision. |
| `mpml_sha` | Full lowercase MPML commit SHA. Runs require a clean source at this revision. |
| `provenance.classification` | `blinded_holdout` for `holdout-vN`, or `development` for `development-vN`. |
| `provenance.author`, `provenance.reviewer` | Nonempty names or stable handles. Author and reviewer handles must be distinct. |
| `provenance.author_independence`, `provenance.reviewer_independence` | Nonempty text describing how independence was established, or disclosing exposure and limitations. |
| `provenance.source_bundle_sha256`, `provenance.spec_sha256` | Lowercase SHA-256 of the distributed bundle and canonical published spec JSON, respectively. Runs verify the live spec hash. |
| `cases` | Nonempty list of case objects. Each has a unique nonempty `id`, original nonempty `question` of at most 4,000 characters, and nonempty `expected` alternatives. |
| `cases[].expected[]` | Each alternative declares `verification` as `validated`, `validated_with_warnings`, `rejected`, or `abstained`, plus a string list of `diagnostic_codes`. Candidate alternatives include ordered `argv` strings and an `env` map of string overrides. Omit both for an abstention without preflight and use an empty diagnostic list. |
| `cases[].constraints` | Optional annotation list. Each entry has `channel` (`argv` or `env`), `target`, `operator`, string `values`, and `span` as two integer, zero-based, half-open character offsets into the original question. |
| `cases[].human_adjudication` | Optional nonempty notes for a human reviewer on ambiguity, acceptable reasoning or why a disposition needs review. |

The existing scorer consumes only the gold alternatives. Constraint annotations
and human notes support review and are kept separate from automated scoring.
List materially equivalent candidates as alternatives when the existing
normalization does not cover them. Preserve argument order where required.
Diagnostic order is immaterial and code multiplicity is preserved. The
historical fixture retains its original schema and contents.

## Freeze and evaluate

1. Finish the questions, alternatives, diagnostic codes, annotations and human
   notes. Complete independent gold review and record provenance.
2. Register a fresh fixture ID and version. Compute the SHA-256 of the exact
   JSON bytes with `sha256sum eval/generation/fixtures/<dataset-id>.json`.
   Record that digest, the version and the source bundle identity in the
   review record. Commit the fixture before exposing it to either model arm.
3. Run both workflow arms with the same fixture ID, frozen bytes and selected
   case IDs, using separate run IDs. Use consistent source, index and model
   settings. Retain coverage and provenance differences with the results.
4. If results expose a label or wording issue, preserve the original fixture
   and reports. Register a new fixture ID and version, repeat gold review where
   needed, record the reason for the change and digest, and report a separate
   evaluation. Access to earlier outputs informs the affected revision’s
   independence classification.

Holdout results describe the frozen set and recorded configuration. Preflight
can establish launch-surface validity. Full intent, runtime success, DL
activation and artifact loading remain outside what the benchmark can prove.
