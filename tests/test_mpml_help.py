import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from argus_cli import mpml_help
from argus_cli.adapters.mpml import BridgeError, BridgeResult
from argus_cli.cli import main
from argus_cli.config import Source
from argus_cli.provenance import Revision

SPEC = {
    "schema_version": 1,
    "arguments": [
        {
            "flags": ["-m", "--mode"],
            "default": None,
            "choices": None,
            "post_parse_choices": ["toy"],
            "post_parse_choices_source": "toy_registry",
        },
        {"flags": ["--format"], "default": "text", "choices": ["text", "json"]},
    ],
    "env": [
        {"name": "TOY_MODE", "default": "toy", "read_in": ["toy.py"], "semantics": "Toy mode."}
    ],
    "precedence": [{"setting": "mode", "order": ["--mode", "TOY_MODE", "toy"]}],
    "rules": [{"code": "TOY_WARNING", "summary": "Synthetic warning."}],
    "registries": {"strategies": {"ids": ["toy"]}},
    "source_edit_only": [{"name": "TOY_CONSTANT", "category": "fixtures"}],
}


@pytest.fixture
def source(tmp_path, monkeypatch):
    source = Source(
        "mpml",
        tmp_path,
        Path(sys.executable),
        "mpml_v1",
        "mpml.spec",
        "mpml.preflight",
        "main.py",
        (),
    )
    monkeypatch.setattr("argus_cli.cli.load_sources", lambda _: {"mpml": source})
    monkeypatch.setattr(mpml_help, "revision", lambda _: Revision("fake-sha", True))
    monkeypatch.setattr(mpml_help, "spec", lambda _: BridgeResult(0, SPEC, ""))
    return source


@pytest.mark.parametrize(
    ("tokens", "field", "expected"),
    [
        (["inspect", "--mode"], "argument", SPEC["arguments"][0]),
        (["inspect", "-m"], "precedence", SPEC["precedence"]),
        (["inspect", "--", "--format"], "argument", SPEC["arguments"][1]),
        (["inspect", "TOY_MODE"], "environment", SPEC["env"][0]),
        (["explain", "TOY_MODE"], "precedence", SPEC["precedence"]),
        (["explain", "precedence"], "details", SPEC["precedence"]),
        (["explain", "mode"], "details", SPEC["precedence"][0]),
        (["explain", "warnings"], "details", SPEC["rules"]),
        (["explain", "TOY_WARNING"], "details", SPEC["rules"][0]),
        (["explain", "strategies"], "registry", SPEC["registries"]["strategies"]),
        (["explain", "source-edit-only"], "details", SPEC["source_edit_only"]),
    ],
)
def test_lookup_uses_published_spec(source, capsys, tokens, field, expected):
    assert main(["--config", "fixture.yaml", *tokens]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report[field] == expected
    canonical_spec = json.dumps(SPEC, indent=2, sort_keys=True) + "\n"
    assert report["provenance"] == {
        "source": "python -m mpml.spec",
        "repository": str(source.root),
        "interpreter": str(source.python),
        "git_sha": "fake-sha",
        "dirty": True,
        "schema_version": 1,
        "spec_sha256": hashlib.sha256(canonical_spec.encode()).hexdigest(),
    }


def test_unknown_flag_fails(source, capsys):
    assert main(["inspect", "--absent"]) == 2
    captured = capsys.readouterr()
    assert "Unknown MPML inspect query '--absent'" in captured.err
    assert not captured.out


@pytest.mark.parametrize(
    ("severity", "preflight_exit", "verification", "exit_code"),
    [
        (None, 0, "validated", 0),
        ("warning", 0, "validated_with_warnings", 0),
        ("error", 2, "rejected", 1),
        ("error", 0, "rejected", 1),
        ("warning", 1, "unverified", 1),
        ("unexpected", 0, "unverified", 1),
    ],
)
def test_recipe_reports_preflight(
    source, capsys, monkeypatch, severity, preflight_exit, verification, exit_code
):
    issues = (
        []
        if severity is None
        else [{"code": "TOY_WARNING", "severity": severity, "source": "toy", "message": "fixture"}]
    )
    preflight = Mock(return_value=BridgeResult(preflight_exit, {"issues": issues}, ""))
    monkeypatch.setattr(mpml_help, "preflight", preflight)
    assert main(["recipe", "defaults"]) == exit_code
    preflight.assert_called_once_with(source, [], overrides={})
    report = json.loads(capsys.readouterr().out)
    assert report["verification"] == verification
    assert report["preflight"]["issues"] == issues
    assert report["argv"] == []
    assert report["env"] == {}


def test_recipe_cannot_validate_if_preflight_is_unavailable(source, capsys, monkeypatch):
    monkeypatch.setattr(mpml_help, "preflight", Mock(side_effect=BridgeError("fixture error")))
    assert main(["recipe", "defaults"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["verification"] == "unverified"
    assert report["preflight_error"] == "fixture error"


def test_lookup_flag_handling_does_not_rewrite_preflight_argv(source, monkeypatch):
    preflight = Mock(return_value=BridgeResult(0, {"issues": []}, ""))
    monkeypatch.setattr("argus_cli.cli.preflight", preflight)
    assert main(["preflight", "--", "inspect", "--mode"]) == 0
    preflight.assert_called_once_with(source, ["inspect", "--mode"], overrides={})
