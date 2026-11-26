"""Bind the opt-in graph to Argus's existing read-only MPML and Ollama interfaces."""

import subprocess
import time
from dataclasses import asdict

from argus_cli.adapters.mpml import BridgeError, preflight
from argus_cli.agent import (
    MAX_CALLS,
    AgentUnavailable,
    Attempt,
    Evidence,
    RecoverableOutput,
    Snapshot,
    Stages,
    Validation,
    build_graph,
)
from argus_cli.ask import (
    _RETRIEVAL_LIMIT,
    CandidateError,
    _lookup_query,
    _render,
    _validate_citations,
    _validate_options,
)
from argus_cli.config import ConfigError, Source
from argus_cli.generation import (
    GenerationError,
    GenerationSettings,
    InvalidCandidateError,
    generate,
)
from argus_cli.intent import Intent
from argus_cli.ollama import model_digest
from argus_cli.retrieval import index_sha256, rank_verified_index, source_matches, verified_index

_SOURCE_ERRORS = (RuntimeError, OSError, ValueError, subprocess.SubprocessError)
_DIAGNOSTICS = {
    "invalid_flag": "The candidate used an unknown flag or a stray argv token. Use exact MPML flags.",
    "argv_shape": "The candidate used an unsupported argument shape. Supply each required value as a single token.",
    "env_in_argv": "Place the indicated environment keys in env, preserving requested values.",
    "env": "Use only launch-selector environment keys published by MPML.",
    "citation": "Cite retrieved evidence IDs and support every proposed setting.",
    "abstention": "For abstention, return empty argv and env and a nonempty uncertainty reason.",
    "invalid_candidate": "Return one JSON object matching the candidate schema.",
    "intent": "Correct the missing, additional, misplaced or out-of-order settings.",
}


def _validation(candidate, evidence, chunks) -> Validation:
    if candidate.outcome == "abstain" and (
        candidate.argv
        or candidate.env
        or not any(reason.strip() for reason in candidate.uncertainty)
    ):
        return Validation(False, _DIAGNOSTICS["abstention"], True, code="abstention")
    try:
        options = _validate_options(candidate, evidence.snapshot.spec)
    except CandidateError as exc:
        key_names = {item["name"] for item in evidence.snapshot.spec["env"]}
        misplaced = sorted(
            {token.partition("=")[0].removeprefix("--") for token in candidate.argv} & key_names
        )
        code = "argv_shape"
        if misplaced:
            code = "env_in_argv"
        elif str(exc).startswith("Unsupported environment override"):
            code = "env"
        elif str(exc).startswith("Unknown flag"):
            code = "invalid_flag"
        reason = _DIAGNOSTICS[code]
        if misplaced:
            reason += " " + ", ".join(misplaced[:8])
        return Validation(False, reason, True, code=code)
    try:
        citations = _validate_citations(candidate, chunks, options)
    except CandidateError:
        return Validation(False, _DIAGNOSTICS["citation"], True, code="citation")
    return Validation(True, citations=tuple(item["id"] for item in citations))


def _repair_context(intent: Intent, attempt: Attempt) -> dict:
    validation = attempt.validation
    code = validation.code if validation and not validation.accepted else "intent"
    violations = attempt.intent.violated if attempt.intent else ()
    return {
        "code": code,
        "diagnostic": validation.reason
        if validation and not validation.accepted
        else _DIAGNOSTICS["intent"],
        "constraints": [asdict(item) for item in intent.constraints],
        "violated_targets": [item.target for item in violations],
    }


def _generation_failure(exc: Exception) -> GenerationError:
    message = str(exc).lower()
    if "changed" in message:
        reason = "Ollama model identity changed."
    elif "timed out" in message or "timeout" in message:
        reason = "Local Ollama generation timed out."
    elif "unavailable" in message:
        reason = "Local Ollama model is unavailable."
    else:
        reason = "Local Ollama generation failed."
    return GenerationError(reason)


def ask_agent(
    source: Source, question: str, *, model: str, settings: GenerationSettings, retrieval_mode: str
) -> dict:
    started = time.monotonic()
    pinned: Snapshot | None = None
    document, metadata = {}, {}
    chunks: list[dict] = []
    digest: str | None = None

    def verify(config):
        nonlocal pinned, document, metadata
        try:
            if pinned is None:
                document, metadata, spec, index_hash = verified_index(config)
                pinned = Snapshot(
                    metadata["git_sha"],
                    metadata["dirty"],
                    metadata["spec_sha256"],
                    index_hash,
                    spec,
                )
            elif (
                index_sha256() != pinned.index_sha256
                or not source_matches(config, metadata)
                or index_sha256() != pinned.index_sha256
            ):
                raise BridgeError("Source or index changed.")
        except _SOURCE_ERRORS as exc:
            raise BridgeError(
                "Cannot verify current MPML source and index; check configuration or rebuild."
            ) from exc
        return pinned

    def retrieve(original, snapshot):
        nonlocal chunks
        try:
            result = rank_verified_index(
                document, _lookup_query(original), retrieval_mode, _RETRIEVAL_LIMIT
            )
            if index_sha256() != snapshot.index_sha256:
                raise BridgeError("Index changed during retrieval.")
        except _SOURCE_ERRORS as exc:
            raise BridgeError("Cannot retrieve evidence from the verified MPML index.") from exc
        chunks = sorted(
            result["results"][retrieval_mode],
            key=lambda item: item["citation"]["path"] != "mpml/spec.py",
        )
        return Evidence(snapshot, tuple(item["id"] for item in chunks))

    def propose(original, feedback=None):
        nonlocal digest
        try:
            if digest is None:
                digest = model_digest(model)
            try:
                candidate, actual_digest = generate(
                    original,
                    chunks,
                    model,
                    settings,
                    repair_context=feedback,
                    expected_digest=digest,
                )
            except InvalidCandidateError as exc:
                # A malformed reply is repairable only while the model tag still identifies
                # the pinned model. The successful generation path already checks this.
                if model_digest(model) != digest:
                    raise GenerationError("Ollama model changed during generation") from exc
                raise RecoverableOutput from exc
            if actual_digest != digest:
                raise GenerationError("Ollama model changed during generation")
        except RecoverableOutput:
            raise
        except (RuntimeError, OSError, ValueError) as exc:
            raise _generation_failure(exc) from exc
        return candidate

    def run_preflight(config, candidate):
        try:
            return preflight(config, candidate.argv, overrides=candidate.env)
        except _SOURCE_ERRORS as exc:
            raise BridgeError("MPML preflight interface is unavailable.") from exc

    try:
        graph = build_graph(
            Stages(
                verify=verify,
                retrieve=retrieve,
                generate=lambda original, _ids, _ordinal: propose(original),
                validate=lambda candidate, evidence: _validation(candidate, evidence, chunks),
                preflight=run_preflight,
                repair=lambda original, _ids, intent, attempt: propose(
                    original, _repair_context(intent, attempt)
                ),
            ),
            time_budget=MAX_CALLS * settings.timeout_seconds + 600,
        )
    except AgentUnavailable as exc:
        raise ConfigError("Install agent support: pip install 'argus-cli[llm,agent]'") from exc
    state = graph.invoke({"question": question, "source": source})
    report = _report(state, chunks, model, digest, settings, retrieval_mode)
    report["wall_seconds"] = time.monotonic() - started
    return report


def _report(state, chunks, model, digest, settings, retrieval_mode):
    snapshot = state.get("snapshot")
    provenance = (
        {key: getattr(snapshot, key) for key in ("git_sha", "dirty", "spec_sha256", "index_sha256")}
        if snapshot
        else None
    )
    source = state["source"]
    validation = state.get("validation")
    candidate = state.get("candidate") if validation and validation.accepted else None
    preflight_result = state.get("preflight")
    status = state.get("preflight_status", "not_run")
    intent = state.get("intent")
    intent_check = state.get("intent_check")
    by_id = {item["id"]: item["citation"] for item in chunks}
    report = {
        "workflow": "m4-langgraph-v1",
        "question": state["question"],
        "model": {"name": model, "digest": digest, "settings": asdict(settings)},
        "retrieval": {"mode": retrieval_mode, "limit": _RETRIEVAL_LIMIT},
        "repository": source.name,
        "cwd": str(source.root),
        "interpreter": str(source.python),
        "entrypoint": source.entrypoint,
        "argv": candidate.argv if candidate else None,
        "env": candidate.env if candidate else None,
        "explanation": candidate.explanation if candidate else None,
        "uncertainty": [
            *(intent.uncertainty if intent else ()),
            *(candidate.uncertainty if candidate else ()),
        ],
        "citations": [{"id": key, **by_id[key]} for key in state["citations"]],
        "provenance": provenance,
        "preflight": preflight_result.document if preflight_result else None,
        "preflight_exit_code": preflight_result.exit_code if preflight_result else None,
        "warnings": state["warnings"],
        "structural_validation": _structure_status(validation),
        "preflight_validation": {
            "validated": "passed",
            "validated_with_warnings": "passed",
            "rejected": "failed",
        }.get(status, status),
        "intent_status": (
            "inconsistent"
            if intent_check and intent_check.violated
            else "consistent_with_explicit_constraints"
            if intent_check and not intent_check.unresolved
            else "unverified"
        ),
        "intent_note": "The checks cover extracted constraints. Full semantic intent, execution and DL activation remain unverified.",
        "intent_coverage": intent.coverage if intent else None,
        "constraints": [asdict(item) for item in intent.constraints] if intent else [],
        "intent_check": asdict(intent_check) if intent_check else None,
        "verification": state["disposition"],
        "reason": state["reason"],
        "reserved_calls": state["reserved_calls"],
        "model_calls": state["model_calls"],
        "repair_count": state["repair_count"],
        "attempts": [_attempt_report(item) for item in state["attempts"]],
        "command": (
            _render(source, str(source.root / source.entrypoint), candidate)
            if state["released"]
            else None
        ),
        "command_purpose": "manual_execution_only",
    }
    if state["disposition"] == "unverified":
        report["error"] = state["reason"]
    return report


def _structure_status(validation):
    if validation is None:
        return "not_run"
    return "passed" if validation.accepted else "failed"


def _attempt_report(attempt):
    preflight_result = attempt.preflight
    return {
        "ordinal": attempt.ordinal,
        "structural_validation": _structure_status(attempt.validation),
        "validation_code": attempt.validation.code if attempt.validation else None,
        "preflight_status": attempt.preflight_status,
        "preflight": preflight_result.document if preflight_result else None,
        "preflight_exit_code": preflight_result.exit_code if preflight_result else None,
        "intent_check": asdict(attempt.intent) if attempt.intent else None,
        "reason": attempt.reason,
        "generation_seconds": attempt.generation_seconds,
    }
