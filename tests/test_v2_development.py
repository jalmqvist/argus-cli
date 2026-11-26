import json
import os
import subprocess
from dataclasses import asdict
from unittest.mock import Mock

import pytest
from test_v2_live_validation import live as fixed_live
from test_v2_workflow import response

from argus_cli import v2_workflow
from argus_cli.provenance import Revision, spec_sha256
from argus_cli.v2_intent import Vocabulary, _candidate_values
from argus_cli.v2_workflow import FirstProposal
from eval.m4v2 import run_development as development

live = fixed_live


def proposal(argv=(), env=(), retrieved=(), cited=()):
    return FirstProposal(
        "recipe", tuple(argv), tuple(env), tuple(retrieved), tuple(cited), 0, False
    )


@pytest.mark.parametrize(
    ("values", "issues", "policy", "outcome"),
    [
        ({"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"]}, [], None, "correct"),
        ({"--strategy": ["MR32", "TF4"], "EXPERIMENT_SEED": ["57"]}, [], None, "incorrect"),
        ({"--strategy": ["TF4", "MR32"], "--experiment-seed": ["57"]}, [], None, "incorrect"),
        ({"--strategy": ["TF4", "MR32"]}, [], None, "incorrect"),
        (
            {"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"], "ACTIVE_PAIRS": ["EURJPY"]},
            [],
            None,
            "incorrect",
        ),
        (
            {"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"]},
            ["invented option"],
            None,
            "incorrect",
        ),
        (
            {"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"]},
            ["invalid exact value"],
            "invalid_exact",
            "exact_invalid_request",
        ),
        (
            {"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"]},
            [],
            "invalid_exact",
            "needs_manual_review",
        ),
    ],
)
def test_candidate_grade_is_independent_of_preflight(values, issues, policy, outcome):
    case = {
        "expected": {
            "proposal": policy,
            "alternatives": [{"--strategy": ["TF4", "MR32"], "EXPERIMENT_SEED": ["57"]}],
        }
    }
    trace = {"preflight_outcome": "accepted", "recipe_withheld": True}
    assert development.grade(case, proposal(), values, issues, trace)["outcome"] == outcome


def test_no_proposal_distinguishes_informational_and_unresolved():
    assert (
        development.grade({"expected": {"proposal": "not_applicable"}}, None, {}, [], {})["outcome"]
        == "not_applicable"
    )
    assert (
        development.grade(
            {"expected": {"alternatives": [{"--strategy": ["MR32"]}]}}, None, {}, [], {}
        )["outcome"]
        == "needs_manual_review"
    )


def test_private_artifact_filters_unrestricted_proposal_values():
    record = development.candidate_record(
        proposal(
            [
                "--strategy=MR32",
                "--output-dir",
                "/private/path",
                "--experiment-seed",
                "555",
                "--arbitrary=secret",
            ],
            [
                ("EXPERIMENT_VARIANT", "B"),
                ("ACTIVE_PAIRS", "EURJPY, USDJPY"),
                ("API_KEY", "secret"),
                ("EXPERIMENT_SEED", "secret"),
            ],
        )
    )
    assert record["argv"][0] == "--strategy=MR32"
    assert "555" in record["argv"]
    assert record["env"] == {
        "EXPERIMENT_VARIANT": "B",
        "ACTIVE_PAIRS": "EURJPY, USDJPY",
        "EXPERIMENT_SEED": "[redacted]",
    }
    assert "/private/path" not in json.dumps(record)
    assert "secret" not in json.dumps(record)
    assert "API_KEY" not in json.dumps(record)


def test_private_location_and_exclusive_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(development, "ROOT", tmp_path / "argus")
    (tmp_path / "argus").mkdir()
    with pytest.raises(development.DevelopmentError, match="outside the Argus checkout"):
        development.private_directory(tmp_path / "argus" / "private")
    repository = tmp_path / "other-git"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    with pytest.raises(development.DevelopmentError, match="outside Git worktrees"):
        development.private_directory(repository / "private")
    directory = development.private_directory(tmp_path / "private")
    assert directory.stat().st_mode & 0o777 == 0o700
    path = directory / "x"
    development.private_write(path, "review")
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        development.private_write(path, "overwrite")
    symlink = directory / "symlink"
    symlink.symlink_to(path)
    with pytest.raises(FileExistsError):
        development.private_write(symlink, "overwrite")
    os.chmod(directory, 0o755)
    with pytest.raises(development.DevelopmentError, match="permissions"):
        development.private_write(directory / "another", "review")
    assert path.read_text() == "review"


def test_evidence_audit_separates_missing_retrieval_missing_citation_and_policy(live):
    source, spec, _ = live
    _, index, metadata = development._snapshot(source)
    strategy = next(
        chunk["id"]
        for chunk in index["chunks"]
        if chunk["citation"]["heading"] == "arguments / --strategy"
    )
    seed = next(
        chunk["id"]
        for chunk in index["chunks"]
        if chunk["citation"]["heading"] == "arguments / --experiment-seed"
    )
    case = {"question": "Use strategy TF40 with seed 57."}
    values, _ = _candidate_values(
        ["--strategy", "TF40", "--experiment-seed", "57"], {}, Vocabulary.from_spec(spec)
    )
    for retrieved in ((seed,), (strategy, seed)):
        item = proposal(retrieved=retrieved, cited=(seed,))
        audit = development.evidence_audit(case, item, index, metadata, spec, values)
        strategy_info = audit["settings"]["--strategy"]
        assert strategy_info["value_supported_in_index"]
        assert strategy_info["value_supported_in_retrieval"] == (strategy in retrieved)
        assert not strategy_info["value_supported_in_citations"]
        seed_info = audit["settings"]["--experiment-seed"]
        assert seed_info["records_cited"] == 1
        assert not seed_info["value_supported_in_index"]


@pytest.fixture
def local_benchmark(live, tmp_path, monkeypatch):
    source, spec, _ = live
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "version": "test",
                "mpml_sha": "revision-a",
                "spec_sha256": spec_sha256(spec),
                "cases": [
                    {
                        "id": "strategy-seed",
                        "category": "configuration",
                        "question": "Use strategy TF40 with seed 57.",
                        "expected": {
                            "answer": "Explain proposal findings.",
                            "alternatives": [{"--strategy": ["TF40"], "--experiment-seed": ["57"]}],
                        },
                    }
                ],
            }
        )
    )
    config = tmp_path / "sources.yaml"
    config.write_text("test fixture")
    monkeypatch.setattr(development, "FIXTURE", fixture)
    monkeypatch.setattr(development, "load_sources", lambda _: {"mpml": source})
    monkeypatch.setattr(development, "model_digest", lambda _: "test-digest")
    monkeypatch.setattr(development, "revision", lambda _: Revision("argus-test", False))

    def directory(path):
        path.mkdir(mode=0o700)
        return path

    # The C1 fixture mocks subprocess.run globally, including Git's location probe.
    monkeypatch.setattr(development, "private_directory", directory)
    for row in spec["env"]:
        monkeypatch.delenv(row["name"], raising=False)
    monkeypatch.setenv("TEST_CREDENTIAL", "inherited-secret-value")

    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        return response(evidence), "test-digest"

    model = Mock(side_effect=generate)
    monkeypatch.setattr(v2_workflow, "generate", model)
    return config, tmp_path / "out", model


def test_local_runner_invokes_actual_workflow_once_and_writes_private_artifacts(local_benchmark):
    config, directory, model = local_benchmark
    assert development.benchmark(config, directory) == directory
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["full_fixture"]
    assert manifest["model_digest"] == "test-digest"
    assert asdict(development.GenerationSettings()) == manifest["settings"]
    results = json.loads((directory / "results.json").read_text())
    assert results["complete"]
    (row,) = results["cases"]
    assert row["candidate_grade"]["outcome"] == "correct"
    assert row["workflow"]["model_calls"] == model.call_count == 1
    assert row["workflow"]["preflight_outcome"] == "accepted"
    assert row["workflow"]["recipe_released"] is False
    assert results["latency"]["End-to-end"]["count"] == 1
    assert "unresolved" in (directory / "findings.md").read_text()
    candidate = directory / "candidate-strategy-seed.json"
    assert json.loads(candidate.read_text())["argv"] == [
        "--strategy",
        "TF40",
        "--experiment-seed",
        "57",
    ]
    for artifact in directory.iterdir():
        contents = artifact.read_text()
        assert artifact.stat().st_mode & 0o777 == 0o600
        assert "MODEL_PRIVATE_PROSE" not in contents
        assert "inherited-secret-value" not in contents
        if artifact != candidate:
            assert '"argv"' not in contents


def test_candidate_recording_failure_stops_before_preflight(local_benchmark, live, monkeypatch):
    config, directory, model = local_benchmark
    original = development.private_write

    def write(path, content):
        if path.name.startswith("candidate-"):
            raise PermissionError("private write failed")
        original(path, content)

    monkeypatch.setattr(development, "private_write", write)
    with pytest.raises(PermissionError):
        development.benchmark(config, directory)
    assert model.call_count == 1
    live[2].assert_not_called()
    assert not (directory / "results.json").exists()


def test_runner_scores_wrong_strategy_incorrect_even_when_preflight_accepts(local_benchmark):
    config, directory, model = local_benchmark

    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        return response(
            evidence, argv=["--strategy", "MR70", "--experiment-seed", "57"]
        ), "test-digest"

    model.side_effect = generate
    development.benchmark(config, directory, ["strategy-seed"])
    (row,) = json.loads((directory / "results.json").read_text())["cases"]
    assert row["workflow"]["preflight_outcome"] == "accepted"
    assert row["candidate_grade"]["outcome"] == "incorrect"
    assert row["candidate_grade"]["mismatched"] == ["--strategy"]
