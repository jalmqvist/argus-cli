import json
from dataclasses import replace
from pathlib import Path

import pytest

from argus_cli.provenance import spec_sha256
from argus_cli.v2_authorization import (
    FinalProvenance,
    MaterialIntentAssessment,
    PreflightObservation,
    SnapshotIdentity,
    ValidationObservation,
    VerifiedSnapshot,
    bind,
    evaluate,
)
from argus_cli.v2_contract import Diagnostic, Preflight, Settings, Span, UnresolvedRequirement
from argus_cli.v2_intent import extract

FIXTURE = Path(__file__).resolve().parents[1] / "eval/m4v2/authorization-development-v1.json"
CASES = json.loads(FIXTURE.read_text())["cases"]
_QUESTION = "Choose strategies TF40 then MR70 and set seed 17 CLI only."
_ARGV = ["--strategy", "TF40", "--strategy", "MR70", "--experiment-seed", "17"]
_SPEC = {
    "arguments": [
        {
            "flags": [flag],
            "action": action,
            "nargs": None,
            "post_parse_choices": choices,
        }
        for flag, action, choices in (
            ("--strategy", "append", ["TF40", "MR70"]),
            ("--phaseaware-tf", "store", ["TF40"]),
            ("--experiment-seed", "store", None),
            ("--output-dir", "store", None),
        )
    ],
    "env": [
        {"name": name, "scope": "launch_selector", "parser": parser}
        for name, parser in (("EXPERIMENT_SEED", "int"), ("ACTIVE_PAIRS", "csv"))
    ],
    "precedence": [{"order": ["--experiment-seed", "EXPERIMENT_SEED", "42"]}],
}
_TARGETS = (
    "--strategy",
    "--phaseaware-tf",
    "--experiment-seed",
    "--output-dir",
    "EXPERIMENT_SEED",
    "ACTIVE_PAIRS",
    "*",
)


def preflight_result(outcome, diagnostic="Synthetic MPML diagnostic."):
    issues = []
    if outcome in {"warnings_only", "accepted_with_warnings", "rejected"}:
        issues.append(
            Diagnostic(
                code="SYNTHETIC_ISSUE",
                severity="error" if outcome == "rejected" else "warning",
                message=diagnostic,
            )
        )
    return Preflight(outcome=outcome, diagnostics=issues)


def inputs(case):
    """Construct trusted synthetic attestations out of band from model-controlled fields."""
    identity = SnapshotIdentity(
        "revision-A", case.get("dirty", False), spec_sha256(_SPEC), "a" * 64
    )
    snapshot = VerifiedSnapshot(
        identity,
        json.dumps(_SPEC).encode(),
        frozenset({"published", "unrelated"}),
        case.get("snapshot_authority", "trusted_adapter"),
    )
    request = extract(case.get("question", _QUESTION), _SPEC)
    settings = Settings(
        argv=case.get("argv", _ARGV) + case.get("extra_argv", []), env=case.get("env", {})
    )
    inherited_env = case.get("inherited_env", {})
    binding = bind(snapshot, request, settings, inherited_env)
    mismatch = case.get("preflight_mismatch")
    preflight_binding = binding
    if mismatch in {"candidate_sha256", "inherited_env_sha256"}:
        preflight_binding = replace(binding, **{mismatch: "b" * 64})
    elif mismatch:
        preflight_binding = replace(binding, snapshot=replace(identity, **{mismatch: "b" * 64}))
    cited_ids = tuple(case.get("cited_ids", ["published"]))
    return {
        "request": request,
        "settings": settings,
        "snapshot": snapshot,
        "inherited_env": inherited_env,
        "cited_ids": cited_ids,
        "validation": ValidationObservation(
            binding,
            "trusted_adapter",
            "passed",
            "manual_mpml_launch",
            cited_ids,
            tuple(
                tuple(pair)
                for pair in case.get("support", [(name, "published") for name in _TARGETS])
            ),
        ),
        "preflight": PreflightObservation.capture(
            preflight_binding,
            case.get("preflight_authority", "trusted_adapter"),
            preflight_result(
                case.get("preflight", "accepted"),
                case.get("diagnostic", "Synthetic MPML diagnostic."),
            ),
        ),
        "final_provenance": FinalProvenance(
            identity, "trusted_adapter", case.get("final_status", "verified")
        ),
        "material": None
        if case.get("omit_material")
        else MaterialIntentAssessment(
            binding,
            case.get("material_authority", "trusted_adapter"),
            case.get("material", "verified"),
            case.get("effective_configuration", "verified"),
        ),
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_adversarial_fixtures(case):
    args = inputs(case)
    result = evaluate(**args)
    assert result.blockers == tuple(case["expected_blockers"])
    assert result.eligible_from_trusted_offline_observations == (not case["expected_blockers"])
    assert result.preflight == args["preflight"].result()
    assert not hasattr(result, "command")
    assert not hasattr(result, "settings")


_MUTATIONS = [
    ("required-value", {"argv": [*_ARGV[:-1], "19"]}, "recognized_constraints"),
    ("missing-argument", {"argv": _ARGV[:-2]}, "recognized_constraints"),
    (
        "reordered-identifiers",
        {"argv": ["--strategy", "MR70", "--strategy", "TF40", *_ARGV[-2:]]},
        "recognized_constraints",
    ),
    (
        "wrong-channel",
        {"argv": _ARGV[:-2], "env": {"EXPERIMENT_SEED": "17"}},
        "recognized_constraints",
    ),
    ("prohibited-override", {"env": {"EXPERIMENT_SEED": "17"}}, "recognized_constraints"),
    ("candidate-fingerprint", {"preflight_mismatch": "candidate_sha256"}, "preflight_binding"),
    ("source-revision", {"preflight_mismatch": "source_revision"}, "preflight_binding"),
    ("spec-digest", {"preflight_mismatch": "spec_sha256"}, "preflight_binding"),
    ("index-digest", {"preflight_mismatch": "index_sha256"}, "preflight_binding"),
    ("preflight-warnings-only", {"preflight": "warnings_only"}, "preflight_acceptance"),
    ("preflight-unavailable", {"preflight": "unavailable"}, "preflight_acceptance"),
    ("unresolved-intent", {"material": "unresolved"}, "material_intent"),
    ("residual-requirement", {}, "unresolved_requirements"),
]


@pytest.mark.parametrize(
    ("name", "changes", "blocker"), _MUTATIONS, ids=[item[0] for item in _MUTATIONS]
)
def test_invalidating_mutation(name, changes, blocker):
    base = inputs({})
    assert evaluate(**base).eligible_from_trusted_offline_observations
    mutated = inputs(changes)
    if name == "residual-requirement":
        request = mutated["request"]
        text = request.analysis.question
        gap = UnresolvedRequirement(
            reason="A material condition remains unresolved.",
            span=Span(start=0, end=len(text), text=text),
        )
        analysis = request.analysis.model_copy(update={"unresolved_material": [gap]})
        mutated["request"] = replace(request, analysis=analysis)
        binding = bind(mutated["snapshot"], mutated["request"], mutated["settings"], {})
        # Keep all observations current so only the residual independently blocks.
        for field in ("validation", "preflight", "material"):
            mutated[field] = replace(mutated[field], binding=binding)
    assert blocker in evaluate(**mutated).blockers
    assert not evaluate(**mutated).eligible_from_trusted_offline_observations


@pytest.mark.parametrize(
    ("field", "changes", "blocker"),
    [
        ("settings", Settings(argv=[*_ARGV[:-1], "18"], env={}), "preflight_binding"),
        ("settings", Settings(argv=_ARGV, env={"ACTIVE_PAIRS": "EURJPY"}), "preflight_binding"),
        ("inherited_env", {"EXPERIMENT_SEED": "99"}, "preflight_binding"),
        ("cited_ids", ("published", "unrelated"), "setting_support"),
    ],
)
def test_old_observations_cannot_be_replayed(field, changes, blocker):
    args = inputs({})
    args[field] = changes
    assert blocker in evaluate(**args).blockers


def test_final_snapshot_must_match_even_when_attested_verified():
    args = inputs({})
    final = args["final_provenance"]
    args["final_provenance"] = replace(final, identity=replace(final.identity, source_revision="B"))
    assert evaluate(**args).blockers == ("provenance",)


def test_spec_bytes_and_preflight_capture_are_snapshots():
    args = inputs({"preflight": "accepted_with_warnings"})
    snapshot = args["snapshot"]
    spec = snapshot.read_spec()
    spec["arguments"].clear()
    assert snapshot.read_spec()["arguments"]
    with pytest.raises(ValueError, match="does not match"):
        replace(snapshot, spec_json=json.dumps(spec).encode())
    result = args["preflight"].result()
    result.diagnostics.clear()
    assert args["preflight"].result().diagnostics


def test_malformed_preflight_cannot_supply_an_acceptance():
    args = inputs({})
    args["preflight"] = replace(
        args["preflight"], result_json=b'{"outcome":"accepted","diagnostics":[{}]}'
    )
    result = evaluate(**args)
    assert result.preflight.outcome == "unavailable"
    assert result.blockers == ("preflight_acceptance",)
