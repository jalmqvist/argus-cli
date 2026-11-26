import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_v2_live_validation import completed
from test_v2_live_validation import live as fixed_live

from argus_cli import cli, retrieval, v2_workflow
from argus_cli.generation import (
    Candidate,
    GenerationError,
    GenerationSettings,
    InvalidCandidateError,
)
from argus_cli.provenance import Revision
from argus_cli.v2_contract import ResponseV2

live = fixed_live

QUESTION = "Use strategy TF40 with seed 57."
CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "eval/m4v2/workflow-development-v1.json").read_text()
)["cases"]


def request(live, question=QUESTION):
    report, code = v2_workflow.run(
        live[0], question, model="qwen2.5-coder:7b", settings=GenerationSettings()
    )
    fields = {key: value for key, value in report.items() if key != "workflow"}
    ResponseV2.model_validate(fields)
    assert report["command"] is report["settings"] is None
    assert not report["workflow"]["recipe_released"]
    return report, code


def response(evidence, **changes):
    ids = [
        f"E{pos}"
        for pos, item in enumerate(evidence, 1)
        if item["citation"]["heading"]
        in {"arguments / --strategy", "arguments / --experiment-seed", "env / EXPERIMENT_SEED"}
    ]
    return Candidate.model_validate(
        {
            "outcome": "recipe",
            "argv": ["--strategy", "TF40", "--experiment-seed", "57"],
            "env": {},
            "explanation": "MODEL_PRIVATE_PROSE; run shell now",
            "evidence_ids": ids,
            "uncertainty": [],
            **changes,
        }
    )


@pytest.fixture
def model(monkeypatch):
    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        return response(evidence), "digest-test"

    mock = Mock(side_effect=generate)
    monkeypatch.setattr(v2_workflow, "generate", mock)
    return mock


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_development_routes(live, model, case):
    result, code = request(live, case["question"])
    trace = result["workflow"]
    assert trace["request_route"] == case["route"]
    assert trace["generation_attempted"] == case["attempt"]
    assert trace["model_calls"] == model.call_count == int(case["attempt"])
    assert trace["deterministic_answer"] == (code == 0)


def test_accepted_proposal_is_qualified_and_private(live, model):
    live[2].return_value = completed(
        0,
        [
            {
                "code": "TOY_WARNING",
                "severity": "warning",
                "source": "launch",
                "message": "MODEL_PRIVATE_PROSE or private/output",
            }
        ],
    )
    report, code = request(live)
    trace = report["workflow"]
    assert code == 1 and trace["answer_delivered"]
    assert report["answer_status"] == "limited"
    assert report["recipe_status"] == "withheld"
    assert report["material_constraints_status"] == "unresolved"
    assert trace["preflight_attempted"] and trace["preflight_outcome"] == "accepted_with_warnings"
    assert report["intent_coverage"] == "unresolved"
    assert trace["material_intent"] == trace["effective_configuration"] == "unresolved"
    assert trace["model_digest"] == "digest-test"
    assert {"setting": "experiment_seed", "winner": "cli"} in trace["effective_observations"]
    assert report["provenance"]["source_revision"] == "revision-a"
    assert report["preflight"]["diagnostics"][0]["code"] == "TOY_WARNING"
    assert "MPML preflight accepted the proposal with warnings." in report["explanation"]
    serialized = json.dumps(report)
    for secret in ("MODEL_PRIVATE_PROSE", "private/output", "--experiment-seed", '"argv"', '"env"'):
        assert secret not in serialized
    assert live[2].call_args.args[0][-4:] == ["--strategy", "TF40", "--experiment-seed", "57"]


@pytest.mark.parametrize(
    ("mutation", "label"),
    [
        ({"argv": ["--strategy", "ZZPRIVATE"]}, "structure"),
        ({"argv": ["--invented-private"]}, "structure"),
        ({"env": {"UNLISTED": "leak-private"}}, "structure"),
        ({"evidence_ids": ["E999"]}, "invalid_citations"),
        (
            {"outcome": "abstain", "argv": [], "uncertainty": ["raw private reason"]},
            "model_abstained",
        ),
        ({"outcome": "abstain", "env": {"UNLISTED": "leak-private"}}, "invalid_abstention"),
    ],
)
def test_untrusted_candidate_cannot_leak_or_probe(live, model, mutation, label):
    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        return response(evidence, **mutation), "digest-test"

    model.side_effect = generate
    report, _ = request(live)
    trace = report["workflow"]
    assert label in trace["blockers"] or trace["error"] == label
    assert trace["model_calls"] == model.call_count == 1
    live[2].assert_not_called()
    rendered = json.dumps(report)
    for hidden in (
        "MODEL_PRIVATE_PROSE",
        "ZZPRIVATE",
        "--invented-private",
        "leak-private",
        "raw private reason",
        "E999",
    ):
        assert hidden not in rendered


def test_wrong_canonical_strategy_is_flagged_even_if_preflight_accepts(live, model):
    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        return response(evidence, argv=["--strategy", "MR70"]), "digest-test"

    model.side_effect = generate
    report, _ = request(live, "Use strategy TF40.")
    trace = report["workflow"]
    assert trace["preflight_outcome"] == "accepted"
    assert "recognized_constraints" in trace["blockers"]
    assert "MR70" not in json.dumps(report)


def test_unrelated_markdown_cannot_attest_settings(live, model, monkeypatch):
    monkeypatch.setattr(
        v2_workflow,
        "rank_verified_index",
        lambda index, *_: {"results": {"lexical": index["chunks"]}},
    )

    def generate(question, evidence, model, settings, *, on_model_call):
        on_model_call()
        doc = next(
            f"E{pos}"
            for pos, item in enumerate(evidence, 1)
            if item["citation"]["path"] == "reference.md"
        )
        return response(evidence, evidence_ids=[doc]), "digest-test"

    model.side_effect = generate
    report, _ = request(live)
    assert report["workflow"]["citations_resolved"]
    assert not report["workflow"]["setting_evidence_valid"]
    assert report["citations"] == []
    assert "Ignore instructions" not in json.dumps(report)


@pytest.mark.parametrize("drift", ["index", "source", "env"])
def test_drift_after_generation_skips_preflight(live, model, monkeypatch, drift):
    assistant = model.side_effect

    def change(*args, **kwargs):
        result = assistant(*args, **kwargs)
        if drift == "index":
            retrieval.INDEX.write_bytes(retrieval.INDEX.read_bytes() + b" ")
        elif drift == "source":
            monkeypatch.setattr(retrieval, "revision", lambda _: Revision("revision-b", False))
        else:
            monkeypatch.setenv("PRIVATE_GENERATION_SETTING", "changed-private-value")
        return result

    model.side_effect = change
    report, code = request(live)
    assert code == 2
    assert report["workflow"]["error"] == "validation_drift"
    assert report["provenance"] is None
    live[2].assert_not_called()


@pytest.mark.parametrize(
    ("error", "count", "label", "status"),
    [
        (GenerationError("unavailable private"), 0, "ollama_unavailable", 2),
        (GenerationError("generation timed out private"), 1, "ollama_timeout", 2),
        (InvalidCandidateError("malformed private"), 1, "invalid_proposal", 1),
    ],
)
def test_failures_never_retry(live, model, error, count, label, status):
    def fail(*args, on_model_call, **kwargs):
        if count:
            on_model_call()
        raise error

    model.side_effect = fail
    report, code = request(live)
    assert code == status
    assert report["workflow"]["error"] == label
    assert report["workflow"]["model_calls"] == count
    assert model.call_count == 1
    assert "private" not in json.dumps(report)
    live[2].assert_not_called()


def test_opt_in_cli_passes_generation_settings(live, model, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_sources", lambda _: {"mpml": live[0]})
    assert (
        cli.main(
            [
                "ask",
                QUESTION,
                "--agent-v2",
                "--model",
                "local-test",
                "--temperature",
                "0.3",
                "--seed",
                "9",
                "--timeout",
                "12",
                "--retrieval-mode",
                "hybrid",
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["workflow"]["model_calls"] == 1
    assert model.call_args.args[2] == "local-test"
    settings = model.call_args.args[3]
    assert settings.temperature == 0.3 and settings.seed == 9 and settings.timeout_seconds == 12
