import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from eval.generation import baseline
from eval.generation import manual_capture as manual

MANUAL_IDS = {
    "q002",
    "q004",
    "q012",
    "q014",
    "q015",
    "q016",
    "q017",
    "q018",
    "q019",
    "q021",
    "q022",
    "q023",
    "q024",
    "q025",
}


@pytest.fixture
def capture(tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "_LOCAL", tmp_path / "manual")
    dataset, fingerprint = manual.load_questions()
    config, index = tmp_path / "source.yaml", tmp_path / "index.json"
    config.write_bytes(b"config")
    index.write_bytes(b"index")
    monkeypatch.setattr(baseline, "INDEX", index)
    manifest = {
        "workflow": "single-pass",
        "dataset_id": dataset["fixture_id"],
        "dataset_version": dataset["version"],
        "dataset_sha256": fingerprint,
        "holdout_sha256": manual._HOLDOUT_SHA256,
        "selected": [item["id"] for item in dataset["cases"]],
        "source": {
            "git_sha": dataset["mpml_sha"],
            "dirty": False,
            "spec_sha256": dataset["provenance"]["spec_sha256"],
        },
        "config": str(config),
        "config_sha256": baseline.sha(config.read_bytes()),
        "index_sha256": baseline.sha(index.read_bytes()),
        "model": {"name": "toy", "digest": "toy-digest"},
        "settings": {"seed": 42},
        "retrieval": {"mode": "hybrid", "limit": 5},
        "environment_sha256": "environment",
        "machine": {},
        "python": "3.12",
        "dependencies": {},
        "ollama_version": "test",
        "wall_timeout_seconds": 1200,
        "argus": {"git_sha": "test-revision", "implementation_hashes": {}},
    }
    return dataset, fingerprint, manifest


def response(case, manifest):
    is_agent = manifest["workflow"] == "agent"
    raw = {
        "question": case["question"],
        "verification": "validated_with_warnings",
        "argv": ["--example", "literal value"],
        "env": {"SETTING": "candidate value"},
        "explanation": "M4 LangGraph: The CLI overrides the environment."
        if is_agent
        else "The CLI takes precedence over the environment.",
        "uncertainty": ["The request is outside deterministic intent coverage."]
        if is_agent
        else [],
        "citations": [
            {"id": "trace", "path": "mpml/spec.py", "heading": "Precedence", "private": "agent"}
        ],
        "preflight": {
            "issues": [
                {
                    "code": "EXAMPLE",
                    "severity": "warning",
                    "source": "env",
                    "message": "A supplied value may be ignored.",
                    "trace": "LangGraph",
                }
            ]
        },
        "preflight_exit_code": 0,
        "preflight_validation": "passed",
        "command": "private interpreter path",
        "reason": "Generation-call budget exhausted.",
        "attempts": [{"reason": "Repeated failed candidate.", "generation_seconds": 1.23}],
        "wall_seconds": 2.34,
        "provenance": {
            **manifest["source"],
            **({"index_sha256": manifest["index_sha256"]} if is_agent else {}),
        },
        "model": {**manifest["model"], "settings": manifest["settings"]},
        "retrieval": manifest["retrieval"],
    }
    if is_agent:
        raw["workflow"] = manifest["agent"]["workflow_id"]
    return {"report": raw, "generation_seconds": 1.23, "wall_seconds": 2.34, "error_category": None}


def _saved(capture, workflow, path):
    dataset, _, before = capture
    manifest = copy.deepcopy(before)
    if workflow == "agent":
        manifest.update(workflow="agent", agent={"workflow_id": "m4-langgraph-v1"})
    run = {
        "format": baseline.FORMAT,
        "manifest": manifest,
        "attempts": {
            case["id"]: {**response(case, manifest), "question": case["question"]}
            for case in dataset["cases"]
        },
        "summary": {"previous_scores": "must not be shared"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run), encoding="utf-8")
    return run


def test_exact_manual_inventory_and_frozen_questions():
    archive = json.loads(manual._ARCHIVE.read_bytes())
    dataset, fingerprint = manual.load_questions()
    assert fingerprint == manual._ARCHIVE_SHA256
    assert {item["id"] for item in dataset["cases"]} == MANUAL_IDS
    assert dataset["cases"] == [
        {"id": item["id"], "question": item["question"]} for item in archive["manual_only"]
    ]
    assert len(dataset["cases"]) == 14


@pytest.mark.parametrize("invalid", ["overlap", "text", "digest"])
def test_archive_mismatches_are_refused(tmp_path, monkeypatch, invalid):
    archive = json.loads(manual._ARCHIVE.read_bytes())
    if invalid == "overlap":
        archive["manual_only"][0]["id"] = archive["cases"][0]["id"]
    elif invalid == "text":
        archive["cases"][0]["question"] += " edited"
    path = tmp_path / "archive.json"
    path.write_text(json.dumps(archive))
    monkeypatch.setattr(manual, "_ARCHIVE", path)
    if invalid != "digest":
        monkeypatch.setattr(manual, "_ARCHIVE_SHA256", baseline.sha(path.read_bytes()))
    with pytest.raises(ValueError, match="partition|frozen holdout|source has changed"):
        manual.load_questions()


def test_interrupted_capture_resumes_with_raw_reports_and_refuses_drift(capture, tmp_path):
    dataset, fingerprint, manifest = capture
    first = dataset["cases"][0]
    path = tmp_path / "raw.json"
    execute = Mock(side_effect=[response(first, manifest), KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        baseline.resume_run(
            path, manifest, dataset, fingerprint, execute, summarize_run=manual.capture_status
        )
    saved = json.loads(path.read_bytes())
    assert saved["summary"]["status"] == "partial"
    assert saved["attempts"][first["id"]]["report"] == response(first, manifest)["report"]

    changed = {**manifest, "model": {"name": "toy", "digest": "changed"}}
    with pytest.raises(ValueError, match="Incompatible resume"):
        baseline.resume_run(
            path, changed, dataset, fingerprint, execute, summarize_run=manual.capture_status
        )
    resume = Mock(side_effect=[response(case, manifest) for case in dataset["cases"][1:]])
    summary = baseline.resume_run(
        path, manifest, dataset, fingerprint, resume, summarize_run=manual.capture_status
    )
    assert resume.call_count == 13
    assert summary == {"status": "complete", "captured": 14, "total": 14, "remaining": []}


def test_blinded_packet_is_offline_and_regenerates_exact_bytes(capture, monkeypatch, capsys):
    first, second = (manual._LOCAL / "runs" / f"{name}.json" for name in ("m3-test", "m4-test"))
    _saved(capture, "single-pass", first)
    _saved(capture, "agent", second)
    blocked = Mock(side_effect=AssertionError("offline packet must never start capture"))
    monkeypatch.setattr(baseline, "live_manifest", blocked)
    monkeypatch.setattr(baseline, "live_attempt", blocked)
    randomness = Mock(return_value=bytes(range(32)))
    monkeypatch.setattr(manual.secrets, "token_bytes", randomness)

    command = ["packet", "m3-test", "m4-test", "review-01"]
    assert manual.main(command) == 0
    result = json.loads(capsys.readouterr().out)
    packet_path, private_path = map(Path, (result["review_packet"], result["private_key"]))
    assert packet_path.name == "review.json"
    assert packet_path.parent != private_path.parent
    packet_bytes = packet_path.read_bytes()
    private = json.loads(private_path.read_bytes())
    packet = json.loads(packet_bytes)
    assert set(packet) == {"cases"}
    assert {case["id"] for case in packet["cases"]} == MANUAL_IDS
    assert {mapping["Response A"] for mapping in private["assignment"].values()} == {
        "agent",
        "single-pass",
    }
    for case in packet["cases"]:
        assert set(case["responses"]) == {"Response A", "Response B"}
        for label, answer in case["responses"].items():
            assert answer["argv"] == ["--example", "literal value"]
            assert answer["env"] == {"SETTING": "candidate value"}
            assert answer["preflight"]["issues"][0]["message"] == "A supplied value may be ignored."
            assert answer["manual_command_available"]
            if private["assignment"][case["id"]][label] == "agent":
                assert "The CLI overrides the environment." in answer["explanation"]
                assert "supported interpretation" in answer["uncertainty"][0]
            else:
                assert answer["explanation"] == "The CLI takes precedence over the environment."
    response_bytes = json.dumps([case["responses"] for case in packet["cases"]]).encode()
    for hidden in (
        b"LangGraph",
        b"attempts",
        b"trace",
        b"m3-test",
        b"m4-test",
        b"deterministic intent",
        b"Repeated failed",
        b"budget exhausted",
        b"previous_scores",
        b"interpreter",
        b"seed",
    ):
        assert hidden not in response_bytes

    packet_path.unlink()
    assert manual.main(command) == 0
    assert packet_path.read_bytes() == packet_bytes
    randomness.assert_called_once_with(32)
    blocked.assert_not_called()

    # New report bytes require a new key even when the captured payload is equivalent.
    first.write_bytes(first.read_bytes() + b"\n")
    assert manual.main(command) == 2
    assert "different captured bytes" in capsys.readouterr().err


@pytest.mark.parametrize("issue", ["partial", "provenance", "question"])
def test_packet_refuses_incompatible_inputs(capture, tmp_path, issue):
    dataset, fingerprint, _ = capture
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    _saved(capture, "single-pass", first)
    run = _saved(capture, "agent", second)
    key = dataset["cases"][0]["id"]
    if issue == "partial":
        del run["attempts"][key]
        expected = "complete captures"
    elif issue == "provenance":
        run["manifest"]["environment_sha256"] = "other environment"
        expected = "Capture provenance differs"
    else:
        run["attempts"][key]["report"]["question"] += " edited"
        expected = "Saved question"
    second.write_text(json.dumps(run))
    with pytest.raises(ValueError, match=expected):
        manual.create_packet(first, second, "review", dataset, fingerprint)
    assert not (manual._LOCAL / "keys").exists()


def test_packet_reports_missing_response_without_raw_error():
    assert manual._project(
        {
            "report": None,
            "error_category": "timeout",
            "error": "LangGraph trace with secret detail",
        }
    ) == {"response_available": False, "capture_error": "timeout"}
