"""Evaluation-side graph metrics and paired comparisons over saved reports."""

from collections import Counter

from .scoring import latency_summary
from .scoring import summarize as historical_summary


def workflow(manifest):
    name = manifest.get("workflow", "single-pass")
    if name not in {"single-pass", "agent"}:
        raise ValueError("Unsupported evaluation workflow")
    return name


def _violations(check):
    return (check or {}).get("violated", [])


def _preflight_passed(status):
    return status in {"passed", "validated", "validated_with_warnings"}


def _case_metrics(attempt, score, case, cap):
    report = attempt["report"] or {}
    has_report = attempt["report"] is not None
    history = report.get("attempts", [])
    initial = history[0]["structural_validation"] if history else "not_run"
    final = report.get("structural_validation", "not_run")
    verification = report.get("verification")
    released = report.get("command") is not None if has_report else None
    reserved, calls, repairs = (
        report.get(key) for key in ("reserved_calls", "model_calls", "repair_count")
    )
    early = verification == "abstained" and reserved == 0
    allows_abstain = any(gold["verification"] == "abstained" for gold in case["expected"])
    reason = report.get("reason", "")
    wrong_attempts = sum(
        _preflight_passed(item["preflight_status"]) and bool(_violations(item.get("intent_check")))
        for item in history
    )
    final_violations = _violations(report.get("intent_check"))
    budget_exhaustion = (
        reason.endswith("Generation-call budget exhausted.")
        or reason == "Generation-call limit reached."
    )
    violation_counts = [len(_violations(item.get("intent_check"))) for item in history]
    over_cap = any(
        value is not None and value > limit
        for value, limit in (
            (reserved, cap),
            (calls, cap),
            (repairs, cap - 1),
            (len(history), cap),
        )
    )
    recovered = (
        bool(repairs)
        and score["outcome"] == "pass"
        and not final_violations
        and not over_cap
        and not budget_exhaustion
    )
    return {
        "verification": verification,
        "command_released": released,
        "validated_recipe": released is True
        and verification in {"validated", "validated_with_warnings"},
        "correct_abstention_pending_review": score["abstention"] == "correct",
        "abstention_without_gold_alternative": verification == "abstained" and not allows_abstain,
        "early_abstention": early,
        "early_abstention_review_candidate": (
            early
            and allows_abstain
            and report.get("intent_coverage") in {"unresolved", "not_covered"}
            and released is False
            and bool(reason)
            and final == "not_run"
            and report.get("preflight_validation") == "not_run"
            and report.get("preflight") is None
            and not report.get("argv")
            and not report.get("env")
        ),
        "correct_authoritative_rejection": (
            verification == "rejected" and score["outcome"] == "pass" and not final_violations
        ),
        "rejection_with_intent_violation": verification == "rejected" and bool(final_violations),
        "preflight_passed_with_explicit_violations_attempts": wrong_attempts,
        "final_preflight_passed_with_explicit_violations": (
            _preflight_passed(report.get("preflight_validation")) and bool(final_violations)
        ),
        "intent_coverage": report.get("intent_coverage") or "not_evaluated",
        "intent_status": report.get("intent_status") or "unverified",
        "constraint_violations": final_violations,
        "released_with_explicit_violations": released is True and bool(final_violations),
        "attempt_constraint_violation_counts": violation_counts,
        "reserved_calls": reserved,
        "model_calls": calls,
        "repair_count": repairs,
        "call_cap_violation": over_cap,
        "initial_structure": initial,
        "final_structure": final,
        "invalid_to_valid_structure": initial == "failed" and final == "passed",
        "recovered_to_pass": recovered,
        "initial_recipe_pass": not repairs
        and reserved == 1
        and score["outcome"] == "pass"
        and released is True,
        "repeated_candidate_stop": reason.endswith("Repeated failed candidate."),
        "budget_exhaustion": budget_exhaustion,
        "repair_terminal": ("error" if score["outcome"] == "error" else verification)
        if repairs
        else None,
        "wall_seconds": attempt["wall_seconds"],
        "generation_seconds_by_attempt": [item.get("generation_seconds") for item in history],
        "timed_out": score["error_category"] == "timeout",
        "response_missing": not has_report,
    }


def summarize(run, dataset, dataset_hash):
    result = historical_summary(run, dataset, dataset_hash)
    if workflow(run["manifest"]) != "agent":
        return result
    cases = {case["id"]: case for case in dataset["cases"]}
    cap = run["manifest"]["agent"]["max_reserved_calls"]
    metrics = {
        key: _case_metrics(run["attempts"][key], score, cases[key], cap)
        for key, score in result["cases"].items()
    }
    rows = list(metrics.values())
    counts = {
        key: sum(row[key] is True for row in rows)
        for key in (
            "validated_recipe",
            "correct_abstention_pending_review",
            "abstention_without_gold_alternative",
            "early_abstention",
            "early_abstention_review_candidate",
            "correct_authoritative_rejection",
            "rejection_with_intent_violation",
            "final_preflight_passed_with_explicit_violations",
            "call_cap_violation",
            "released_with_explicit_violations",
            "invalid_to_valid_structure",
            "recovered_to_pass",
            "initial_recipe_pass",
            "repeated_candidate_stop",
            "budget_exhaustion",
            "timed_out",
            "response_missing",
        )
    }
    counts.update(
        {
            "commands_released": sum(row["command_released"] is True for row in rows),
            "attempts_with_explicit_constraint_violations": sum(
                sum(count > 0 for count in row["attempt_constraint_violation_counts"])
                for row in rows
            ),
            "commands_withheld": sum(row["command_released"] is False for row in rows),
            "commands_unknown": sum(row["command_released"] is None for row in rows),
            "explicit_constraint_violation_cases": sum(
                bool(row["constraint_violations"]) for row in rows
            ),
            "final_intent_unverified": sum(row["intent_status"] == "unverified" for row in rows),
            "preflight_passed_with_explicit_violations_attempts": sum(
                row["preflight_passed_with_explicit_violations_attempts"] for row in rows
            ),
        }
    )
    result["agent"] = {
        "counts": counts,
        "intent_coverage": dict(Counter(row["intent_coverage"] for row in rows)),
        "initial_structure": dict(Counter(row["initial_structure"] for row in rows)),
        "final_structure": dict(Counter(row["final_structure"] for row in rows)),
        "repair_terminals": dict(
            Counter(row["repair_terminal"] for row in rows if row["repair_terminal"])
        ),
        "model_call_distribution": dict(
            Counter(
                str(row["model_calls"]) if row["model_calls"] is not None else "unknown"
                for row in rows
            )
        ),
        "generation_attempt_seconds": latency_summary(
            [elapsed for row in rows for elapsed in row["generation_seconds_by_attempt"]]
        ),
        **{
            key: sum(row[key] or 0 for row in rows)
            for key in (
                "reserved_calls",
                "model_calls",
                "repair_count",
            )
        },
        "cases": metrics,
    }
    return result


def _observation(attempt, score, *, agent):
    report = attempt["report"]
    if report is None:
        return {
            "outcome": score["outcome"],
            "released": None,
            "abstained": None,
            "wrong_intent_preflight_passed": None,
            "model_calls": None,
            "wall_seconds": attempt["wall_seconds"],
        }
    # Historical timing wraps exactly one single-pass generation invocation.
    calls = report.get("model_calls") if agent else int(attempt["generation_seconds"] is not None)
    return {
        "outcome": score["outcome"],
        "released": report["command"] is not None,
        "abstained": report["verification"] == "abstained",
        "wrong_intent_preflight_passed": (
            report["preflight_validation"] == "passed" and score["intent_match"] == "mismatch"
        ),
        "model_calls": calls,
        "wall_seconds": attempt["wall_seconds"],
    }


def compare(single, agent, dataset, dataset_hash, *, allow_provenance_mismatch=False):
    before, after = single["manifest"], agent["manifest"]
    if (workflow(before), workflow(after)) != ("single-pass", "agent"):
        raise ValueError("Compare a single-pass run followed by an agent run")
    left = summarize(single, dataset, dataset_hash)
    right = summarize(agent, dataset, dataset_hash)
    if "partial" in (left["status"], right["status"]):
        raise ValueError("Paired comparison requires completed runs")
    if set(before["selected"]) != set(after["selected"]):
        raise ValueError("Paired comparison requires identical selected case IDs")

    required = {
        "source": tuple(
            {key: manifest["source"][key] for key in ("git_sha", "dirty", "spec_sha256")}
            for manifest in (before, after)
        ),
        "index_sha256": (before["index_sha256"], after["index_sha256"]),
        "retrieval": (before["retrieval"], after["retrieval"]),
    }
    mismatches = {key: {"single_pass": a, "agent": b} for key, (a, b) in required.items() if a != b}
    if mismatches and not allow_provenance_mismatch:
        raise ValueError("Incompatible comparison provenance: " + ", ".join(mismatches))
    optional = (
        "model",
        "settings",
        "ollama_version",
        "python",
        "dependencies",
        "environment_sha256",
        "machine",
        "argus",
        "wall_timeout_seconds",
    )
    differences = {
        key: {"single_pass": before.get(key), "agent": after.get(key)}
        for key in optional
        if before.get(key) is None or after.get(key) is None or before[key] != after[key]
    }

    pairs = {}
    for case_id in before["selected"]:
        a = _observation(single["attempts"][case_id], left["cases"][case_id], agent=False)
        b = _observation(agent["attempts"][case_id], right["cases"][case_id], agent=True)
        pairs[case_id] = {
            "single_pass": a,
            "agent": b,
            "transition": f"{a['outcome']} → {b['outcome']}",
            "wall_seconds_delta": round(b["wall_seconds"] - a["wall_seconds"], 4),
            "model_calls_delta": b["model_calls"] - a["model_calls"]
            if a["model_calls"] is not None and b["model_calls"] is not None
            else None,
        }

    def arm(name, summary):
        rows = [pair[name] for pair in pairs.values()]
        return {
            "outcomes": summary["outcomes"],
            "abstentions": sum(row["abstained"] is True for row in rows),
            "recipes_released": sum(row["released"] is True for row in rows),
            "missing_responses": sum(row["released"] is None for row in rows),
            "preflight_passed_with_wrong_gold_intent": summary[
                "preflight_passed_with_wrong_intent"
            ],
            "model_calls": sum(row["model_calls"] or 0 for row in rows),
            "model_call_samples": sum(row["model_calls"] is not None for row in rows),
            "wall_seconds": summary["wall_seconds"],
        }

    return {
        "scope": left["scope"],
        "paired_cases": len(pairs),
        "dataset_total": left["dataset_total"],
        "dataset_sha256": dataset_hash,
        "agent_workflow": after["agent"],
        "provenance_mismatches": mismatches,
        "configuration_differences_or_unknowns": differences,
        "single_pass": arm("single_pass", left),
        "agent": {
            **arm("agent", right),
            "call_cap_violations": right["agent"]["counts"]["call_cap_violation"],
            "released_with_explicit_violations": right["agent"]["counts"][
                "released_with_explicit_violations"
            ],
            "preflight_passed_with_explicit_violations_attempts": right["agent"]["counts"][
                "preflight_passed_with_explicit_violations_attempts"
            ],
        },
        "transitions": dict(Counter(pair["transition"] for pair in pairs.values())),
        "new_passes": [
            key
            for key, pair in pairs.items()
            if pair["single_pass"]["outcome"] != "pass" and pair["agent"]["outcome"] == "pass"
        ],
        "regressions": [
            key
            for key, pair in pairs.items()
            if pair["single_pass"]["outcome"] == "pass" and pair["agent"]["outcome"] != "pass"
        ],
        "wrong_recipe_withheld_without_new_pass": [
            key
            for key, pair in pairs.items()
            if pair["single_pass"]["released"] is True
            and pair["single_pass"]["wrong_intent_preflight_passed"]
            and pair["agent"]["released"] is False
            and pair["agent"]["outcome"] != "pass"
        ],
        "cases": pairs,
    }
