"""Ground one MPML candidate in live evidence and preflight it for manual use."""

import os
import re
import shlex
import subprocess
from dataclasses import asdict

from argus_cli.adapters.mpml import BridgeError, preflight, preflight_verification
from argus_cli.config import Source
from argus_cli.generation import (
    MAX_EXCERPT_CHARS,
    Candidate,
    GenerationError,
    GenerationSettings,
    InvalidCandidateError,
    evidence_by_prompt_id,
    generate,
)
from argus_cli.ollama import EmbeddingError
from argus_cli.retrieval import RetrievalError, retrieve_context, source_matches

_RETRIEVAL_LIMIT = 5
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
_NEGATIVE_NUMBER = re.compile(r"-[0-9]+(?:\.[0-9]+)?")
_SOURCE_ERRORS = (
    BridgeError,
    RetrievalError,
    EmbeddingError,
    OSError,
    UnicodeError,
    subprocess.SubprocessError,
)


class CandidateError(ValueError):
    pass


def _lookup_query(question: str) -> str:
    # Exact identifiers help retrieve spec entries for natural-language pair/strategy requests.
    hints = []
    if re.search(r"\b[A-Z]{6}\b", question):
        hints.append("ACTIVE_PAIRS")
    if re.search(r"\b(?:MR|TF)[0-9]+\b", question, re.IGNORECASE):
        hints.append("--strategy")
    return " ".join([question, *hints])


def _validate_options(candidate: Candidate, document: dict) -> set[str]:
    if any(_CONTROL.search(value) for value in [*candidate.argv, *candidate.env.values()]):
        raise CandidateError("Arguments and override values must be single-line text")

    allowed_env = {
        entry["name"] for entry in document["env"] if entry.get("scope") == "launch_selector"
    }
    for key in candidate.env:
        if not _ENV_NAME.fullmatch(key) or key not in allowed_env:
            raise CandidateError(f"Unsupported environment override {key!r}")

    options = {flag: entry for entry in document["arguments"] for flag in entry["flags"]}
    used = set(candidate.env)
    tokens = iter(candidate.argv)
    for token in tokens:
        flag, equals, value = token.partition("=")
        entry = options.get(flag)
        if entry is None:
            raise CandidateError(f"Unknown flag or unexpected argument {token!r}")
        used.add(flag)

        action = entry["action"]
        nargs = entry["nargs"]
        if action in {"store_true", "store_false"} and nargs == 0 and not equals:
            continue
        if action not in {"store", "append"} or nargs not in (None, 1):
            raise CandidateError(f"Unsupported argument shape for {flag!r}")
        if not equals:
            value = next(tokens, None)
            if value is None or (value.startswith("-") and not _NEGATIVE_NUMBER.fullmatch(value)):
                raise CandidateError(f"Expected a single value for {flag!r}")
    return used


def _validate_citations(candidate: Candidate, evidence: list[dict], used: set[str]) -> list[dict]:
    by_id = evidence_by_prompt_id(evidence)
    if set(candidate.evidence_ids) - by_id.keys():
        raise CandidateError("Model cited evidence that was not retrieved")
    cited = [by_id[key] for key in dict.fromkeys(candidate.evidence_ids)]
    if candidate.outcome == "recipe" and not cited:
        raise CandidateError("A recipe must cite retrieved evidence")
    for name in sorted(used):
        mention = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        if not any(
            mention.search(item["citation"]["heading"] + "\n" + item["text"][:MAX_EXCERPT_CHARS])
            for item in cited
        ):
            raise CandidateError(f"No cited evidence mentions {name!r}")
    return [{"id": item["id"], **item["citation"]} for item in cited]


def _render(source: Source, entrypoint: str, candidate: Candidate) -> str:
    overrides = [f"{key}={value}" for key, value in sorted(candidate.env.items())]
    command = [str(source.python), entrypoint, *candidate.argv]
    if overrides:
        command = ["env", *overrides, *command]
    return f"cd {shlex.quote(str(source.root))} && {shlex.join(command)}"


def ask(
    source: Source,
    question: str,
    *,
    model: str,
    settings: GenerationSettings,
    retrieval_mode: str,
) -> dict:
    entrypoint = str(source.root / source.entrypoint)
    report = {
        "question": question,
        "model": {"name": model, "digest": None, "settings": asdict(settings)},
        "repository": source.name,
        "retrieval": {"mode": retrieval_mode, "limit": _RETRIEVAL_LIMIT},
        "cwd": str(source.root),
        "interpreter": str(source.python),
        "entrypoint": source.entrypoint,
        "argv": None,
        "env": None,
        "explanation": None,
        "citations": [],
        "uncertainty": [],
        "provenance": None,
        "preflight": None,
        "preflight_exit_code": None,
        "structural_validation": "not_run",
        "preflight_validation": "not_run",
        "intent_status": "unverified",
        "intent_note": "Preflight checks the launch surface only. Execution and DL activation are unverified.",
        "verification": "unverified",
        "command": None,
        "command_purpose": "manual_execution_only",
    }

    try:
        report_from_index, metadata, document = retrieve_context(
            source, _lookup_query(question), retrieval_mode, _RETRIEVAL_LIMIT
        )
    except _SOURCE_ERRORS as exc:
        return {**report, "error": str(exc)}
    report["provenance"] = {key: metadata[key] for key in ("git_sha", "dirty", "spec_sha256")}
    evidence = report_from_index["results"][retrieval_mode]
    if not evidence:
        return {**report, "verification": "abstained", "error": "No relevant indexed evidence"}

    try:
        candidate, digest = generate(question, evidence, model, settings)
    except InvalidCandidateError as exc:
        return {
            **report,
            "structural_validation": "failed",
            "verification": "rejected",
            "error": str(exc),
        }
    except GenerationError as exc:
        return {**report, "error": str(exc)}
    report["model"]["digest"] = digest
    report.update(candidate.model_dump(exclude={"outcome", "evidence_ids"}))
    try:
        if candidate.outcome == "abstain" and (
            candidate.argv or candidate.env or not candidate.uncertainty
        ):
            raise CandidateError("An abstention requires empty argv/env and a reason")
        used = _validate_options(candidate, document)
        report["citations"] = _validate_citations(candidate, evidence, used)
    except CandidateError as exc:
        return {
            **report,
            "structural_validation": "failed",
            "verification": "rejected",
            "error": str(exc),
        }
    report["structural_validation"] = "passed"
    if candidate.outcome == "abstain" or candidate.uncertainty:
        return {**report, "verification": "abstained"}

    # Record whether DL activation would remain unverified even with a clean preflight.
    dl_request = candidate.env.get("DL_SIGNALS_ENABLED", os.environ.get("DL_SIGNALS_ENABLED", ""))
    try:
        if not source_matches(source, metadata):
            return {**report, "error": "MPML evidence changed during generation; rebuild the index"}
        result = preflight(source, candidate.argv, overrides=candidate.env)
        report["preflight"] = result.document
        report["preflight_exit_code"] = result.exit_code
        verification = preflight_verification(result)
        if not source_matches(source, metadata):
            raise RetrievalError("MPML evidence changed during preflight; rebuild the index")
    except _SOURCE_ERRORS as exc:
        return {**report, "preflight_validation": "unverified", "error": str(exc)}
    report["preflight_validation"] = {
        "rejected": "failed",
        "unverified": "unverified",
        "validated": "passed",
        "validated_with_warnings": "passed",
    }[verification]
    report["verification"] = verification
    if report["preflight_validation"] != "passed":
        return report

    if dl_request.casefold() not in {"", "false"}:
        return {
            **report,
            "verification": "abstained",
            "uncertainty": ["MPML preflight cannot verify DL activation or artifact loading."],
        }
    report["command"] = _render(source, entrypoint, candidate)
    return report
