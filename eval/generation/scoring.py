"""Deterministic scoring of captured M3 JSON against the frozen gold cases."""

import math
from collections import Counter


def option_tokens(argv):
    """Group flag/value tokens for comparison without interpreting MPML option values."""
    options = []
    for token in argv:
        if token.startswith("--"):
            key, equals, value = token.partition("=")
            options.append((key, value) if equals else (key,))
        elif options and len(options[-1]) == 1 and options[-1][0].startswith("--"):
            options[-1] += (token,)
        else:
            options.append((token,))
    return options


def differences(expected, argv, env):
    want = option_tokens(expected["argv"])
    got = option_tokens(argv)
    missing = Counter(want) - Counter(got)
    unexpected = Counter(got) - Counter(want)
    return {
        "missing_options": [list(tokens) for tokens in missing.elements()],
        "unexpected_options": [list(tokens) for tokens in unexpected.elements()],
        "missing_env": {key: val for key, val in expected["env"].items() if env.get(key) != val},
        "unexpected_env": {key: val for key, val in env.items() if expected["env"].get(key) != val},
        "argv_order_mismatch": not missing and not unexpected and want != got,
    }


def failure_category(report):
    error = report.get("error", "").lower()
    if not error:
        return None
    if "timed out" in error:
        return "timeout"
    if "ollama" in error and "unavailable" in error:
        return "model_unavailable"
    if "did not return structured" in error or any(
        term in error for term in ("invalid json", "schema", "output limit")
    ):
        return "invalid_output"
    if any(text in error for text in ("citation", "cited", "must cite")):
        return "citation_rejection"
    if report["structural_validation"] == "failed":
        return "candidate_rejection"
    if report["preflight_validation"] == "unverified":
        return "preflight_error"
    if "ollama" in error:
        return "ollama_error"
    return "argus_error"


def citation_status(report, indexed_citations):
    citations = report["citations"]
    if any(indexed_citations.get(item["id"]) != item for item in citations):
        return "invalid"
    if failure_category(report) == "citation_rejection":
        return "invalid"
    if report["structural_validation"] != "passed":
        return "not_evaluated"
    if citations:
        # A passing production validator also checks that citations came from the retrieved subset.
        return "valid"
    return "not_required" if report["verification"] == "abstained" else "invalid"


def score_case(case, attempt, indexed_citations):
    report = attempt["report"]
    if report is None:
        return {
            "outcome": "error",
            "intent_match": "not_scored",
            "abstention": "not_scored",
            "citations": "not_evaluated",
            "diagnostic_match": None,
            "differences": None,
            "diagnostic_codes": [],
            "error_category": attempt["error_category"],
        }

    verification = report["verification"]
    command = report["command"] is not None
    issues = [] if report["preflight"] is None else report["preflight"].get("issues")
    diagnostics_readable = isinstance(issues, list) and all(
        isinstance(issue, dict) and isinstance(issue.get("code"), str) for issue in issues
    )
    codes = sorted(issue["code"] for issue in issues) if diagnostics_readable else []
    citations = citation_status(report, indexed_citations)
    gold = case["expected"]
    permits_abstain = any(expect["verification"] == "abstained" for expect in gold)
    abstention = "not_applicable"
    if verification == "abstained":
        abstention = "correct" if permits_abstain and not command else "incorrect"
    elif permits_abstain and verification != "unverified":
        abstention = "alternative" if verification == "rejected" else "missed"

    argv, env = report["argv"], report["env"]
    comparisons = []
    for expect in gold:
        target = expect["verification"]
        diagnostic_match = (
            codes == sorted(expect["diagnostic_codes"]) if diagnostics_readable else None
        )
        expected_preflight = (
            "not_run" if "argv" not in expect else "failed" if target == "rejected" else "passed"
        )
        disposition_match = (
            target == verification
            and command == target.startswith("validated")
            and report["preflight_validation"] == expected_preflight
        )
        if "argv" in expect and argv is not None and env is not None:
            diff = differences(expect, argv, env)
            settings_match = not any(diff.values())
        elif "argv" not in expect:
            # Bare abstention requires no candidate settings or attempted preflight.
            diff = (
                differences({"argv": [], "env": {}}, argv, env)
                if argv is not None and env is not None and (argv or env)
                else None
            )
            settings_match = not argv and not env and report["preflight"] is None
        else:
            diff = None
            settings_match = False
        comparisons.append((disposition_match, diagnostic_match, settings_match, diff))

    # Prefer a matching disposition and the closest allowed settings for diagnostics.
    disposition, diagnostics, settings, diff = max(
        comparisons,
        key=lambda item: (
            all(item[:3]),
            item[0],
            item[2],
            item[1] is True,
            -sum(
                len(value) if isinstance(value, (list, dict)) else int(value)
                for value in item[3].values()
            )
            if item[3] is not None
            else -math.inf,
        ),
    )
    error = failure_category(report)
    human_review = verification == "abstained" and disposition and settings and diagnostics
    if human_review:
        intent = "review"
    elif diff is not None:
        intent = "match" if settings else "mismatch"
    elif verification == "abstained" or argv is not None:
        intent = "mismatch"
    else:
        intent = "not_scored"

    passed = (
        disposition
        and diagnostics
        and settings
        and error is None
        and report["structural_validation"] == "passed"
        and citations in {"valid", "not_required"}
    )
    if abstention == "alternative" and not passed:
        abstention = "missed"
    if abstention == "correct" and (not passed or not any(report.get("uncertainty", []))):
        abstention = "incorrect"
    return {
        "outcome": (
            "review"
            if passed and human_review and abstention == "correct"
            else "pass"
            if passed and not human_review
            else "error"
            if verification == "unverified"
            else "fail"
        ),
        "intent_match": intent,
        "abstention": abstention,
        "citations": citations,
        "diagnostic_match": diagnostics,
        "differences": diff,
        "diagnostic_codes": codes,
        "error_category": error,
    }


def latency_summary(values):
    ordered = sorted(value for value in values if value is not None)
    return {
        "samples": len(ordered),
        **{
            f"p{p}": ordered[math.ceil(len(ordered) * p / 100) - 1] if ordered else None
            for p in (50, 95)
        },
    }


def summarize(run, dataset, dataset_hash):
    manifest = run["manifest"]
    if manifest["dataset_sha256"] != dataset_hash:
        raise ValueError("The recorded dataset hash does not match the frozen fixture")
    cases = {case["id"]: case for case in dataset["cases"]}
    selected = manifest["selected"]
    attempts = run["attempts"]
    if (
        not selected
        or len(set(selected)) != len(selected)
        or not set(selected) <= cases.keys()
        or not attempts.keys() <= set(selected)
    ):
        raise ValueError("Recorded case IDs do not match the selected fixture cases")
    results = {
        key: score_case(cases[key], attempts[key], manifest["indexed_citations"])
        for key in selected
        if key in attempts
    }
    full = set(selected) == cases.keys()
    complete = len(attempts) == len(selected)
    return {
        "status": ("complete_full" if full else "complete_subset") if complete else "partial",
        "scope": "full" if full else "subset",
        "attempted": len(attempts),
        "selected": len(selected),
        "dataset_total": len(cases),
        "remaining": [key for key in selected if key not in attempts],
        "outcomes": dict(Counter(row["outcome"] for row in results.values())),
        "intent": dict(Counter(row["intent_match"] for row in results.values())),
        "abstentions": dict(Counter(row["abstention"] for row in results.values())),
        "citations": dict(Counter(row["citations"] for row in results.values())),
        "errors": dict(
            Counter(row["error_category"] for row in results.values() if row["error_category"])
        ),
        "diagnostics_matched": sum(row["diagnostic_match"] is True for row in results.values()),
        "structural_validation": dict(
            Counter(
                (attempt["report"] or {}).get("structural_validation", "not_run")
                for attempt in attempts.values()
            )
        ),
        "preflight_validation": dict(
            Counter(
                (attempt["report"] or {}).get("preflight_validation", "not_run")
                for attempt in attempts.values()
            )
        ),
        "preflight_passed_with_wrong_intent": sum(
            (attempts[key]["report"] or {}).get("preflight_validation") == "passed"
            and row["intent_match"] == "mismatch"
            for key, row in results.items()
        ),
        "generation_seconds": latency_summary(
            [row["generation_seconds"] for row in attempts.values()]
        ),
        "wall_seconds": latency_summary([row["wall_seconds"] for row in attempts.values()]),
        "cases": results,
    }
