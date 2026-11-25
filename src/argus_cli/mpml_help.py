"""Deterministic lookup and candidate reporting for MPML's published schema."""

from argus_cli.adapters.mpml import BridgeError, preflight, spec
from argus_cli.config import Source
from argus_cli.provenance import revision, spec_sha256


def _parameter(document: dict, name: str) -> dict | None:
    for argument in document["arguments"]:
        if name in argument["flags"]:
            aliases = set(argument["flags"])
            return {
                "source": "command line",
                "argument": argument,
                "precedence": [
                    rule for rule in document["precedence"] if aliases.intersection(rule["order"])
                ],
            }

    for entry in document["env"]:
        if name == entry["name"]:
            return {
                "source": "environment",
                "environment": entry,
                "precedence": [rule for rule in document["precedence"] if name in rule["order"]],
            }
    return None


def describe(source: Source, command: str, query: str) -> tuple[dict, int]:
    document = spec(source).document
    try:
        report = _recipe(source) if command == "recipe" else _lookup(document, command, query)
    except (KeyError, TypeError) as exc:
        raise BridgeError("MPML returned an incomplete schema v1 document") from exc
    info = revision(source.root)
    report["provenance"] = {
        "source": "python -m mpml.spec",
        "repository": str(source.root),
        "interpreter": str(source.python),
        "git_sha": info.sha,
        "dirty": info.dirty,
        "schema_version": document["schema_version"],
        "spec_sha256": spec_sha256(document),
    }
    rejected = report.get("verification") in {"rejected", "unverified"}
    return report, int(rejected)


def _lookup(document: dict, command: str, query: str) -> dict:
    if command == "explain":
        sections = {
            "precedence": "precedence",
            "warnings": "rules",
            "source-edit-only": "source_edit_only",
        }
        if query in {"strategies", "behavioral-surfaces"}:
            return {"topic": query, "registry": document["registries"][query.replace("-", "_")]}
        if query in sections:
            return {"topic": query, "details": document[sections[query]]}
        for section, key in (("rules", "code"), ("precedence", "setting")):
            for entry in document[section]:
                if query == entry[key]:
                    return {"topic": query, "details": entry}

    parameter = _parameter(document, query)
    if parameter is not None:
        return parameter
    raise BridgeError(f"Unknown MPML {command} query {query!r}; see 'argus {command} --help'")


def _recipe(source: Source) -> dict:
    # The defaults pattern supplies no MPML arguments or environment overrides.
    argv: list[str] = []
    overrides: dict[str, str] = {}
    report = {
        "pattern": "defaults",
        "cwd": str(source.root),
        "interpreter": str(source.python),
        "entrypoint": source.entrypoint,
        "argv": argv,
        "env": overrides,
        "explanation": "Use MPML defaults and the inherited process environment.",
        "verification": "unverified",
    }
    try:
        result = preflight(source, argv, overrides=overrides)
    except BridgeError as exc:
        report["preflight_error"] = str(exc)
        return report

    issues = result.document.get("issues")
    report["preflight"] = result.document
    report["preflight_exit_code"] = result.exit_code
    if not isinstance(issues, list) or not all(
        isinstance(issue, dict)
        and issue.get("severity") in ("error", "warning")
        and all(isinstance(issue.get(key), str) for key in ("code", "source", "message"))
        for issue in issues
    ):
        report["preflight_error"] = "MPML returned malformed preflight diagnostics"
    elif any(issue["severity"] == "error" for issue in issues):
        report["verification"] = "rejected"
    elif result.exit_code == 0:
        report["verification"] = "validated_with_warnings" if issues else "validated"
    return report
