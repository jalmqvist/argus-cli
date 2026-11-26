import argparse
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from eval.generation import baseline, scoring, timed_ask

CITATION = {"id": "spec-id", "path": "mpml/spec.py", "heading": "Strategy", "git_sha": "sha"}
SETTINGS = {
    "temperature": 0.0,
    "seed": 42,
    "num_ctx": 8192,
    "num_predict": 1100,
    "timeout_seconds": 300.0,
}


def gold(argv=("--strategy", "MR32"), env=None, verification="validated", codes=()):
    return {
        "argv": list(argv),
        "env": env or {},
        "verification": verification,
        "diagnostic_codes": list(codes),
    }


def case(*expected, key="fixture"):
    return {"id": key, "question": "Synthetic launch question", "expected": list(expected)}


def report(**changes):
    return {
        "argv": ["--strategy", "MR32"],
        "env": {},
        "verification": "validated",
        "command": "mock command for manual use",
        "preflight": {"issues": []},
        "preflight_validation": "passed",
        "structural_validation": "passed",
        "citations": [CITATION],
        "uncertainty": [],
        "provenance": {"git_sha": "sha", "dirty": False, "spec_sha256": "spec-sha"},
        "model": {"name": "toy", "digest": "model-sha", "settings": SETTINGS},
        "retrieval": {"mode": "hybrid", "limit": 5},
        **changes,
    }


def attempt(reply, error_category=None):
    return {
        "report": reply,
        "generation_seconds": 2 if reply is not None else None,
        "wall_seconds": 4,
        "error_category": error_category,
        "exit_code": 0,
    }


def score(question, reply):
    return scoring.score_case(question, attempt(reply), {"spec-id": CITATION})


@pytest.mark.parametrize("argv", [["--strategy", "MR32"], ["--strategy=MR32"]])
def test_equivalent_recipes(argv):
    result = score(case(gold()), report(argv=argv))
    assert result["outcome"] == "pass"
    assert result["intent_match"] == "match"
    assert result["citations"] == "valid"


def test_allowed_order_only_where_enumerated():
    first = ["--experiment-seed", "123", "--experiment-variant", "A"]
    second = first[2:] + first[:2]
    assert score(case(gold(first), gold(second)), report(argv=second))["outcome"] == "pass"
    result = score(case(gold(first)), report(argv=second))
    assert result["outcome"] == "fail"
    assert result["differences"]["argv_order_mismatch"]


def test_missing_and_extra_settings_even_with_preflight_acceptance():
    result = score(
        case(gold(env={"ACTIVE_PAIRS": "USDJPY"})),
        report(argv=["--strategy", "TF4", "--debug"], env={"EXPERIMENT_SEED": "4"}),
    )
    assert result["intent_match"] == "mismatch"
    assert result["outcome"] == "fail"
    assert result["differences"] == {
        "missing_options": [["--strategy", "MR32"]],
        "unexpected_options": [["--strategy", "TF4"], ["--debug"]],
        "missing_env": {"ACTIVE_PAIRS": "USDJPY"},
        "unexpected_env": {"EXPERIMENT_SEED": "4"},
        "argv_order_mismatch": False,
    }


def test_abstentions_and_reason_review():
    abstain = {"verification": "abstained", "diagnostic_codes": []}
    reply = report(
        verification="abstained",
        argv=[],
        env={},
        command=None,
        citations=[],
        preflight=None,
        preflight_validation="not_run",
        uncertainty=["Unsupported request."],
    )
    accepted = score(case(abstain), reply)
    assert accepted["abstention"] == "correct"
    assert accepted["outcome"] == accepted["intent_match"] == "review"
    assert score(case(gold()), reply)["abstention"] == "incorrect"
    missed = score(case(abstain), report())
    assert missed["abstention"] == "missed"
    assert missed["differences"]["unexpected_options"] == [["--strategy", "MR32"]]
    assert score(case(abstain), {**reply, "uncertainty": []})["abstention"] == "incorrect"
    assert score(case(abstain), {**reply, "argv": ["--debug"]})["outcome"] == "fail"


def test_expected_rejection_requires_the_right_diagnostic():
    abstain = {"verification": "abstained", "diagnostic_codes": []}
    argv = ["--strategy", "ZZ999"]
    question = case(abstain, gold(argv, verification="rejected", codes=["STRATEGY_UNKNOWN"]))
    reply = report(
        argv=argv,
        verification="rejected",
        command=None,
        preflight_validation="failed",
        preflight={"issues": [{"code": "STRATEGY_UNKNOWN"}]},
    )
    assert score(question, reply)["outcome"] == "pass"
    assert score(question, reply)["abstention"] == "alternative"
    reply["preflight"]["issues"][0]["code"] = "OTHER"
    assert score(question, reply)["outcome"] == "fail"
    assert score(question, reply)["abstention"] == "missed"


def test_citations_are_checked_against_index_snapshot():
    result = score(case(gold()), report(citations=[{**CITATION, "heading": "Wrong"}]))
    assert result["outcome"] == "fail"
    assert result["citations"] == "invalid"


@pytest.fixture
def run_data(tmp_path, monkeypatch):
    config = tmp_path / "sources.yaml"
    config.write_text("fixture")
    index = tmp_path / "index.json"
    index.write_text("fixture index")
    monkeypatch.setattr(baseline, "INDEX", index)
    dataset = {"cases": [case(gold(), key=key) for key in ("A", "B", "C")]}
    manifest = {
        "selected": ["A", "B"],
        "dataset_sha256": "fixture-hash",
        "config": str(config),
        "config_sha256": baseline.sha(config.read_bytes()),
        "index_sha256": baseline.sha(index.read_bytes()),
        "indexed_citations": {"spec-id": CITATION},
        "source": report()["provenance"],
        "model": {"name": "toy", "digest": "model-sha"},
        "settings": SETTINGS,
        "retrieval": {"mode": "hybrid", "limit": 5},
        "wall_timeout_seconds": 660,
    }
    return tmp_path / "reports/run.json", manifest, dataset


def test_incremental_resume_skips_completed_attempts(run_data):
    path, manifest, dataset = run_data
    first = Mock(side_effect=[attempt(report()), KeyboardInterrupt])
    with pytest.raises(KeyboardInterrupt):
        baseline.resume_run(path, manifest, dataset, "fixture-hash", first)
    saved = json.loads(path.read_bytes())
    assert saved["summary"]["status"] == "partial"
    assert saved["summary"]["remaining"] == ["B"]
    assert list(saved["attempts"]) == ["A"]

    second = Mock(return_value=attempt(None, "timeout"))
    summary = baseline.resume_run(path, manifest, dataset, "fixture-hash", second)
    assert [call.args[0]["id"] for call in second.call_args_list] == ["B"]
    assert summary["status"] == "complete_subset"
    assert summary["dataset_total"] == 3
    assert summary["outcomes"] == {"pass": 1, "error": 1}
    assert summary["errors"] == {"timeout": 1}
    assert summary["generation_seconds"] == {"samples": 1, "p50": 2, "p95": 2}
    assert summary["wall_seconds"] == {"samples": 2, "p50": 4, "p95": 4}

    finished = Mock(side_effect=AssertionError("repeated attempt"))
    assert baseline.resume_run(path, manifest, dataset, "fixture-hash", finished) == summary
    assert scoring.summarize(json.loads(path.read_bytes()), dataset, "fixture-hash") == summary


@pytest.mark.parametrize(
    "change",
    [
        {"model": {"name": "toy", "digest": "different"}},
        {"source": {"git_sha": "other", "dirty": False, "spec_sha256": "spec"}},
        {"index_sha256": "other"},
        {"selected": ["A"]},
        {"settings": {**SETTINGS, "seed": 1}},
    ],
)
def test_resume_rejects_incompatible_provenance(run_data, change):
    path, manifest, dataset = run_data
    execute = Mock(side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        baseline.resume_run(path, manifest, dataset, "fixture-hash", execute)
    execute.reset_mock()
    with pytest.raises(ValueError, match="Incompatible resume"):
        baseline.resume_run(path, {**manifest, **change}, dataset, "fixture-hash", execute)
    execute.assert_not_called()


def test_full_summary_counts_intent_mismatch_independently(run_data):
    _, manifest, dataset = run_data
    manifest["selected"].append("C")
    run = {
        "manifest": manifest,
        "attempts": {
            "A": attempt(report()),
            "B": attempt(report(argv=["--strategy", "TF4"])),
            "C": attempt(
                report(
                    verification="unverified",
                    argv=None,
                    env=None,
                    command=None,
                    preflight=None,
                    preflight_validation="not_run",
                    structural_validation="not_run",
                    citations=[],
                    error="Local Ollama generation timed out",
                )
            ),
        },
    }
    result = scoring.summarize(run, dataset, "fixture-hash")
    assert result["status"] == "complete_full"
    assert result["intent"] == {"match": 1, "mismatch": 1, "not_scored": 1}
    assert result["preflight_passed_with_wrong_intent"] == 1
    assert result["errors"] == {"timeout": 1}


def test_cli_attempt_errors_are_persistable(run_data, monkeypatch):
    _, manifest, dataset = run_data
    call = Mock(
        side_effect=[
            subprocess.TimeoutExpired("fixture", 660),
            subprocess.CompletedProcess([], 2, "", "setup error"),
            subprocess.CompletedProcess([], 0, "not json", ""),
            subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {
                        "report": report(),
                        "generation_seconds": 2.5,
                    }
                ),
                "",
            ),
        ]
    )
    monkeypatch.setattr(baseline.subprocess, "run", call)
    config = Path(manifest["config"])
    observed = [baseline.attempt_case(dataset["cases"][0], config, manifest) for _ in range(4)]
    assert [row["error_category"] for row in observed] == [
        "timeout",
        "cli_error",
        "invalid_report",
        None,
    ]
    assert observed[-1]["generation_seconds"] == 2.5
    assert observed[-1]["report"]["argv"] == report()["argv"]
    assert "--model" in call.call_args.args[0]
    assert call.call_args.args[0][-1] == dataset["cases"][0]["question"]
    assert call.call_args.kwargs["timeout"] == 660


@pytest.mark.parametrize("workflow", ["single-pass", "agent"])
@pytest.mark.parametrize("fixture", ["baseline-v1", "holdout-v1", "wrong-spec"])
def test_manifest_uses_pinned_index_and_model_metadata(run_data, monkeypatch, workflow, fixture):
    from argus_cli import ollama, retrieval
    from argus_cli import provenance as git_provenance
    from argus_cli.config import Source

    _, manifest, dataset = run_data
    source = Source(
        "mpml",
        Path("/fixture"),
        Path("/fixture/python"),
        "mpml_v1",
        "mpml.spec",
        "mpml.preflight",
        "main.py",
        (),
    )
    source_info = manifest["source"]
    dataset.update(version="fixture-v1", mpml_sha="sha")
    index = {
        "embeddings": {"model": "embed", "digest": "embed-sha"},
        "chunks": [{"id": "spec-id", "citation": {k: v for k, v in CITATION.items() if k != "id"}}],
    }
    baseline.INDEX.write_text(json.dumps(index))
    monkeypatch.setattr("argus_cli.config.load_sources", Mock(return_value={"mpml": source}))
    lookup = Mock(return_value=({}, source_info, {"env": []}))
    monkeypatch.setattr(retrieval, "retrieve_context", lookup)
    monkeypatch.setattr(
        ollama, "model_digest", lambda model: {"toy": "model-sha", "embed": "embed-sha"}[model]
    )
    monkeypatch.setattr(
        ollama,
        "_request",
        lambda path, *_: {"version": "fixture-version"} if path == "version" else {},
    )
    monkeypatch.setattr(
        git_provenance, "revision", lambda _: git_provenance.Revision("argus-sha", False)
    )
    monkeypatch.setattr(baseline, "version", lambda _: "fixture-version")
    args = argparse.Namespace(
        workflow=workflow,
        config=Path(manifest["config"]),
        model="toy",
        retrieval="hybrid",
        temperature=0.0,
        seed=42,
        timeout=300.0,
        wall_timeout=660.0,
    )

    if fixture != "baseline-v1":
        dataset.update(
            fixture_id="holdout-v1",
            provenance={
                "spec_sha256": source_info["spec_sha256"] if fixture == "holdout-v1" else "wrong"
            },
        )
    if fixture == "wrong-spec":
        with pytest.raises(ValueError, match="specification hash"):
            baseline.live_manifest(args, dataset, "fixture-hash", manifest["selected"])
        return

    observed = baseline.live_manifest(args, dataset, "fixture-hash", manifest["selected"])
    assert observed["dataset_id"] == fixture
    assert observed["workflow"] == workflow
    if workflow == "agent":
        assert observed["agent"]["workflow_id"] == "m4-langgraph-v1"
        assert observed["agent"]["max_reserved_calls"] == 3
        assert observed["agent"]["langgraph_version"]
    else:
        assert "agent" not in observed
    assert observed["source"] == source_info
    assert observed["retrieval"]["embedding"] == index["embeddings"]
    assert observed["model"] == manifest["model"]
    assert observed["settings"] == SETTINGS
    assert observed["indexed_citations"] == {"spec-id": CITATION}
    assert observed["index_sha256"] == baseline.sha(baseline.INDEX.read_bytes())
    assert observed["ollama_version"] == "fixture-version"
    lookup.assert_called_once_with(source, "benchmark", "lexical", 1)


def test_timing_wrapper_only_observes_existing_generation(monkeypatch, capsys):
    generate = Mock(return_value="candidate")
    monkeypatch.setattr(timed_ask.ask, "generate", generate)

    def fake_main(argv):
        assert argv == ["ask", "fixture"]
        assert timed_ask.ask.generate("fixture") == "candidate"
        print(json.dumps(report()))
        return 0

    monkeypatch.setattr(timed_ask, "main", fake_main)
    assert timed_ask.run(["ask", "fixture"]) == 0
    observed = json.loads(capsys.readouterr().out)
    assert observed["report"] == report()
    assert observed["generation_seconds"] >= 0
    assert timed_ask.ask.generate is generate


def test_offline_score_never_loads_live_manifest(run_data, monkeypatch, capsys):
    path, manifest, dataset = run_data
    monkeypatch.setattr(baseline, "REPORTS", path.parent)
    monkeypatch.setattr(baseline, "read_dataset", lambda: (dataset, "fixture-hash"))
    monkeypatch.setattr(baseline, "live_manifest", Mock(side_effect=AssertionError("live request")))
    baseline.resume_run(path, manifest, dataset, "fixture-hash", lambda *_: attempt(report()))
    expected = json.loads(path.read_bytes())["summary"]
    assert baseline.main(["score", "run"]) == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_malformed_preflight_diagnostics_preserve_error():
    reply = report(
        preflight={"issues": "malformed"},
        preflight_validation="unverified",
        verification="unverified",
        command=None,
        error="MPML returned malformed preflight diagnostics",
    )
    result = score(case(gold()), reply)
    assert result["outcome"] == "error"
    assert result["intent_match"] == "match"
    assert result["diagnostic_match"] is None
    assert result["error_category"] == "preflight_error"


def test_reported_model_drift_keeps_prior_attempts(run_data):
    path, manifest, dataset = run_data
    drift = report(model={**report()["model"], "digest": "other-model"})
    execute = Mock(side_effect=[attempt(report()), attempt(drift)])
    with pytest.raises(ValueError, match="different generation model"):
        baseline.resume_run(path, manifest, dataset, "fixture-hash", execute)
    saved = json.loads(path.read_bytes())
    assert saved["summary"]["status"] == "partial"
    assert list(saved["attempts"]) == ["A"]
