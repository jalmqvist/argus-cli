import json
import shlex
from pathlib import Path

import pytest
from pydantic import ValidationError

from argus_cli.v2_contract import RequestAnalysis, ResponseV2, Settings

FIXTURE = Path(__file__).resolve().parents[1] / "eval/m4v2/acceptance-v1.json"
CASES = json.loads(FIXTURE.read_text())["cases"]


def candidate(case):
    return case["synthetic_observations"].get(
        "settings", {"argv": ["--experiment-seed", "314"], "env": {}}
    )


def response(case):
    question = case["question"]
    route = case["expected_route"]
    observed = case["synthetic_observations"]
    outcome = observed.get("preflight", "accepted" if route in {"launch", "mixed"} else "not_run")
    warnings = outcome in {"warnings_only", "accepted_with_warnings"}
    diagnostics = []
    if warnings or outcome == "rejected":
        diagnostics.append(
            {
                "code": "SYNTHETIC_DIAGNOSTIC",
                "message": "Original synthetic diagnostic.",
                "severity": "warning" if warnings else "error",
            }
        )
    settings = Settings.model_validate(candidate(case))
    return {
        "schema_version": "argus-response-v2.0",
        "request": {
            "question": question,
            "route": route,
            "requirements": [],
            "unresolved_material": (
                [
                    {
                        "reason": "Value missing",
                        "span": {"start": 0, "end": len(question), "text": question},
                    }
                ]
                if route == "ambiguous"
                else []
            ),
        },
        "response_kind": "answer",
        "answer_status": "limited",
        "recipe_status": "withheld" if route != "informational" else "not_requested",
        "intent_coverage": "enforced" if route in {"launch", "mixed"} else "unresolved",
        "material_constraints_status": observed.get("material", "verified"),
        "explanation": "Synthetic explanation.",
        "citations": [{"evidence_id": "spec-1", "path": "spec.json", "heading": "Launch options"}],
        "provenance": {
            "source_revision": "synthetic",
            "source_dirty": False,
            "spec_sha256": "1" * 64,
            "index_sha256": "2" * 64,
        },
        "preflight": {"outcome": outcome, "diagnostics": diagnostics},
        "audit": {
            "candidate_sha256": settings.fingerprint(),
            "provenance": observed.get("provenance", "verified"),
            "structure": observed.get("structure", "passed"),
            "evidence": observed.get("evidence", "passed"),
            "evidence_ids": ["spec-1"],
            "release_scope": observed.get("scope", "manual_mpml_launch"),
        },
        "settings": None,
        "command": None,
    }


def with_command(payload):
    case = next(case for case in CASES if case["question"] == payload["request"]["question"])
    settings = candidate(case)
    return {
        **payload,
        "response_kind": "recipe",
        "recipe_status": (
            "validated_with_warnings"
            if payload["preflight"]["outcome"] == "accepted_with_warnings"
            else "validated"
        ),
        "settings": {"argv": list(settings["argv"]), "env": dict(settings["env"])},
        "command": shlex.join(["python", "main.py", *settings["argv"]]),
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_offline_acceptance(case):
    payload = response(case)
    value = ResponseV2.model_validate(payload)
    assert value.request.route == case["expected_route"]
    assert (not value.release_blockers()) == case["expected_release_eligible"]
    if case["expected_release_eligible"]:
        released = ResponseV2.model_validate(with_command(payload))
        assert released.preflight.model_dump() == payload["preflight"]
        assert ResponseV2.model_validate_json(released.model_dump_json()) == released
    else:
        with pytest.raises(ValidationError, match="command release blocked"):
            ResponseV2.model_validate(with_command(payload))


def valid_launch():
    return response(next(case for case in CASES if case["id"] == "multiple-cli"))


def test_grounded_answer_cannot_publish_settings_or_command():
    payload = response(CASES[0])
    payload["answer_status"] = "grounded"
    ResponseV2.model_validate(payload)
    for field, value in (("command", "python main.py"), ("settings", {"argv": [], "env": {}})):
        with pytest.raises(ValidationError, match="only a validated recipe"):
            ResponseV2.model_validate({**payload, field: value})
    with pytest.raises(ValidationError, match="grounded answers require"):
        ResponseV2.model_validate({**payload, "citations": []})


def test_confidence_cannot_replace_gate_observations():
    payload = with_command(valid_launch())
    payload["audit"]["structure"] = "unchecked"
    with pytest.raises(ValidationError, match="command release blocked: structure"):
        ResponseV2.model_validate(payload)
    payload["audit"]["confidence"] = 1.0
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ResponseV2.model_validate(payload)


def test_release_requires_exact_settings_and_cited_evidence():
    payload = with_command(valid_launch())
    payload["settings"]["argv"][-1] = "315"
    with pytest.raises(ValidationError, match="released settings"):
        ResponseV2.model_validate(payload)
    payload = with_command(valid_launch())
    payload["audit"]["evidence_ids"] = ["unknown"]
    with pytest.raises(ValidationError, match="command release blocked: evidence"):
        ResponseV2.model_validate(payload)


def test_warnings_cannot_disappear_into_clean_acceptance():
    case = next(case for case in CASES if case["id"] == "mixed-warning")
    payload = with_command(response(case))
    payload["recipe_status"] = "validated"
    with pytest.raises(ValidationError, match="matching preflight"):
        ResponseV2.model_validate(payload)
    payload["preflight"]["outcome"] = "accepted"
    with pytest.raises(ValidationError, match="contradicts authoritative diagnostics"):
        ResponseV2.model_validate(payload)


def test_advisory_route_cannot_override_unresolved_span():
    payload = with_command(valid_launch())
    question = payload["request"]["question"]
    payload["request"]["unresolved_material"] = [
        {"reason": "Unresolved path", "span": {"start": 0, "end": len(question), "text": question}}
    ]
    with pytest.raises(ValidationError, match="command release blocked: material_constraints"):
        ResponseV2.model_validate(payload)


def test_explicit_requirement_spans_preserve_text_and_order():
    question = "Use EURJPY before GBPJPY."
    request = {
        "question": question,
        "route": "launch",
        "requirements": [
            {
                "target": "pair",
                "operator": "ordered",
                "channel": "either",
                "values": ["EURJPY", "GBPJPY"],
                "span": {"start": 4, "end": 24, "text": question[4:24]},
            }
        ],
        "unresolved_material": [],
    }
    parsed = RequestAnalysis.model_validate(request)
    assert parsed.requirements[0].values == ["EURJPY", "GBPJPY"]
    request["requirements"][0]["span"]["text"] = "GBPJPY before EURJPY"
    with pytest.raises(ValidationError, match="span must match"):
        RequestAnalysis.model_validate(request)


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        ("release_scope", "unsupported", "manual_launch_scope"),
        ("provenance", "unchecked", "provenance"),
        ("candidate_sha256", None, "structure"),
    ],
)
def test_launch_route_cannot_override_independent_gate(field, value, blocker):
    payload = with_command(valid_launch())
    payload["audit"][field] = value
    with pytest.raises(ValidationError, match=f"command release blocked: {blocker}"):
        ResponseV2.model_validate(payload)


def test_legacy_fields_and_private_trace_are_not_public_v2_fields():
    for field in ("verification", "private_trace"):
        with pytest.raises(ValidationError, match=field):
            ResponseV2.model_validate({**valid_launch(), field: None})
