# argus-cli

Local, privacy-preserving, **read-only** research CLI assistant. An MPML-first portfolio
project demonstrating deterministic tool integration, local LLMs, structured generation,
RAG, validation and measured agent reliability.

**Current state:** deterministic MPML lookup, preflight, and local retrieval. Argus reads the
published MPML spec from your checkout and can check a default launch candidate.

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
export MPML_REPO=/absolute/path/to/market-phase-ml
export MPML_PYTHON=/absolute/path/to/market-phase-ml/.venv/bin/python
argus doctor
argus spec
argus preflight -- --strategy MR32 --behavioral-surface trend_vol
argus preflight --env DL_SIGNALS_ENABLED=1 -- --strategy MR32
python -m pytest -q
```

MPML is not a pip dependency: the bridge uses MPML's own interpreter and the repo root
as the subprocess working directory. No experiment commands are executed.

## Look up MPML settings

```bash
argus inspect --strategy
argus inspect EXPERIMENT_VARIANT
argus explain precedence
argus explain experiment_variant
argus explain warnings
argus explain strategies
argus recipe defaults
```

`inspect` matches exact flag spellings and environment variable names. It prints the
published parameter record, including its default, any structured choices or post-parse
choices, and matching precedence entries. Environment choices and alias behavior may
appear in the published semantics text. The flag default is the parser default. Consult
precedence and environment semantics for runtime fallbacks.

`explain` also accepts an exact flag, environment variable, precedence setting, or preflight
issue code. The `warnings` topic lists the published diagnostic summaries, including
potential errors. Actual findings come from preflight. Lookup reports include the MPML
checkout SHA, dirty state, interpreter, schema version, and canonical spec SHA-256.

`recipe defaults` proposes an empty argument list with no environment overrides and
runs MPML preflight using the inherited process environment. The JSON includes the working
directory, interpreter, entrypoint, arguments, overrides, findings, and verification
status. `validated` and `validated_with_warnings` describe the preflight result.
`rejected` and `unverified` return a nonzero status. For a custom candidate, use
`argus preflight --env KEY=VALUE -- <MPML args>`.

## Retrieve cited MPML evidence

```bash
argus index
argus retrieve "What takes precedence over EXPERIMENT_VARIANT?"
argus retrieve -- --strategy
```

`argus index` reads the live spec and the Markdown paths in `sources.mpml.documents` in
`sources.yaml`. It writes `indexes/mpml.json` relative to the working directory.
The index is gitignored and contains the selected source text. Build and query it from
the same working directory. Each hit includes a stable chunk ID, the source text, and a
citation with the repository key, relative path, heading, Git SHA, and dirty state.
Spec headings identify schema entries. Markdown sections use hash-prefixed headings.

Lexical retrieval uses BM25+ and preserves exact flag and environment tokens as well
as their component words. To compare it with cosine similarity and reciprocal rank
fusion, start Ollama on the default loopback port and use a locally installed embedding model.

```bash
ollama pull nomic-embed-text
argus index --embed nomic-embed-text
argus retrieve --mode embedding "How do artifact path overrides work?"
argus retrieve --mode hybrid "How do artifact path overrides work?"
argus retrieve --mode all "How do artifact path overrides work?"
```

`--mode all` returns the three ranked lists for the same query. Each list defaults to
five results. Only `argus index` writes the artifact or embeds the corpus. Embedding,
hybrid, and ablation queries send one query embedding request to the local Ollama
instance. Argus checks the stored model digest before using those vectors.

Retrieval checks the live Git SHA and dirty state, the spec hash, and the selected
Markdown hashes before returning hits. A changed revision or evidence file requires
rebuilding with `argus index`, including `--embed MODEL` if using embedding modes.
A dirty checkout can be indexed, with the dirty state visible in each citation.

### Synthetic hit@5

The held-out fixture contains six questions. A hit means the expected path and
heading appeared among the first five results.

| Ranking | Hit@5 |
| --- | ---: |
| Lexical BM25+ | 5/6 |
| Embedding cosine | 6/6 |
| Hybrid | 6/6 |

The fixture uses a synthetic spec, Markdown, and embedding responses. These scores
measure the retrieval pipeline on the fixture. Live Ollama and MPML retrieval quality
remain unmeasured.

```bash
python -m pytest -q -s tests/test_retrieval.py::test_held_out_hit_at_five
```

## Key repo files

- `PLAN.md`: updated implementation roadmap and evaluation strategy
- `sources.yaml`: source repo bridge configuration (environment-variable expansion)
- `docs/adr/`: architectural decisions
- `docs/prompts/`: Codex implementation prompts
- `src/argus_cli/adapters/mpml.py`: constrained MPML spec/preflight subprocess bridge
- `tests/`: synthetic/mock tests, independent of private repos

## Limitations

- Lookup reports documented settings. It does not resolve the effective value for your
  current environment or infer choices and precedence the spec leaves implicit.
- The only recipe is `defaults`. Inherited settings may affect the candidate, including
  whether it requests DL. Preflight checks the launch surface. Artifact loading,
  DL activation, and experiment success require a separate run.
- Lookup uses the live spec. A dirty checkout means its Git SHA alone cannot identify
  the inspected content.
- The adapter is scoped to MPML's `schema_version: 1`; schema changes require explicit
  review and version handling.
