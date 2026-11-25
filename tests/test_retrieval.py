import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from argus_cli import ollama, retrieval
from argus_cli.cli import main

FIXTURES = Path(__file__).parent / "fixtures/retrieval"


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "toy"
    root.mkdir()
    (root / "mpml").mkdir()
    (root / "mpml/spec.py").write_text(
        "from pathlib import Path\nprint(Path('spec.json').read_text())\n", encoding="utf-8"
    )
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (root / "docs").mkdir()
    shutil.copyfile(FIXTURES / "spec.json", root / "spec.json")
    shutil.copyfile(FIXTURES / "reference.md", root / "docs/reference.md")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "Synthetic source",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MPML_REPO", str(root))
    monkeypatch.setenv("MPML_PYTHON", sys.executable)
    Path("sources.yaml").write_text(
        """schema_version: 1
sources:
  mpml:
    root: ${MPML_REPO}
    python: ${MPML_PYTHON}
    adapter: mpml_v1
    spec_module: mpml.spec
    preflight_module: mpml.preflight
    entrypoint: main.py
    documents: [docs/reference.md]
""",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def fake_ollama(monkeypatch):
    model = {"name": "toy:latest", "digest": "synthetic-v1"}
    calls = []
    # A tiny fixed concept map stands in for the local model in public CI.
    features = [
        ("feed", "archive"),
        ("seed", "random"),
        ("batch", "limit"),
        ("saving", "directory"),
        ("resume", "resuming", "pick up", "checkpoint"),
        ("calendar", "weekend", "saturdays"),
        ("credentials", "token"),
        ("clock", "utc"),
        ("compression", "gzip"),
        ("quiet", "suppress"),
    ]

    def request(path, payload=None):
        calls.append(path)
        if path == "tags":
            return {"models": [model]}
        assert path == "embed"
        assert payload["model"] == "toy"
        assert payload["truncate"] is False
        return {
            "embeddings": [
                [1] + [int(any(term in value.casefold() for term in group)) for group in features]
                for value in payload["input"]
            ]
        }

    monkeypatch.setattr(ollama, "_request", request)
    return model, calls


def test_held_out_hit_at_five(checkout, fake_ollama, capsys):
    assert main(["index", "--embed", "toy"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["source"]["git_sha"] == git(checkout, "rev-parse", "HEAD")
    original = retrieval.INDEX.read_bytes()
    questions = json.loads((FIXTURES / "held_out.json").read_text(encoding="utf-8"))
    hits = dict.fromkeys(("lexical", "embedding", "hybrid"), 0)
    for item in questions:
        assert main(["retrieve", "--mode", "all", item["query"]]) == 0
        results = json.loads(capsys.readouterr().out)["results"]
        assert set(results) == set(hits)
        for mode, chunks in results.items():
            assert len(chunks) <= 5
            hits[mode] += any(
                chunk["citation"]["path"] == item["path"]
                and chunk["citation"]["heading"] == item["heading"]
                for chunk in chunks
            )
    print(f"held-out hit@5 ({len(questions)} queries): {hits}")
    assert hits["lexical"] >= 4
    assert hits["embedding"] >= 5
    assert hits["hybrid"] >= 5
    assert retrieval.INDEX.read_bytes() == original


def test_lexical_uses_exact_token_and_never_calls_ollama(checkout, fake_ollama, capsys):
    _, calls = fake_ollama
    assert main(["index"]) == 0
    capsys.readouterr()
    assert main(["retrieve", "--", "--feed-mode"]) == 0
    match = json.loads(capsys.readouterr().out)["results"]["lexical"][0]
    assert match["citation"] == {
        "repo": "mpml",
        "path": "mpml/spec.py",
        "heading": "arguments / --feed-mode",
        "git_sha": git(checkout, "rev-parse", "HEAD"),
        "dirty": False,
    }
    assert not calls


@pytest.mark.parametrize("change", ["commit", "docs", "spec"])
def test_refuses_source_drift(checkout, change, capsys):
    if change != "commit":
        # Start dirty so an evidence change cannot be detected by the dirty bit alone.
        (checkout / "untracked").touch()
    assert main(["index"]) == 0
    capsys.readouterr()
    if change == "commit":
        git(
            checkout,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "New revision",
        )
    elif change == "docs":
        with (checkout / "docs/reference.md").open("a", encoding="utf-8") as doc:
            doc.write("\nChanged evidence.\n")
    else:
        path = checkout / "spec.json"
        path.write_text(path.read_text().replace("archive", "local"), encoding="utf-8")
    assert main(["retrieve", "feed"]) == 2
    result = capsys.readouterr()
    assert not result.out
    assert "index is stale; rebuild with argus index" in result.err


def test_stable_ids_and_fenced_markdown(checkout):
    assert main(["index"]) == 0
    first = json.loads(retrieval.INDEX.read_text())["chunks"]
    assert not any("shell comment" in chunk["citation"]["heading"] for chunk in first)
    doc = checkout / "docs/reference.md"
    doc.write_text(doc.read_text().replace("save disk space", "reduce file size"))
    assert main(["index"]) == 0
    updated = json.loads(retrieval.INDEX.read_text())["chunks"]
    assert [chunk["id"] for chunk in first] == [chunk["id"] for chunk in updated]
    assert all(chunk["citation"]["dirty"] for chunk in updated)


def test_model_drift_and_failed_build_preserve_index(checkout, fake_ollama, capsys):
    model, calls = fake_ollama
    assert main(["index", "--embed", "toy"]) == 0
    original = retrieval.INDEX.read_bytes()
    capsys.readouterr()
    model["digest"] = "synthetic-v2"
    assert main(["retrieve", "--mode", "embedding", "feed"]) == 2
    assert "model changed" in capsys.readouterr().err
    assert calls.count("embed") == 1
    assert main(["index", "--embed", "missing"]) == 2
    assert retrieval.INDEX.read_bytes() == original
