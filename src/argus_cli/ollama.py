"""Embedding and model metadata calls to the local Ollama instance."""

import json
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

LOCAL_URL = "http://127.0.0.1:11434"


class EmbeddingError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"{LOCAL_URL}/api/{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=60) as response:
            result = json.load(response)
    except (URLError, OSError, ValueError) as exc:
        raise EmbeddingError(f"Local Ollama /api/{path} failed: {exc}") from exc
    if not isinstance(result, dict):
        raise EmbeddingError(f"Local Ollama /api/{path} returned an invalid response")
    return result


def model_digest(model: str) -> str:
    name = model if ":" in model.rsplit("/", 1)[-1] else f"{model}:latest"
    if name.endswith(("-cloud", ":cloud")) or "-cloud:" in name or "://" in name:
        raise EmbeddingError("Ollama cloud models are unsupported")
    models = _request("tags").get("models")
    if isinstance(models, list):
        for entry in models:
            if isinstance(entry, dict) and entry.get("name") == name:
                if entry.get("remote_host") or entry.get("remote_model"):
                    raise EmbeddingError("Ollama cloud models are unsupported")
                digest = entry.get("digest")
                if isinstance(digest, str) and digest:
                    return digest
    raise EmbeddingError(f"Ollama model {name!r} is unavailable; pull it locally first")


def embed(model: str, texts: list[str]) -> list:
    vectors = []
    for start in range(0, len(texts), 32):
        batch = texts[start : start + 32]
        response = _request("embed", {"model": model, "input": batch, "truncate": False})
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(batch):
            raise EmbeddingError("Ollama returned the wrong number of embeddings")
        vectors.extend(embeddings)
    return vectors
