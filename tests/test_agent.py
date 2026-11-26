from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from argus_cli.adapters.mpml import BridgeResult
from argus_cli.agent import Evidence, Snapshot, Stages, Validation, build_graph
from argus_cli.ask import CandidateError, _validate_citations, _validate_options
from argus_cli.config import Source
from argus_cli.generation import Candidate
from argus_cli.intent import check, extract

FLAGS = (
    "--strategy",
    "--experiment-seed",
    "--phaseaware-tf",
    "--phaseaware-mr",
    "--experiment-variant",
    "--behavioral-surface",
)
ENV = (
    "ACTIVE_PAIRS",
    "EXPERIMENT_SEED",
    "EXPERIMENT_VARIANT",
    "BEHAVIORAL_SURFACE",
    "DL_SIGNALS_ENABLED",
)
SPEC = {
    "arguments": [{"flags": [name], "action": "store", "nargs": None} for name in FLAGS],
    "env": [{"name": name, "scope": "launch_selector"} for name in ENV],
}
SNAPSHOT = Snapshot("git", False, "spec", "index", SPEC)
SOURCE = Source(
    "mpml",
    Path("/toy"),
    Path("/toy/python"),
    "mpml_v1",
    "mpml.spec",
    "mpml.preflight",
    "main.py",
    (),
)
QUESTION = "How do I evaluate MR32 on USDJPY?"
WARNING = {"code": "TOY_WARNING", "message": "Preserve me", "source": "env", "severity": "warning"}
ERROR = {**WARNING, "code": "TOY_ERROR", "severity": "error"}


def candidate(argv=None, env=None, **changes):
    return Candidate(
        **{
            "argv": ["--strategy", "MR32"] if argv is None else argv,
            "env": {"ACTIVE_PAIRS": "USDJPY"} if env is None else env,
            "explanation": "Toy candidate",
            "evidence_ids": ["E1"],
            "uncertainty": [],
            "outcome": "recipe",
            **changes,
        }
    )


def validate(proposal, evidence):
    try:
        used = _validate_options(proposal, evidence.snapshot.spec)
        citations = _validate_citations(
            proposal,
            [
                {
                    "id": evidence.ids[0],
                    "citation": {"heading": "Toy"},
                    "text": " ".join((*FLAGS, *ENV)),
                }
            ],
            used,
        )
    except CandidateError as exc:
        return Validation(False, str(exc), retryable=True)
    return Validation(True, citations=tuple(item["id"] for item in citations))


@pytest.fixture
def stages(monkeypatch):
    pytest.importorskip("langgraph")
    monkeypatch.delenv("DL_SIGNALS_ENABLED", raising=False)
    return Stages(
        verify=Mock(return_value=SNAPSHOT),
        retrieve=Mock(return_value=Evidence(SNAPSHOT, ("toy-id",))),
        generate=Mock(return_value=candidate()),
        validate=Mock(side_effect=validate),
        preflight=Mock(return_value=BridgeResult(0, {"issues": []}, "")),
    )


def run(stages, question=QUESTION, **extra):
    return build_graph(stages).invoke({"question": question, "source": SOURCE, **extra})


def test_release_requires_gates_and_exact_candidate(stages):
    wrapped = Mock()
    for name in ("verify", "retrieve", "generate", "validate", "preflight"):
        wrapped.attach_mock(getattr(stages, name), name)
    state = run(stages, reserved_calls=99, released=True, disposition="validated")
    calls = [call[0] for call in wrapped.mock_calls]
    assert calls == [
        "verify",
        "retrieve",
        "verify",
        "generate",
        "validate",
        "verify",
        "preflight",
        "verify",
        "verify",
    ]
    assert state["released"]
    assert state["disposition"] == "validated"
    assert state["reserved_calls"] == state["model_calls"] == 1
    assert state["repair_count"] == 0
    assert state["intent_check"].violated == ()
    assert state["citations"] == ("toy-id",)
    assert state["wall_seconds"] >= 0
    stages.preflight.assert_called_once_with(SOURCE, candidate())


def test_warnings_survive(stages):
    stages.preflight.return_value = BridgeResult(0, {"issues": [WARNING]}, "")
    state = run(stages)
    assert state["released"]
    assert state["disposition"] == "validated_with_warnings"
    assert state["warnings"] == (WARNING,)


def test_accepted_preflight_with_wrong_intent_never_releases(stages):
    stages.generate.return_value = candidate(["--strategy", "TF4"])
    state = run(stages)
    assert not state["released"]
    assert state["disposition"] == "abstained"
    assert state["intent_check"].violated
    assert state["preflight_status"] == "validated"
    assert len(state["attempts"]) == 2
    assert "Repeated failed candidate" in state["reason"]


@pytest.mark.parametrize("bad", [candidate(["--invented"]), candidate(evidence_ids=["unknown"])])
def test_structural_and_citation_failures_skip_preflight(stages, bad):
    stages.generate.return_value = bad
    state = run(stages)
    assert state["disposition"] == "rejected"
    assert not state["released"]
    stages.preflight.assert_not_called()


def test_preflight_rejection_keeps_errors(stages):
    stages.preflight.return_value = BridgeResult(1, {"issues": [ERROR, WARNING]}, "")
    state = run(stages)
    assert state["disposition"] == "rejected"
    assert not state["released"]
    assert state["attempts"][0].preflight.document["issues"] == [ERROR, WARNING]
    assert state["warnings"] == (WARNING,)
    assert state["reserved_calls"] == 1


def test_valid_abstention_skips_preflight(stages):
    stages.generate.return_value = candidate(
        [], {}, outcome="abstain", uncertainty=["No supported recipe."], evidence_ids=[]
    )
    state = run(stages)
    assert state["disposition"] == "abstained"
    assert not state["released"]
    stages.preflight.assert_not_called()


@pytest.mark.parametrize(
    "question,reason",
    [
        ("Use the previous strategy.", "identifier is missing"),
        ("Use only the strategy I meant last time", "outside the supported patterns"),
        ("Which MPML launch flags place a live broker order for USDJPY?", "unsupported"),
        (
            "Can preflight prove DL is active and the prediction artifact was actually loaded?",
            "cannot prove",
        ),
        ("Make a nice recipe", "outside deterministic intent coverage"),
    ],
)
def test_unresolved_requests_never_generate(stages, question, reason):
    state = run(stages, question)
    assert state["disposition"] == "abstained"
    assert not state["released"]
    assert reason in state["reason"]
    assert state["reserved_calls"] == 0
    stages.generate.assert_not_called()


def test_phaseaware_role_substitution_detected(stages):
    stages.generate.return_value = candidate(["--phaseaware-mr", "MR32"], {})
    state = run(
        stages,
        "Use MR32 as the PhaseAware trend-following representative. "
        "Do not substitute another strategy.",
    )
    assert not state["released"]
    assert {item.target for item in state["intent_check"].violated} == {
        "--phaseaware-tf",
        "--phaseaware-mr",
    }


def test_source_drift_before_release_blocks_command(stages):
    stages.verify.side_effect = [SNAPSHOT] * 4 + [replace(SNAPSHOT, dirty=True)]
    state = run(stages)
    assert state["disposition"] == "unverified"
    assert not state["released"]
    assert len(state["attempts"]) == 1


def test_index_drift_during_retrieval_skips_generation(stages):
    stages.retrieve.return_value = Evidence(replace(SNAPSHOT, index_sha256="other"), ("toy-id",))
    assert run(stages)["disposition"] == "unverified"
    stages.generate.assert_not_called()


def test_budget_caps_distinct_failed_candidates(stages):
    stages.generate.side_effect = [
        candidate(["--strategy", name]) for name in ("TF1", "TF2", "TF3")
    ]
    state = run(stages)
    assert state["disposition"] == "abstained"
    assert not state["released"]
    assert state["reserved_calls"] == state["model_calls"] == len(state["attempts"]) == 3
    assert state["repair_count"] == 2
    assert "budget exhausted" in state["reason"]
    assert [entry.ordinal for entry in state["attempts"]] == [1, 2, 3]


def test_scripted_valid_second_candidate_passes_all_gates(stages):
    stages.generate.side_effect = [candidate(["--invented"]), candidate()]
    state = run(stages)
    assert state["released"]
    assert state["reserved_calls"] == 2
    assert not state["attempts"][0].validation.accepted
    assert state["attempts"][0].preflight is None
    stages.preflight.assert_called_once()


@pytest.mark.parametrize("failure", [RuntimeError("fixture unavailable"), KeyboardInterrupt()])
def test_failed_or_interrupted_generation_consumes_attempt(stages, failure):
    stages.generate.side_effect = failure
    state = run(stages)
    assert state["disposition"] == "unverified"
    assert state["reserved_calls"] == state["model_calls"] == 1
    assert state["attempts"][0].candidate is None
    stages.preflight.assert_not_called()


@pytest.mark.parametrize(
    ("question", "correct", "incorrect"),
    [
        (
            "Evaluate TF4 followed by MR32 in the same launch, in that order.",
            (["--strategy=TF4", "--strategy", "MR32"], {}),
            (["--strategy", "MR32", "--strategy", "TF4"], {}),
        ),
        (
            "Use --strategy TF4 --strategy MR32",
            (["--strategy", "TF4", "--strategy", "MR32"], {}),
            (["--strategy", "TF4"], {}),
        ),
        (
            "Use only USDJPY and EURUSD, in that order, with the default strategy selection.",
            ([], {"ACTIVE_PAIRS": "usdjpy, EURUSD"}),
            ([], {"ACTIVE_PAIRS": "EURUSD,USDJPY"}),
        ),
        ("Use the default strategy selection", ([], {}), (["--strategy", "MR32"], {})),
        (
            "Set the MPML random seed to 123 using an environment override only.",
            ([], {"EXPERIMENT_SEED": "123"}),
            (["--experiment-seed", "123"], {"EXPERIMENT_SEED": "123"}),
        ),
        (
            "Use the --experiment-seed flag to set the MPML random seed to 123.",
            (["--experiment-seed", "123"], {}),
            (["--experiment-seed", "123"], {"EXPERIMENT_SEED": "123"}),
        ),
        (
            "Keep EXPERIMENT_SEED=11 in the environment, but make this run use seed 123 through the CLI.",
            (["--experiment-seed", "123"], {"EXPERIMENT_SEED": "11"}),
            (["--experiment-seed", "123"], {}),
        ),
        (
            "Use ACTIVE_PAIRS=USDJPY, EURUSD",
            ([], {"ACTIVE_PAIRS": "USDJPY, EURUSD"}),
            ([], {"ACTIVE_PAIRS": "USDJPY,EURUSD"}),
        ),
    ],
)
def test_intent_check_records_spans_and_violations(question, correct, incorrect):
    intent = extract(question, SPEC)
    assert intent.coverage == "enforced"
    assert all(question[start:end] for start, end in (item.span for item in intent.constraints))
    assert check(intent, *correct).satisfied == intent.constraints
    assert check(intent, *incorrect).violated


@pytest.mark.parametrize(
    "question",
    [
        "Do not evaluate MR32 on USDJPY.",
        'The example is "evaluate MR32 on USDJPY". What else can I do?',
        "Evaluate MR32 on USDJPY unless the other pair is better.",
    ],
)
def test_negation_quotes_and_qualifiers_do_not_yield_partial_constraints(question):
    result = extract(question, SPEC)
    assert result.coverage != "enforced"
    assert result.constraints == ()


def test_cli_and_single_pass_import_without_langgraph():
    import subprocess
    import sys

    code = """
import sys
sys.modules['langgraph'] = None
from argus_cli.cli import main
from argus_cli.ask import ask
from argus_cli.agent import build_graph
try:
    build_graph(None)
except RuntimeError as exc:
    assert 'optional agent extra' in str(exc)
else:
    raise AssertionError('expected dependency error')
main(['ask', '--help'])
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_dl_activation_cannot_release_on_clean_preflight(stages):
    stages.generate.return_value = candidate(
        env={"ACTIVE_PAIRS": "USDJPY", "DL_SIGNALS_ENABLED": "true"}
    )
    state = run(stages)
    assert state["disposition"] == "abstained"
    assert not state["released"]
    assert state["preflight_status"] == "validated"
    assert "cannot verify DL activation" in state["reason"]


def test_malformed_preflight_preserves_raw_response(stages):
    stages.preflight.return_value = BridgeResult(0, {"issues": "malformed"}, "")
    state = run(stages)
    assert state["disposition"] == "unverified"
    assert not state["released"]
    assert state["attempts"][0].preflight.document == {"issues": "malformed"}


def test_live_spec_must_support_enforced_option():
    result = extract(QUESTION, {**SPEC, "arguments": []})
    assert result.coverage == "unresolved"
    assert not result.constraints


def test_unsupported_strategy_value_is_preserved_for_preflight(stages):
    stages.generate.return_value = candidate(["--strategy", "ZZ999"], {})
    stages.preflight.return_value = BridgeResult(1, {"issues": [ERROR]}, "")
    state = run(stages, "Evaluate only ZZ999. Do not replace it with another strategy.")
    assert state["disposition"] == "rejected"
    assert state["intent_check"].violated == ()
    stages.preflight.assert_called_once_with(SOURCE, candidate(["--strategy", "ZZ999"], {}))


@pytest.mark.parametrize(
    ("question", "argv", "env"),
    [
        ("Use only USDJPY and EURUSD, in that order.", [], {"ACTIVE_PAIRS": "USDJPY,EURUSD"}),
        ("Set experiment variant B through the environment only.", [], {"EXPERIMENT_VARIANT": "B"}),
        (
            "Keep EXPERIMENT_VARIANT=A as an environment override, but select variant B on the command line.",
            ["--experiment-variant", "B"],
            {"EXPERIMENT_VARIANT": "A"},
        ),
        (
            "Keep BEHAVIORAL_SURFACE=trend_vol in the environment but select persistent on the command line.",
            ["--behavioral-surface", "persistent"],
            {"BEHAVIORAL_SURFACE": "trend_vol"},
        ),
        (
            "Use MR32 as the PhaseAware mean-reversion representative.",
            ["--phaseaware-mr", "MR32"],
            {},
        ),
        (
            (
                "Set TF4 as the PhaseAware trend-following representative and MR32 as the mean-reversion "
                "representative, without filtering the evaluated strategies."
            ),
            ["--phaseaware-tf", "TF4", "--phaseaware-mr", "MR32"],
            {},
        ),
    ],
)
def test_additional_supported_patterns(question, argv, env):
    intent = extract(question, SPEC)
    assert intent.coverage == "enforced"
    assert check(intent, argv, env).satisfied == intent.constraints


def test_second_call_failure_still_consumes_repair_slot(stages):
    stages.generate.side_effect = [candidate(["--invented"]), RuntimeError("fixture failed")]
    state = run(stages)
    assert state["disposition"] == "unverified"
    assert state["reserved_calls"] == state["model_calls"] == len(state["attempts"]) == 2
    assert state["repair_count"] == 1
    assert state["attempts"][0].validation.reason
    assert state["attempts"][1].generation_seconds >= 0
