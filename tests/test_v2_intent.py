import json
from collections import Counter
from pathlib import Path

import pytest

from argus_cli.v2_intent import InterpretationRules, check_candidate, extract

FIXTURE = Path(__file__).resolve().parents[1] / "eval/m4v2/intent-development-v1.json"
CASES = json.loads(FIXTURE.read_text())["cases"]


@pytest.fixture
def spec():
    # Public synthetic IDs. Option names, arity and precedence mirror the published surface.
    return {
        "arguments": [
            {"flags": [f"--{flag}"], "action": action, "nargs": None, "post_parse_choices": choices}
            for flag, action, choices in (
                ("strategy", "append", ["TF40", "MR70"]),
                ("phaseaware-tf", "store", ["TF40"]),
                ("phaseaware-mr", "store", ["MR70"]),
                ("experiment-seed", "store", None),
                ("experiment-variant", "store", None),
                ("output-dir", "store", None),
            )
        ],
        "env": [
            {"name": name, "scope": "launch_selector", "parser": parser}
            for name, parser in (
                ("ACTIVE_PAIRS", "csv"),
                ("EXPERIMENT_SEED", "int"),
                ("EXPERIMENT_VARIANT", "enum"),
                ("MPML_OUTPUT_DIR", "path"),
            )
        ],
        "precedence": [
            {"order": [flag, name, fallback]}
            for flag, name, fallback in (
                ("--experiment-seed", "EXPERIMENT_SEED", "42"),
                ("--experiment-variant", "EXPERIMENT_VARIANT", "A"),
                ("--output-dir", "MPML_OUTPUT_DIR", "generated directory"),
            )
        ],
    }


def _key(value):
    return json.dumps(value, sort_keys=True)


def test_development_metrics(spec):
    true_positive = predicted = expected = coverage_correct = false_enforced = 0
    false_accept = false_reject = acceptable = unacceptable = unresolved = 0
    differences = []
    for case in CASES:
        result = extract(case["question"], spec)
        analysis = result.analysis
        reported = [_key(item.model_dump()) for item in analysis.requirements]
        gold = [_key(item) for item in case["requirements"]]
        true_positive += sum((Counter(reported) & Counter(gold)).values())
        predicted += len(reported)
        expected += len(gold)
        unresolved += len(analysis.unresolved_material)
        coverage_correct += result.coverage == case["coverage"]
        false_enforced += result.coverage == "enforced" and case["coverage"] != "enforced"
        if reported != gold:
            differences.append((case["id"], "requirements", reported, gold))
        for field, actual in (
            ("route", analysis.route),
            ("coverage", result.coverage),
            ("unresolved", [item.model_dump() for item in analysis.unresolved_material]),
        ):
            if actual != case[field]:
                differences.append((case["id"], field, actual, case[field]))
        for candidate in case["candidates"]:
            checked = check_candidate(result, candidate["argv"], candidate["env"], spec)
            # Fixture-level consistency label, never a release verdict.
            consistent = result.coverage == "enforced" and not (
                checked.violated or checked.unresolved or checked.candidate_issues
            )
            acceptable += candidate["consistent"]
            unacceptable += not candidate["consistent"]
            false_accept += consistent and not candidate["consistent"]
            false_reject += not consistent and candidate["consistent"]
            if consistent != candidate["consistent"]:
                differences.append((case["id"], "candidate", candidate, checked))
    print(
        f"precision={true_positive}/{predicted}, recall={true_positive}/{expected}, "
        f"coverage={coverage_correct}/{len(CASES)}, false enforced={false_enforced}/"
        f"{sum(case['coverage'] != 'enforced' for case in CASES)}, "
        f"false accept={false_accept}/{unacceptable}, false reject={false_reject}/{acceptable}, "
        f"unresolved={unresolved}"
    )
    assert not differences, "\n".join(map(str, differences))


def test_phrase_bindings_are_spec_gated(spec):
    rules = InterpretationRules((("randomizer", "--experiment-seed"),))
    assert extract("Pin randomizer 77.", spec, rules).coverage == "enforced"
    spec["arguments"] = []
    result = extract("Pin randomizer 77.", spec, rules)
    assert result.coverage == "unresolved"
    assert result.analysis.requirements == []


def test_checker_reports_distinct_constraint_outcomes(spec):
    result = extract("Use seed 47; choose variant B; set output directory.", spec)
    checked = check_candidate(
        result, ["--experiment-seed", "47", "--experiment-variant", "C"], {"GHOST": "x"}, spec
    )
    assert [item.target for item in checked.satisfied] == ["--experiment-seed"]
    assert [item.target for item in checked.violated] == ["--experiment-variant"]
    assert checked.unresolved[0].span.text == "set output directory."
    assert checked.candidate_issues == ("Unrecognized launch environment override: GHOST",)


@pytest.mark.parametrize(
    "question",
    [
        "--experiment-seed 381?",
        "Consider “use seed 381 and set variant B and use strategy TF40”.",
        "Do not set EXPERIMENT_SEED=381 and EXPERIMENT_VARIANT=B.",
    ],
)
def test_context_does_not_promote_mentioned_options_to_requirements(spec, question):
    result = extract(question, spec)
    assert result.coverage == "unresolved"
    assert not result.analysis.requirements
    assert result.analysis.unresolved_material
