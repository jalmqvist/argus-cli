"""Build and query a local index of MPML's published launch references."""

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Plus

from argus_cli import ollama
from argus_cli.adapters.mpml import spec
from argus_cli.config import Source
from argus_cli.provenance import revision, spec_sha256

INDEX = Path("indexes/mpml.json")
MODES = ("lexical", "embedding", "hybrid", "all")
_SPEC_LABELS = {
    "arguments": "flags",
    "env": "name",
    "precedence": "setting",
    "rules": "code",
    "source_edit_only": "name",
}
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_TOKEN = re.compile(r"--[\w]+(?:-[\w]+)*|[\w]+(?:-[\w]+)*")


class RetrievalError(RuntimeError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _markdown_sections(text: str):
    headings: list[tuple[int, str]] = []
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        marker = _FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
        elif marker:
            fence = marker[1]
        else:
            heading = _HEADING.match(line)
            if heading:
                if headings or any(line.strip() for line in lines):
                    yield (
                        " / ".join(title for _, title in headings) or "(preamble)",
                        "\n".join(lines).strip(),
                    )
                level = len(heading[1])
                title = re.sub(r"[ \t]+#+$", "", heading[2]).strip()
                while headings and headings[-1][0] >= level:
                    headings.pop()
                headings.append((level, title))
                lines = []
                continue
        lines.append(line)
    if headings or any(line.strip() for line in lines):
        yield " / ".join(title for _, title in headings) or "(preamble)", "\n".join(lines).strip()


def _snapshot(source: Source) -> tuple[dict, list[dict], dict]:
    before = revision(source.root)
    document = spec(source).document
    sections = []
    try:
        for section, key in _SPEC_LABELS.items():
            for entry in document[section]:
                label = entry[key]
                if key == "flags":
                    label = ", ".join(label) or entry["dest"]
                sections.append(
                    ("mpml/spec.py", f"{section} / {label}", json.dumps(entry, sort_keys=True))
                )
        for name, registry in sorted(document["registries"].items()):
            sections.append(
                ("mpml/spec.py", f"registries / {name}", json.dumps(registry, sort_keys=True))
            )
    except (KeyError, TypeError, AttributeError) as exc:
        raise RetrievalError("MPML returned an incomplete schema v1 spec") from exc

    root = source.root.resolve()
    documents = {}
    for name in source.documents:
        relative = Path(name)
        path = (root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix.lower() != ".md"
            or not path.is_relative_to(root)
        ):
            raise RetrievalError(f"Expected a Markdown path inside the MPML checkout: {name!r}")
        name = relative.as_posix()
        if name in documents:
            continue
        raw = path.read_bytes()
        documents[name] = hashlib.sha256(raw).hexdigest()
        sections.extend(
            (name, heading, body) for heading, body in _markdown_sections(raw.decode("utf-8"))
        )

    if revision(source.root) != before:
        raise RetrievalError(
            "MPML source changed while reading it; retry when the checkout is stable"
        )
    metadata = {
        "repo": source.name,
        "root": str(root),
        "interpreter": str(source.python),
        "git_sha": before.sha,
        "dirty": before.dirty,
        "spec_sha256": spec_sha256(document),
        "documents": documents,
    }
    chunks = []
    occurrences: Counter[tuple[str, str]] = Counter()
    for path, heading, body in sections:
        occurrences[path, heading] += 1
        chunks.append(
            {
                "id": _digest([source.name, path, heading, occurrences[path, heading]]),
                "text": body,
                "citation": {
                    "repo": source.name,
                    "path": path,
                    "heading": heading,
                    "git_sha": before.sha,
                    "dirty": before.dirty,
                },
            }
        )
    if not chunks:
        raise RetrievalError("MPML spec and references produced no chunks")
    return metadata, chunks, document


def _search_text(chunk: dict) -> str:
    return f"{chunk['citation']['heading']}\n{chunk['text']}"


def _unit_vectors(vectors: list, count: int) -> np.ndarray:
    try:
        matrix = np.asarray(vectors, dtype=float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise RetrievalError("Invalid embedding matrix") from exc
    if matrix.ndim != 2 or matrix.shape[0] != count or not matrix.shape[1]:
        raise RetrievalError("Unexpected embedding matrix dimensions")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or (norms == 0).any():
        raise RetrievalError("Embeddings must be finite and nonzero")
    return matrix / norms


def build(source: Source, model: str | None) -> dict:
    metadata, chunks, _ = _snapshot(source)
    embeddings = None
    if model is not None:
        digest = ollama.model_digest(model)
        vectors = ollama.embed(model, [_search_text(chunk) for chunk in chunks])
        _unit_vectors(vectors, len(chunks))
        if ollama.model_digest(model) != digest:
            raise RetrievalError("Ollama model changed during indexing; retry argus index")
        embeddings = {"model": model, "digest": digest, "vectors": vectors}
        if _snapshot(source)[0] != metadata:
            raise RetrievalError("MPML source changed during indexing; retry argus index")

    document = {"version": 1, "source": metadata, "chunks": chunks, "embeddings": embeddings}
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=INDEX.parent, delete=False
    ) as pending:
        try:
            json.dump(document, pending, allow_nan=False)
            pending.close()
            os.replace(pending.name, INDEX)
        finally:
            Path(pending.name).unlink(missing_ok=True)
    return {
        "index": str(INDEX),
        "chunks": len(chunks),
        "embedding_model": model,
        "source": metadata,
    }


def _lexical(chunks: list[dict], query: str) -> list[int]:
    # Keep exact option and environment tokens alongside their component words.
    def tokens(text: str) -> list[str]:
        words = _TOKEN.findall(text.casefold())
        parts = [
            part for word in words for part in re.split(r"[-_]+", word) if part and part != word
        ]
        return words + parts

    corpus = [tokens(_search_text(chunk)) for chunk in chunks]
    query_tokens = set(tokens(query))
    matches = [i for i, words in enumerate(corpus) if query_tokens.intersection(words)]
    if not matches:
        return []
    scores = BM25Plus(corpus).get_scores(sorted(query_tokens))
    return sorted(matches, key=lambda i: (-scores[i], chunks[i]["id"]))


def _embedding(chunks: list[dict], query: str, embeddings: dict | None) -> list[int]:
    if embeddings is None:
        raise RetrievalError("No stored embeddings; run argus index --embed MODEL")
    if not isinstance(embeddings, dict) or not (
        isinstance(embeddings.get("model"), str)
        and isinstance(embeddings.get("digest"), str)
        and isinstance(embeddings.get("vectors"), list)
    ):
        raise RetrievalError("Invalid stored embeddings; rebuild with argus index --embed MODEL")
    model = embeddings["model"]
    if ollama.model_digest(model) != embeddings["digest"]:
        raise RetrievalError("Indexed Ollama model changed; rebuild with argus index --embed MODEL")
    matrix = _unit_vectors(embeddings["vectors"], len(chunks))
    vector = _unit_vectors(ollama.embed(model, [query]), 1)
    if vector.shape[1] != matrix.shape[1]:
        raise RetrievalError(
            "Query embedding dimensions differ from the index; rebuild with argus index"
        )
    if ollama.model_digest(model) != embeddings["digest"]:
        raise RetrievalError(
            "Ollama model changed during retrieval; rebuild with argus index --embed MODEL"
        )
    scores = matrix @ vector[0]
    return sorted(range(len(chunks)), key=lambda i: (-scores[i], chunks[i]["id"]))


def retrieve(source: Source, query: str, mode: str, limit: int) -> dict:
    report, _, _ = retrieve_context(source, query, mode, limit)
    return report


def source_matches(source: Source, metadata: dict) -> bool:
    return _snapshot(source)[0] == metadata


def retrieve_context(source: Source, query: str, mode: str, limit: int) -> tuple[dict, dict, dict]:
    """Return rankings with the live source metadata and spec used to verify the index."""
    try:
        document = json.loads(INDEX.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError) as exc:
        raise RetrievalError("Missing or unreadable index; run argus index") from exc
    if not isinstance(document, dict) or document.get("version") != 1:
        raise RetrievalError("Unsupported index format; rebuild with argus index")
    try:
        metadata, chunks, spec_document = _snapshot(source)
    except (OSError, UnicodeError) as exc:
        raise RetrievalError(
            f"Cannot verify current MPML evidence; check the source and rebuild with argus index: {exc}"
        ) from exc
    if document.get("source") != metadata or document.get("chunks") != chunks:
        raise RetrievalError("MPML index is stale; rebuild with argus index")

    rankings = {}
    if mode != "embedding":
        rankings["lexical"] = _lexical(chunks, query)
    if mode != "lexical":
        rankings["embedding"] = _embedding(chunks, query, document.get("embeddings"))
    if mode in {"all", "hybrid"}:
        scores: Counter[int] = Counter()
        for ranks in rankings.values():
            for rank, index in enumerate(ranks, start=1):
                scores[index] += 1 / (60 + rank)
        rankings["hybrid"] = sorted(scores, key=lambda i: (-scores[i], chunks[i]["id"]))
    selected = rankings if mode == "all" else {mode: rankings[mode]}
    report = {
        "query": query,
        "results": {name: [chunks[i] for i in ranks[:limit]] for name, ranks in selected.items()},
    }
    return report, metadata, spec_document
