import json
import shlex
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessageChunk
from test_agent import ENV, ERROR, FLAGS, QUESTION, SOURCE, SPEC, WARNING, candidate

from argus_cli import generation, live_agent
from argus_cli.adapters.mpml import BridgeResult
from argus_cli.cli import main
from argus_cli.generation import GenerationError, InvalidCandidateError

METADATA = {"git_sha": "git", "dirty": False, "spec_sha256": "spec"}
CHUNKS = [
    {
        "id": "toy-id",
        "citation": {"path": "mpml/spec.py", "heading": "Toy", **METADATA},
        "text": " ".join((*FLAGS, *ENV)),
    }
]


@pytest.fixture
def live(monkeypatch):
    pytest.importorskip("langgraph")
    monkeypatch.delenv("DL_SIGNALS_ENABLED", raising=False)
    mocks = {
        "verified_index": Mock(return_value=({}, METADATA, SPEC, "index")),
        "index_sha256": Mock(return_value="index"),
        "rank_verified_index": Mock(return_value={"results": {"hybrid": CHUNKS}}),
        "source_matches": Mock(return_value=True),
        "model_digest": Mock(return_value="model-digest"),
        "generate": Mock(return_value=(candidate(), "model-digest")),
        "preflight": Mock(return_value=BridgeResult(0, {"issues": []}, "")),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(live_agent, name, mock)
    monkeypatch.setattr("argus_cli.cli.load_sources", lambda _: {"mpml": SOURCE})
    return mocks


def ask(capsys, question=QUESTION, code=0):
    assert main(["ask", question, "--agent"]) == code
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("issues", [[], [WARNING]])
def test_agent_cli_renders_only_final_validated_settings(live, capsys, issues):
    live["preflight"].return_value = BridgeResult(0, {"issues": issues}, "")
    report = ask(capsys)
    assert report["workflow"] == "m4-langgraph-v1"
    assert report["model_calls"] == report["reserved_calls"] == 1
    assert report["repair_count"] == 0
    assert report["verification"] == ("validated_with_warnings" if issues else "validated")
    assert report["warnings"] == issues
    assert report["preflight"]["issues"] == issues
    assert report["citations"][0]["id"] == "toy-id"
    assert report["intent_status"] == "consistent_with_explicit_constraints"
    assert report["provenance"] == {**METADATA, "index_sha256": "index"}
    assert report["command_purpose"] == "manual_execution_only"
    assert shlex.split(report["command"]) == [
        "cd",
        "/toy",
        "&&",
        "env",
        "ACTIVE_PAIRS=USDJPY",
        "/toy/python",
        "/toy/main.py",
        "--strategy",
        "MR32",
    ]
    live["verified_index"].assert_called_once_with(SOURCE)
    live["preflight"].assert_called_once_with(
        SOURCE, ["--strategy", "MR32"], overrides={"ACTIVE_PAIRS": "USDJPY"}
    )


@pytest.mark.parametrize(
    ("failed", "diagnostic"),
    [
        (candidate(["--invented=private-value"]), "invalid_flag"),
        (candidate(["--strategy", "MR32", "ACTIVE_PAIRS=private-value"], {}), "env_in_argv"),
        (candidate([], {}, outcome="abstain", uncertainty=["  "]), "abstention"),
        (candidate(evidence_ids=["fabricated-private-value"]), "citation"),
        (InvalidCandidateError("malformed private-value"), "invalid_candidate"),
    ],
)
def test_repair_uses_fixed_inputs_and_redacted_feedback(live, capsys, failed, diagnostic):
    live["generate"].side_effect = [
        failed if isinstance(failed, Exception) else (failed, "model-digest"),
        (candidate(), "model-digest"),
    ]
    report = ask(capsys)
    assert report["repair_count"] == 1
    assert report["attempts"][0]["validation_code"] == diagnostic
    assert report["attempts"][0]["preflight"] is None
    assert report["attempts"][1]["structural_validation"] == "passed"
    first, second = live["generate"].call_args_list
    assert first.args == second.args
    assert first.args[:2] == (QUESTION, CHUNKS)
    assert first.kwargs["repair_context"] is None
    feedback = second.kwargs["repair_context"]
    assert feedback["code"] == diagnostic
    assert json.loads(json.dumps(feedback["constraints"])) == report["constraints"]
    assert "private-value" not in json.dumps(feedback)
    assert "private-value" not in json.dumps(report)
    assert first.kwargs["expected_digest"] == second.kwargs["expected_digest"] == "model-digest"
    live["rank_verified_index"].assert_called_once()
    live["preflight"].assert_called_once()


@pytest.mark.parametrize(
    ("question", "proposed", "targets"),
    [
        (
            "Use MR32 as the PhaseAware trend-following representative.",
            candidate(["--phaseaware-mr", "MR32"], {}),
            {"--phaseaware-tf", "--phaseaware-mr"},
        ),
        (
            "Use only USDJPY and EURUSD, in that order, with the default strategy selection.",
            candidate(["--strategy", "MR32"], {"ACTIVE_PAIRS": "USDJPY,EURUSD"}),
            {"--strategy"},
        ),
        (
            "Use ACTIVE_PAIRS=USDJPY,EURUSD",
            candidate([], {"ACTIVE_PAIRS": "EURUSD,USDJPY"}),
            {"ACTIVE_PAIRS"},
        ),
    ],
)
def test_clean_preflight_cannot_override_explicit_constraints(
    live, capsys, question, proposed, targets
):
    live["generate"].return_value = (proposed, "model-digest")
    report = ask(capsys, question, code=1)
    assert report["verification"] == "abstained"
    assert report["preflight_validation"] == "passed"
    assert report["intent_status"] == "inconsistent"
    assert report["command"] is None
    assert "Repeated failed candidate" in report["reason"]
    assert report["reserved_calls"] == 2
    assert set(live["generate"].call_args.kwargs["repair_context"]["violated_targets"]) == targets


def test_ordered_repeated_strategies_and_pairs_pass(live, capsys):
    argv = ["--strategy", "TF4", "--strategy=MR32"]
    live["generate"].return_value = (candidate(argv, {}), "model-digest")
    report = ask(capsys, "Use --strategy TF4 --strategy MR32")
    assert report["argv"] == argv
    live["preflight"].assert_called_once_with(SOURCE, argv, overrides={})

    env = {"ACTIVE_PAIRS": "USDJPY, EURUSD"}
    live["generate"].return_value = (candidate([], env), "model-digest")
    report = ask(capsys, "Use ACTIVE_PAIRS=USDJPY,EURUSD")
    assert report["env"] == env
    assert shlex.split(report["command"])[4] == "ACTIVE_PAIRS=USDJPY, EURUSD"


@pytest.mark.parametrize("matches_intent", [True, False])
def test_authoritative_rejection_retains_diagnostics(live, capsys, matches_intent):
    live["generate"].return_value = (
        candidate(["--strategy", "MR32" if matches_intent else "TF4"]),
        "model-digest",
    )
    live["preflight"].return_value = BridgeResult(1, {"issues": [ERROR, WARNING]}, "private stderr")
    report = ask(capsys, code=1)
    assert report["verification"] == "rejected"
    assert ("explicitly requested" in report["reason"]) is matches_intent
    assert report["preflight"]["issues"] == [ERROR, WARNING]
    assert report["warnings"] == [WARNING]
    assert report["attempts"][0]["preflight"]["issues"] == [ERROR, WARNING]
    assert report["command"] is None
    assert "private stderr" not in json.dumps(report)
    live["generate"].assert_called_once()


@pytest.mark.parametrize(
    "question",
    [
        "Which MPML launch flags place a live broker order for USDJPY?",
        "Use the previous strategy.",
        "Can preflight prove DL is active and the prediction artifact was actually loaded?",
        "Make me a nice recipe.",
    ],
)
def test_unsupported_or_unresolved_intent_abstains(live, capsys, question):
    report = ask(capsys, question, code=1)
    assert report["verification"] == "abstained"
    assert report["reason"]
    assert report["reserved_calls"] == 0
    assert report["command"] is None
    live["generate"].assert_not_called()
    live["preflight"].assert_not_called()


@pytest.mark.parametrize(
    "message,reason",
    [
        ("transport timeout with private-value", "timed out"),
        ("Ollama model is unavailable: private-value", "unavailable"),
        ("Ollama model changed between attempts: private-value", "identity changed"),
    ],
)
def test_generation_infrastructure_errors_stop(live, capsys, message, reason):
    live["generate"].side_effect = GenerationError(message)
    report = ask(capsys, code=1)
    assert report["verification"] == "unverified"
    assert report["reserved_calls"] == 1
    assert reason in report["reason"]
    assert "private-value" not in json.dumps(report)
    assert report["command"] is None
    live["preflight"].assert_not_called()


def test_invalid_citations_exhaust_budget_without_preflight(live, capsys):
    live["generate"].side_effect = [
        (candidate(evidence_ids=[item]), "model-digest") for item in ("fake1", "fake2", "fake3")
    ]
    report = ask(capsys, code=1)
    assert report["verification"] == "rejected"
    assert report["reserved_calls"] == 3
    assert report["repair_count"] == 2
    assert "budget exhausted" in report["reason"]
    assert report["command"] is None
    live["preflight"].assert_not_called()


@pytest.mark.parametrize("drift", ["source", "index"])
def test_drift_at_release_blocks_command(live, capsys, drift):
    if drift == "source":
        live["source_matches"].side_effect = [True, True, True, False]
    else:
        live["index_sha256"].side_effect = ["index"] * 7 + ["changed"]
    report = ask(capsys, code=1)
    assert report["verification"] == "unverified"
    assert report["preflight_validation"] == "passed"
    assert report["command"] is None
    assert "before release" in report["reason"]


def test_model_replacement_after_malformed_output_stops(live, capsys):
    live["generate"].side_effect = InvalidCandidateError("invalid output")
    live["model_digest"].side_effect = ["model-digest", "different"]
    report = ask(capsys, code=1)
    assert report["verification"] == "unverified"
    assert report["reserved_calls"] == 1
    assert "identity changed" in report["reason"]
    live["preflight"].assert_not_called()


def test_repair_prompt_extends_only_agent_generation(monkeypatch):
    chat = Mock()

    def stream(_):
        yield AIMessageChunk(content=candidate().model_dump_json())

    chat.return_value.stream.side_effect = stream
    monkeypatch.setattr(generation, "ChatOllama", chat)
    monkeypatch.setattr(generation, "model_digest", lambda _: "digest")
    monkeypatch.setattr(generation, "_request", lambda *_: {})
    settings = generation.GenerationSettings()

    generation.generate(QUESTION, CHUNKS, "local", settings)
    messages = chat.return_value.stream.call_args.args[0]
    assert messages[0] == ("system", generation.SYSTEM_PROMPT)
    assert "repair" not in json.loads(messages[1][1])
    feedback = {"code": "intent", "constraints": []}
    generation.generate(
        QUESTION, CHUNKS, "local", settings, repair_context=feedback, expected_digest="digest"
    )
    messages = chat.return_value.stream.call_args.args[0]
    assert "Never change the requested strategy, role" in messages[0][1]
    assert json.loads(messages[1][1])["repair"] == feedback

    with pytest.raises(GenerationError, match="changed"):
        generation.generate(QUESTION, CHUNKS, "local", settings, expected_digest="other")
    assert chat.call_count == 2


def test_missing_agent_extra_has_install_message(live, capsys, monkeypatch):
    from argus_cli.agent import AgentUnavailable

    monkeypatch.setattr(live_agent, "build_graph", Mock(side_effect=AgentUnavailable))
    assert main(["ask", QUESTION, "--agent"]) == 2
    result = capsys.readouterr()
    assert not result.out
    assert "pip install 'argus-cli[llm,agent]'" in result.err
    live["generate"].assert_not_called()


def test_bridge_failure_is_unverified_without_retry(live, capsys):
    live["preflight"].side_effect = RuntimeError("private-value")
    report = ask(capsys, code=1)
    assert report["verification"] == "unverified"
    assert report["preflight_validation"] == "unverified"
    assert report["reserved_calls"] == 1
    assert report["command"] is None
    assert "private-value" not in json.dumps(report)
