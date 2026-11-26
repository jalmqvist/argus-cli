import copy
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_generation_baseline import CITATION, SETTINGS, attempt, case, gold, report

from eval.generation import baseline, paired, scoring, timed_ask

ABSTAIN = {"verification": "abstained", "diagnostic_codes": []}
AGENT_ID = "m4-langgraph-v1"
VIOLATION = {"target": "--strategy", "operator": "exact", "values": ["MR32"]}
CHECK = {"satisfied": [], "violated": [VIOLATION], "unresolved": []}


def step(structure="passed", preflight="validated", intent=None, elapsed=1.5):
    return {
        "structural_validation": structure,
        "preflight_status": preflight,
        "intent_check": intent,
        "generation_seconds": elapsed,
    }


def m4(*steps, **changes):
    calls = len(steps)
    return report(
        **{
            "workflow": AGENT_ID,
            "intent_status": "consistent_with_explicit_constraints",
            "intent_coverage": "enforced",
            "intent_check": {"satisfied": [VIOLATION], "violated": [], "unresolved": []},
            "provenance": {**report()["provenance"], "index_sha256": "index"},
            "reserved_calls": calls,
            "model_calls": calls,
            "repair_count": max(calls - 1, 0),
            "attempts": list(steps),
            **changes,
        }
    )


def saved(dataset, attempts, *, agent=True, selected=None):
    manifest = {
        "selected": selected if selected is not None else [item["id"] for item in dataset["cases"]],
        "dataset_sha256": "fixture",
        "source": report()["provenance"],
        "index_sha256": "index",
        "retrieval": report()["retrieval"],
        "indexed_citations": {"spec-id": CITATION},
    }
    if agent:
        manifest.update(workflow="agent", agent={"workflow_id": AGENT_ID, "max_reserved_calls": 3})
    return {"format": 1, "manifest": manifest, "attempts": attempts}


def score_one(reply, *goldens):
    dataset = {"cases": [case(*goldens)]}
    run = saved(dataset, {"fixture": attempt(reply)})
    result = paired.summarize(run, dataset, "fixture")
    return result["cases"]["fixture"], result["agent"]["cases"]["fixture"]


def test_historical_summary_is_byte_equivalent_and_unchanged():
    dataset = {
        "cases": [case(gold(), key="pass"), case(ABSTAIN, key="review"), case(gold(), key="error")]
    }
    abstain = report(
        verification="abstained",
        command=None,
        argv=[],
        env={},
        citations=[],
        preflight=None,
        preflight_validation="not_run",
        uncertainty=["Unsupported"],
    )
    historical = saved(
        dataset,
        {
            "pass": attempt(report()),
            "review": attempt(abstain),
            "error": attempt(None, "timeout"),
        },
        agent=False,
    )
    original = copy.deepcopy(historical)
    expected = scoring.summarize(historical, dataset, "fixture")
    assert json.dumps(paired.summarize(historical, dataset, "fixture")) == json.dumps(expected)
    assert expected["outcomes"] == {"pass": 1, "review": 1, "error": 1}
    assert historical == original


def test_one_pass_and_repaired_recipes_credit_only_real_passes():
    one, first = score_one(m4(step()), gold())
    assert one["outcome"] == "pass"
    assert first["initial_recipe_pass"]
    assert first["validated_recipe"]
    assert not first["recovered_to_pass"]
    repaired, final = score_one(m4(step("failed", "not_run"), step()), gold())
    assert repaired["outcome"] == "pass"
    assert final["invalid_to_valid_structure"]
    assert final["recovered_to_pass"]
    assert not final["initial_recipe_pass"]
    assert final["generation_seconds_by_attempt"] == [1.5, 1.5]

    wrong, metrics = score_one(
        m4(
            step("failed", "not_run"),
            step(intent=CHECK),
            argv=["--strategy", "TF4"],
            command=None,
            verification="abstained",
            intent_check=CHECK,
            intent_status="inconsistent",
        ),
        gold(),
    )
    assert wrong["outcome"] == "fail"
    assert metrics["invalid_to_valid_structure"]
    assert metrics["final_preflight_passed_with_explicit_violations"]
    assert not metrics["recovered_to_pass"]


def test_warning_recipe_uses_frozen_diagnostic_score():
    score, metrics = score_one(
        m4(
            step(preflight="validated_with_warnings"),
            verification="validated_with_warnings",
            preflight={"issues": [{"code": "WARNING"}]},
        ),
        gold(verification="validated_with_warnings", codes=["WARNING"]),
    )
    assert score["outcome"] == "pass"
    assert metrics["validated_recipe"]


def test_early_abstention_supplement_preserves_historical_failure():
    early = m4(
        verification="abstained",
        command=None,
        argv=None,
        env=None,
        citations=[],
        preflight=None,
        structural_validation="not_run",
        preflight_validation="not_run",
        intent_coverage="unresolved",
        intent_status="unverified",
        intent_check=None,
        reason="Missing strategy",
        uncertainty=["Missing strategy"],
    )
    outcome, metrics = score_one(early, ABSTAIN)
    assert outcome["outcome"] == "fail"
    assert metrics["early_abstention_review_candidate"]
    assert metrics["early_abstention"]
    assert not metrics["correct_abstention_pending_review"]
    assert not metrics["validated_recipe"]
    _, unnecessary = score_one(early, gold())
    assert unnecessary["abstention_without_gold_alternative"]
    assert not unnecessary["early_abstention_review_candidate"]


@pytest.mark.parametrize(("validation", "expected"), [("passed", "review"), ("failed", "fail")])
def test_abstention_still_requires_structure_and_review(validation, expected):
    reply = m4(
        step(validation, "not_run"),
        verification="abstained",
        command=None,
        argv=[],
        env={},
        citations=[],
        preflight=None,
        preflight_validation="not_run",
        structural_validation=validation,
        uncertainty=["Unsupported"],
    )
    result, metrics = score_one(reply, ABSTAIN)
    assert result["outcome"] == expected
    assert not metrics["early_abstention"]
    assert metrics["correct_abstention_pending_review"] is (validation == "passed")


def test_authoritative_rejection_and_intent_mismatch_are_distinct():
    allowed = gold(verification="rejected", codes=["STRATEGY_UNKNOWN"])
    rejected = m4(
        step(preflight="rejected"),
        verification="rejected",
        command=None,
        preflight_validation="failed",
        preflight={"issues": [{"code": "STRATEGY_UNKNOWN"}]},
    )
    result, metrics = score_one(rejected, ABSTAIN, allowed)
    assert result["outcome"] == "pass"
    assert metrics["correct_authoritative_rejection"]
    wrong = {**rejected, "argv": ["--strategy", "TF4"], "intent_check": CHECK}
    result, metrics = score_one(wrong, ABSTAIN, allowed)
    assert result["outcome"] == "fail"
    assert metrics["rejection_with_intent_violation"]
    assert not metrics["correct_authoritative_rejection"]


def test_budget_exhaustion_and_cap_violations_are_visible():
    exhausted = m4(
        *(step(intent=CHECK) for _ in range(3)),
        command=None,
        verification="abstained",
        argv=["--strategy", "TF4"],
        intent_check=CHECK,
        intent_status="inconsistent",
        reason="Proposal violates intent. Generation-call budget exhausted.",
    )
    score, metrics = score_one(exhausted, gold())
    assert score["outcome"] == "fail"
    assert metrics["budget_exhaustion"]
    assert metrics["repair_terminal"] == "abstained"
    assert metrics["preflight_passed_with_explicit_violations_attempts"] == 3
    assert not metrics["recovered_to_pass"]
    assert not metrics["call_cap_violation"]
    _, breach = score_one({**exhausted, "reserved_calls": 4}, gold())
    assert breach["call_cap_violation"]
    _, repeated = score_one(
        {**exhausted, "reason": "Violation. Repeated failed candidate."}, gold()
    )
    assert repeated["repeated_candidate_stop"]


@pytest.fixture
def runs():
    dataset = {"cases": [case(gold(), key=key) for key in ("A", "B", "C")]}
    wrong = report(argv=["--strategy", "TF4"])
    single = saved(
        dataset, {"A": attempt(wrong), "B": attempt(report()), "C": attempt(wrong)}, agent=False
    )
    blocked = m4(
        step(intent=CHECK),
        command=None,
        verification="abstained",
        argv=["--strategy", "TF4"],
        intent_check=CHECK,
        intent_status="inconsistent",
    )
    agent = saved(dataset, {"A": attempt(m4(step())), "B": attempt(blocked), "C": attempt(blocked)})
    return dataset, single, agent


def test_pair_separates_regressions_new_passes_and_withholding(runs):
    dataset, single, agent = runs
    result = paired.compare(single, agent, dataset, "fixture")
    assert result["scope"] == "full"
    assert result["transitions"] == {"fail → pass": 1, "pass → fail": 1, "fail → fail": 1}
    assert result["new_passes"] == ["A"]
    assert result["regressions"] == ["B"]
    assert result["wrong_recipe_withheld_without_new_pass"] == ["C"]
    assert result["single_pass"]["recipes_released"] == 3
    assert result["agent"]["recipes_released"] == 1
    assert result["agent"]["preflight_passed_with_explicit_violations_attempts"] == 2
    assert result["cases"]["A"]["model_calls_delta"] == 0


def test_comparison_rejects_partial_and_labels_matched_subsets(runs):
    dataset, first, second = runs
    del second["attempts"]["C"]
    with pytest.raises(ValueError, match="completed runs"):
        paired.compare(first, second, dataset, "fixture")
    second["manifest"]["selected"].remove("C")
    with pytest.raises(ValueError, match="identical selected"):
        paired.compare(first, second, dataset, "fixture")
    first["manifest"]["selected"].remove("C")
    del first["attempts"]["C"]
    assert paired.compare(first, second, dataset, "fixture")["scope"] == "subset"


def test_incompatible_comparison_requires_explicit_override(runs):
    dataset, first, second = runs
    second["manifest"].update(
        index_sha256="other", model={"name": "other"}, machine={"platform": "other"}
    )
    with pytest.raises(ValueError, match="index_sha256"):
        paired.compare(first, second, dataset, "fixture")
    compared = paired.compare(first, second, dataset, "fixture", allow_provenance_mismatch=True)
    assert "index_sha256" in compared["provenance_mismatches"]
    assert {"model", "machine"} <= compared["configuration_differences_or_unknowns"].keys()
    second["manifest"]["dataset_sha256"] = "other"
    with pytest.raises(ValueError, match="dataset hash"):
        paired.compare(first, second, dataset, "fixture", allow_provenance_mismatch=True)


def test_offline_comparison_and_agent_score_cli(runs, tmp_path, monkeypatch, capsys):
    dataset, first, second = runs
    for key, run in (("m3", first), ("m4", second)):
        (tmp_path / f"{key}.json").write_text(json.dumps(run))
    monkeypatch.setattr(baseline, "REPORTS", tmp_path)
    monkeypatch.setattr(baseline, "read_dataset", lambda: (dataset, "fixture"))
    monkeypatch.setattr(baseline, "live_manifest", Mock(side_effect=AssertionError("live request")))
    assert baseline.main(["score", "m4"]) == 0
    assert json.loads(capsys.readouterr().out)["agent"]["counts"]["commands_released"] == 1
    assert baseline.main(["compare", "m3", "m4"]) == 0
    assert json.loads(capsys.readouterr().out)["scope"] == "full"


def test_runner_adds_agent_flag_and_rejects_wrong_workflow_or_index(monkeypatch):
    manifest = {
        "workflow": "agent",
        "agent": {"workflow_id": AGENT_ID},
        "model": report()["model"],
        "settings": SETTINGS,
        "source": report()["provenance"],
        "index_sha256": "index",
        "retrieval": report()["retrieval"],
        "wall_timeout_seconds": 660,
    }
    invoke = Mock(
        return_value=subprocess.CompletedProcess(
            [],
            0,
            json.dumps({"report": m4(step()), "generation_seconds": 1.5}),
            "",
        )
    )
    monkeypatch.setattr(baseline.subprocess, "run", invoke)
    observed = baseline.attempt_case(case(gold()), Path("fixture.yaml"), manifest)
    assert "--agent" in invoke.call_args.args[0]
    baseline.verify_attempt(observed, manifest)
    with pytest.raises(ValueError, match="different workflow"):
        baseline.verify_attempt(attempt(report()), manifest)
    with pytest.raises(ValueError, match="different index fingerprint"):
        baseline.verify_attempt(
            attempt(m4(step(), provenance={**report()["provenance"], "index_sha256": "wrong"})),
            manifest,
        )


def test_resume_refuses_mixing_workflows(runs, tmp_path):
    dataset, single, agent = runs
    path = tmp_path / "run.json"
    path.write_text(json.dumps(single))
    execute = Mock(side_effect=AssertionError("unexpected execution"))
    with pytest.raises(ValueError, match="Incompatible resume"):
        baseline.resume_run(path, agent["manifest"], dataset, "fixture", execute)
    execute.assert_not_called()


def test_agent_timing_sums_existing_attempt_times(monkeypatch, capsys):
    reply = m4(step("failed", "not_run", elapsed=1), step(elapsed=2.25))
    original = timed_ask.ask.generate

    def fake_main(argv):
        assert argv == ["ask", "--agent", "--", "fixture"]
        assert timed_ask.ask.generate is original
        print(json.dumps(reply))
        return 0

    monkeypatch.setattr(timed_ask, "main", fake_main)
    assert timed_ask.run(["ask", "--agent", "--", "fixture"]) == 0
    assert json.loads(capsys.readouterr().out) == {"report": reply, "generation_seconds": 3.25}


def test_agent_records_raw_attempts_and_resume_skips_them(tmp_path, monkeypatch):
    dataset = {"cases": [case(gold(), key=key) for key in ("A", "B")]}
    run = saved(dataset, {})
    manifest = run["manifest"]
    path = tmp_path / "report.json"
    config = tmp_path / "sources.yaml"
    config.write_text("fixture")
    index = tmp_path / "index.json"
    index.write_text("fixture")
    monkeypatch.setattr(baseline, "INDEX", index)
    manifest.update(
        config=str(config),
        config_sha256=baseline.sha(config.read_bytes()),
        index_sha256=baseline.sha(index.read_bytes()),
        settings=SETTINGS,
        model=report()["model"],
    )
    reply = m4(step(), provenance={**manifest["source"], "index_sha256": manifest["index_sha256"]})
    fixture = attempt(reply)
    execute = Mock(side_effect=[fixture, KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        baseline.resume_run(path, manifest, dataset, "fixture", execute)
    partial = json.loads(path.read_bytes())
    assert partial["summary"]["status"] == "partial"
    assert partial["attempts"]["A"] == {**fixture, "question": dataset["cases"][0]["question"]}
    assert partial["attempts"]["A"]["report"]["attempts"] == reply["attempts"]

    resume = Mock(return_value=fixture)
    final = baseline.resume_run(path, manifest, dataset, "fixture", resume)
    assert resume.call_args.args[0]["id"] == "B"
    resume.assert_called_once()
    assert final["status"] == "complete_full"
    assert final["agent"]["model_calls"] == 2
    assert final["agent"]["generation_attempt_seconds"]["samples"] == 2


def test_comparison_records_review_to_pass():
    rejected_gold = gold(verification="rejected", codes=["STRATEGY_UNKNOWN"])
    dataset = {"cases": [case(ABSTAIN, rejected_gold)]}
    abstained = report(
        verification="abstained",
        command=None,
        argv=[],
        env={},
        citations=[],
        preflight=None,
        preflight_validation="not_run",
        uncertainty=["Unsupported"],
    )
    rejected = m4(
        step(preflight="rejected"),
        verification="rejected",
        command=None,
        preflight_validation="failed",
        preflight={"issues": [{"code": "STRATEGY_UNKNOWN"}]},
    )
    single = saved(dataset, {"fixture": attempt(abstained)}, agent=False)
    agent = saved(dataset, {"fixture": attempt(rejected)})
    result = paired.compare(single, agent, dataset, "fixture")
    assert result["transitions"] == {"review → pass": 1}
    assert result["new_passes"] == ["fixture"]
    assert result["agent"]["recipes_released"] == 0
