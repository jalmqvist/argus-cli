import hashlib
import io
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval" / "retrieval"
MODES = {"lexical", "embedding", "hybrid"}
TARGET = {"path": "docs/guide.md", "heading": "Preflight"}
ALTERNATIVE = {"path": "mpml/spec.py", "heading": "rules / EXAMPLE"}
DISTRACTORS = [
    {"path": "docs/other.md", "heading": "Preflight"},
    {"path": "docs/guide.md", "heading": "Setup"},
    {"path": "docs/guide.md", "heading": "Usage"},
    {"path": "docs/guide.md", "heading": "Examples"},
    {"path": "docs/guide.md", "heading": "FAQ"},
]


@pytest.fixture
def benchmark(tmp_path, monkeypatch):
    module_spec = spec_from_file_location("retrieval_benchmark", EVAL_DIR / "benchmark.py")
    runner = module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "DATASET", tmp_path / "questions.json")
    monkeypatch.setattr(runner, "INDEX", tmp_path / "index.json")
    # Validation errors must occur before any network request or subprocess call.
    monkeypatch.setattr(runner, "build_opener", Mock(side_effect=AssertionError("unexpected HTTP")))
    monkeypatch.setattr(
        runner,
        "subprocess",
        SimpleNamespace(
            PIPE=runner.subprocess.PIPE,
            run=Mock(side_effect=AssertionError("unexpected retrieval")),
            check_output=Mock(return_value="fixture-commit\n"),
        ),
    )
    dataset = {
        "version": "fixture-v1",
        "mpml_sha": "fixture-sha",
        "questions": [
            {"id": "first", "query": "first query", "expected": [TARGET, ALTERNATIVE]},
            {"id": "second", "query": "second query", "expected": [TARGET]},
        ],
    }
    index = {
        "version": 1,
        "source": {
            "git_sha": "fixture-sha",
            "dirty": False,
            "repo": "mpml",
            "spec_sha256": "fixture-hash",
            "documents": {},
        },
        "embeddings": {"model": "fixture-model", "digest": "fixture-digest"},
        "chunks": [{"citation": label} for label in [TARGET, ALTERNATIVE, *DISTRACTORS]],
    }
    return runner, dataset, index


def write_inputs(runner, dataset, index):
    runner.DATASET.write_text(json.dumps(dataset), encoding="utf-8")
    runner.INDEX.write_text(json.dumps(index), encoding="utf-8")


def test_benchmark_scores_first_matching_citation(benchmark):
    runner, dataset, index = benchmark
    write_inputs(runner, dataset, index)
    runner.build_opener.side_effect = None
    runner.build_opener.return_value.open.return_value = io.StringIO('{"version": "fixture"}')
    rankings_by_query = [
        {
            "lexical": [TARGET, ALTERNATIVE],
            "embedding": [*DISTRACTORS[:4], ALTERNATIVE],
            "hybrid": DISTRACTORS,
        },
        {
            "lexical": [],
            "embedding": [ALTERNATIVE, TARGET],
            "hybrid": [TARGET],
        },
    ]
    runner.subprocess.run.side_effect = [
        SimpleNamespace(
            stdout=json.dumps(
                {
                    "results": {
                        mode: [{"citation": label} for label in labels]
                        for mode, labels in rankings.items()
                    }
                }
            )
        )
        for rankings in rankings_by_query
    ]

    result = runner.benchmark()

    assert result["questions"] == 2
    assert result["first_relevant_rank"] == {
        "first": {"lexical": 1, "embedding": 5, "hybrid": None},
        "second": {"lexical": None, "embedding": 2, "hybrid": 1},
    }
    assert result["hits"] == {
        "lexical": {"hit@1": 1, "hit@5": 1},
        "embedding": {"hit@1": 0, "hit@5": 2},
        "hybrid": {"hit@1": 1, "hit@5": 1},
    }
    assert [call.args[0][-7:] for call in runner.subprocess.run.call_args_list] == [
        ["retrieve", "--mode", "all", "--limit", "5", "--", item["query"]]
        for item in dataset["questions"]
    ]


@pytest.mark.parametrize(
    ("invalid_input", "message"),
    [
        ("duplicate_id", "unique IDs"),
        ("no_questions", "nonempty"),
        ("absent_evidence", "Missing indexed labels for first"),
        ("no_labels", "Missing indexed labels for first"),
        ("wrong_revision", "clean, pinned MPML checkout"),
        ("dirty_source", "clean, pinned MPML checkout"),
        ("no_embeddings", "Build an embedding index"),
    ],
)
def test_benchmark_rejects_invalid_inputs(benchmark, invalid_input, message):
    runner, dataset, index = benchmark
    if invalid_input == "duplicate_id":
        dataset["questions"][1]["id"] = dataset["questions"][0]["id"]
    elif invalid_input == "no_questions":
        dataset["questions"].clear()
    elif invalid_input == "absent_evidence":
        # Keep one valid label to verify that partial label coverage still fails.
        index["chunks"].remove({"citation": ALTERNATIVE})
    elif invalid_input == "no_labels":
        dataset["questions"][0]["expected"].clear()
    elif invalid_input == "wrong_revision":
        index["source"]["git_sha"] = "different-sha"
    elif invalid_input == "dirty_source":
        index["source"]["dirty"] = True
    elif invalid_input == "no_embeddings":
        index["embeddings"] = None
    write_inputs(runner, dataset, index)

    with pytest.raises(ValueError, match=message):
        runner.benchmark()
    runner.build_opener.assert_not_called()
    runner.subprocess.run.assert_not_called()


def test_recorded_v1_hits_match_per_question_ranks():
    dataset_bytes = (EVAL_DIR / "questions.json").read_bytes()
    dataset = json.loads(dataset_bytes)
    report = json.loads((EVAL_DIR / "results-v1.json").read_bytes())
    ranks = report["first_relevant_rank"]

    assert report["dataset"] == dataset["version"]
    assert report["dataset_sha256"] == hashlib.sha256(dataset_bytes).hexdigest()
    assert report["source"]["git_sha"] == dataset["mpml_sha"]
    assert report["questions"] == len(dataset["questions"]) == len(ranks)
    assert set(ranks) == {item["id"] for item in dataset["questions"]}
    assert set(report["hits"]) == MODES
    for row in ranks.values():
        assert set(row) == MODES
        assert all(rank is None or type(rank) is int and 1 <= rank <= 5 for rank in row.values())
    for mode in MODES:
        mode_ranks = [row[mode] for row in ranks.values()]
        assert report["hits"][mode] == {
            "hit@1": mode_ranks.count(1),
            "hit@5": len(mode_ranks) - mode_ranks.count(None),
        }
