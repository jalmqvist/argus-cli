# Real MPML retrieval benchmark

The frozen [v1 question set](questions.json) contains 20 questions written from the
published MPML spec and configured reference documents. It covers exact flags and
environment variables, paraphrased launch questions, diagnostics, and architecture
details. A question scores a hit if any labeled path and heading appears in the
first 1 or 5 results. Labels include both structured spec entries and reference
sections when either supplies the expected evidence.

## Recorded results

The [recorded run](results-v1.json) used 139 chunks from a clean MPML checkout and
`nomic-embed-text` served by Ollama 0.40.18 on CPU.

| Ranking | Hit@1 | Hit@5 |
| --- | ---: | ---: |
| BM25+ | 14/20 | 20/20 |
| Embedding cosine | 15/20 | 18/20 |
| Hybrid | 18/20 | 20/20 |

Hybrid placed relevant evidence first on four more questions than BM25+.
Embedding-only retrieval missed the repeated-strategy and preflight artifact-loading
questions in its top five. Both were recovered by hybrid at rank 3.

## Reproduce

Use an Argus Python 3.12 environment and a separate MPML checkout and interpreter.
Check out MPML commit `14ad36e3f70a10bb5781b88200e825a717ca402f` with a clean worktree
and verify `python -m mpml.spec` works in the MPML environment. The recorded run
used Python 3.12.14, NumPy 2.5.5, pandas 3.1.1, and ta 0.11.0 for the MPML spec.
Start local Ollama on port 11434. From the Argus repo root with its virtual
environment active and `MPML_REPO` and `MPML_PYTHON` configured, run:

```bash
ollama pull nomic-embed-text
argus index --embed nomic-embed-text
python eval/retrieval/benchmark.py
```

The runner validates that every label exists in the index and compares lexical,
embedding, and hybrid rankings from the same `argus retrieve --mode all` call
for each question. It exits with an error on missing evidence or a failed
retrieval call. Its JSON includes aggregate hit counts, first relevant ranks,
the dataset hash, source and document hashes, retrieval configuration, and the
Ollama version and model digest. Compare the digest to the recorded run when
reproducing it because model tags can change.

This benchmark measures retrieval over the pinned MPML snapshot. Broad reference
sections can count as hits and the set is small, so the scores primarily help
identify where ranking modes differ on these questions. Recipe generation and
preflight outcomes have their own evaluations.
