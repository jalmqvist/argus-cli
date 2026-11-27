# Draft release notes for v0.1.0rc1

Argus CLI is a **read-only developer preview** for researchers and developers
with a local MPML checkout. It provides source-grounded assistance with MPML's
published launch configuration.

- Inspect documented flags, environment variables, defaults, precedence and
  diagnostic codes from the live specification.
- Build a verified local lexical index and retrieve cited specification and
  reference entries.
- Check explicit settings with MPML's read-only preflight interface.
- Use `argus ask --agent-v2` for grounded deterministic answers and qualified
  configuration assessment with at most one local Qwen generation call.

Use Python 3.12, Git and a compatible MPML checkout with its own interpreter.
The `llm` extra enables v2, including deterministic answers. For model-assisted
assessment, run local Ollama with `qwen2.5-coder:7b`. Lexical v2 requires no
embedding model or LangGraph. See the [installation quickstart](../../README.md).

## Recorded local development results

In the paired 14-case developer-authored fixture, five of seven supported
configuration requests produced exact-correct candidates. Two candidate cases
remained incorrect. The local run made nine model attempts with a median
generation latency of approximately **6.80 seconds** on an NVIDIA GTX 1070
with 8 GB VRAM. It released **zero v2 commands**. These are development
measurements. Human usefulness review and independent generalization evidence
are pending. [Paired development findings](../../eval/m4v2/PAIRED_FINDINGS_3C.md)

## Known limitations

- Environment-only requests can produce proposals with incorrect CLI settings.
  `ACTIVE_PAIRS` proposals can omit the requested pair filter.
- Independent complete-intent and aggregate effective-configuration verification
  are incomplete. A preflight-accepted candidate can still be wrong.
- V2 releases no verified manual recipes. Public `command` and `settings` are null.
- Argus performs no experiment execution, artifact loading or broker operations.
- Plain `argus ask` still uses M3. `--agent` selects experimental M4 v1. These
  historical modes have distinct manual-command release behavior.

Next priorities are diagnosing channel and pair-filter errors, human review of
answer usefulness and withholding, a new independent evaluation, and complete
intent verification for a bounded class of requests.

These notes are a draft. See the [release gate and publication procedure](V0_1_0_RC1_ACCEPTANCE.md).
