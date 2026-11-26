# M4v2-3A first-attempt development evaluation

The [14-question fixture](first-attempt-development-v1.json) is developer-authored
development data. It covers two informational questions, seven configuration
requests, two invalid exact values, one ambiguous reference and two unsupported
execution requests. It pins the same clean MPML source and spec used for the
prior benchmark. Historical fixtures and reports retain their original meaning.

Gold alternatives are stored separately from question text, which is the only
fixture field sent to the actual v2 workflow. The expected settings were checked
against the pinned MPML CLI/spec source, precedence rows, registered strategy
families and pair-filter behavior independently of model output. This is a
developer source review. A separate human has yet to review the fixture.

## Maintainer-local run

Use the configured clean MPML checkout, a current verified local index,
Argus's `llm` extra, and the installed local `qwen2.5-coder:7b`. Unset inherited
published MPML settings before the run. From the repository root on the
GTX 1070 system:

```sh
python -m eval.m4v2.run_development \
  --config sources.yaml \
  --output "$HOME/argus-m4v2-first-attempt-01"
```

Use an unused directory name whose parent already exists outside Git worktrees.
For a diagnostic subset, add `--case strategy-seed` or repeat `--case` with
other fixture IDs. The manifest and results distinguish a subset from the full
fixture. Runs are sequential, lexical, and use the existing settings and bounded
one-attempt workflow. No experiment, artifact loading or order execution is part
of this procedure.

## Artifacts and grading

- `manifest.json` records fixture/version/hash, selected cases, config hash,
  Argus revision/dirty state, implementation hashes, clean MPML source/spec/index,
  package versions, platform, model digest and generation settings. The runner
  checks source, index and inherited environment across cases and verifies the
  model digest. It omits inherited environment contents.
- `candidate-<case>.json` is available only through the local runner's explicit
  in-process hook. It records the first schema-valid structured proposal before
  later validation. It preserves tokens and overrides for the fixture's narrow
  vocabulary, with unrestricted values redacted and unknown env keys omitted.
  Prompts, model prose, raw diagnostics, private paths and inherited values are
  excluded. The hook has no normal CLI flag. Unsafe paths or failed writes stop
  the run. The runner creates a mode-0700 directory and exclusive mode-0600 files.
- `results.json` records correctness separately from the public v2 workflow's
  validation, evidence, preflight, answer status and release findings. The
  candidate scorer compares the complete explicit settings to a gold alternative.
  Canonical option names and the same parsed representation used by the v2
  intent checker handle split/equal CLI forms and MPML pair normalization.
  CLI and environment channels are distinct, ordered strategy occurrences must
  match exactly, and unexpected settings fail even if preflight accepted. Exact
  requested invalid values are counted separately when structure or MPML rejects
  them. Missing or abstained proposals can require manual review. Withholding a
  command is a separate outcome.
- `findings.md` summarizes candidate grades and preflight counts, with separate
  unresolved review entries for factual answer quality, usefulness and unnecessary
  withholding. Review whether the supported request received a useful answer
  or proposal. Required withholding of an unauthorized command is not
  unnecessary withholding. End-to-end median and nearest-rank p95 include
  completed error and withheld cases. Generation latency uses cases in which
  the workflow recorded an attempted generation stage.

Interrupted runs may leave a manifest and private candidate files. Choose a new
directory when rerunning. Treat only a complete `results.json` as a finished
result and check its selected case set before reporting counts. Keep candidate
artifacts local. No live inference was run for this PR.

## Diagnosing the MR32 and seed case

Inspect `results.json` for `strategy-seed`. Each proposed setting lists its
pinned structured records and whether they were retrieved or cited. Separate
booleans show whether C1's current exact-value support rule succeeds with the
whole index, retrieved records and cited records respectively. If the index
supports the value but retrieval lacks support, retrieval is the gap. If
retrieval supports it but citations do not, citation selection is the gap.
If even the full index does not support it under C1's policy, neither retrieval
nor citation selection alone can fix the gap. In particular, C1's current
integer support rule can leave a non-default seed unsupported even when the
correct seed record was retrieved and cited. This is a diagnostic hypothesis
for the maintainer run, not a measured attribution of the previous smoke result.
Unrelated and unresolved citations are reported without rewriting them.

For M4v2-3B, compare these evidence gaps with human usability and actual
first-attempt correctness. Decide whether any recurring failure justifies
retrieval or evidence-policy changes before considering a repair loop.
