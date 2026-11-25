"""Score the frozen real-MPML retrieval set with the existing Argus CLI."""

import hashlib
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

DATASET = Path(__file__).with_name("questions.json")
INDEX = Path("indexes/mpml.json")
MODES = ("lexical", "embedding", "hybrid")
LIMIT = 5


def citation_key(citation):
    return citation["path"], citation["heading"]


def benchmark():
    dataset_bytes = DATASET.read_bytes()
    dataset = json.loads(dataset_bytes)
    index_bytes = INDEX.read_bytes()
    index = json.loads(index_bytes)
    source = index["source"]
    embeddings = index["embeddings"]
    if source["git_sha"] != dataset["mpml_sha"] or source["dirty"]:
        raise ValueError("Build the index from the dataset's clean, pinned MPML checkout")
    if embeddings is None:
        raise ValueError("Build an embedding index with argus index --embed nomic-embed-text")

    questions = dataset["questions"]
    available = {citation_key(chunk["citation"]) for chunk in index["chunks"]}
    expected = {
        item["id"]: {citation_key(label) for label in item["expected"]} for item in questions
    }
    if not questions or len(expected) != len(questions):
        raise ValueError("The question set must be nonempty and have unique IDs")
    for question_id, labels in expected.items():
        if not labels or not labels <= available:
            raise ValueError(
                f"Missing indexed labels for {question_id}: {sorted(labels - available)}"
            )

    with build_opener(ProxyHandler({})).open(
        "http://127.0.0.1:11434/api/version", timeout=10
    ) as response:
        ollama_version = json.load(response)["version"]
    ranks = {}
    for question in questions:
        query_id = question["id"]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "argus_cli",
                "retrieve",
                "--mode",
                "all",
                "--limit",
                str(LIMIT),
                "--",
                question["query"],
            ],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
            timeout=180,
        )
        rankings = json.loads(result.stdout)["results"]
        if INDEX.read_bytes() != index_bytes:
            raise ValueError("Index changed during the benchmark; rerun with a stable index")
        ranks[query_id] = {
            mode: next(
                (
                    i
                    for i, chunk in enumerate(rankings[mode], 1)
                    if citation_key(chunk["citation"]) in expected[query_id]
                ),
                None,
            )
            for mode in MODES
        }

    return {
        "dataset": dataset["version"],
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "questions": len(questions),
        "source": {
            key: source[key] for key in ("repo", "git_sha", "dirty", "spec_sha256", "documents")
        },
        "index": {"format": index["version"], "chunks": len(index["chunks"])},
        "retrieval": {
            "lexical": "BM25+",
            "embedding": "cosine similarity",
            "hybrid": "reciprocal rank fusion (k=60)",
            "limit": LIMIT,
            "argus_retrieval_commit": subprocess.check_output(
                ["git", "log", "-1", "--format=%H", "--", "src/argus_cli/retrieval.py"], text=True
            ).strip(),
            "python": platform.python_version(),
            "numpy": version("numpy"),
            "rank_bm25": version("rank-bm25"),
        },
        "ollama": {
            "version": ollama_version,
            "model": embeddings["model"],
            "digest": embeddings["digest"],
        },
        "hits": {
            mode: {
                f"hit@{k}": sum(row[mode] is not None and row[mode] <= k for row in ranks.values())
                for k in (1, LIMIT)
            }
            for mode in MODES
        },
        "first_relevant_rank": ranks,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(benchmark(), indent=2))
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Retrieval benchmark failed: {exc}")
