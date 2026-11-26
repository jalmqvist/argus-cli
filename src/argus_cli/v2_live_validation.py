"""Bind fixed MPML settings to trusted live observations without releasing a command."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import ValidationError

from argus_cli.adapters.mpml import BridgeError, preflight, preflight_verification
from argus_cli.ask import CandidateError, _validate_options
from argus_cli.config import Source
from argus_cli.retrieval import RetrievalError, index_sha256, rank_verified_index, verified_index
from argus_cli.v2_answer import _cite
from argus_cli.v2_authorization import (
    CandidateEvaluation,
    FinalProvenance,
    PreflightObservation,
    SnapshotIdentity,
    ValidationObservation,
    VerifiedSnapshot,
    bind,
    evaluate,
)
from argus_cli.v2_contract import Diagnostic, IntentCoverage, Preflight, Provenance, Settings
from argus_cli.v2_intent import Vocabulary, _candidate_values, check_candidate, extract

_SOURCE_ERRORS = (
    BridgeError,
    RetrievalError,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    subprocess.SubprocessError,
)
_OUTCOMES = {
    "validated": "accepted",
    "validated_with_warnings": "accepted_with_warnings",
    "rejected": "rejected",
}


@dataclass(frozen=True)
class CapturedIssue:
    code: str
    severity: str
    source: str
    message: str


@dataclass(frozen=True)
class LiveEvaluation:
    candidate_sha256: str
    coverage: IntentCoverage | None
    evidence_ids: tuple[str, ...]
    evaluation: CandidateEvaluation | None
    preflight_exit_code: int | None
    preflight_issues: tuple[CapturedIssue, ...]
    diagnostics_redacted: bool
    final_provenance: Literal["verified", "stale", "unavailable", "unchecked"]
    environment: Literal["unchanged", "changed", "unavailable", "unchecked"]
    blockers: tuple[str, ...]


def _snapshot(source):
    index, metadata, spec, index_digest = verified_index(source)
    identity = SnapshotIdentity.from_provenance(
        Provenance(
            source_revision=metadata["git_sha"],
            source_dirty=metadata["dirty"],
            spec_sha256=metadata["spec_sha256"],
            index_sha256=index_digest,
        )
    )
    snapshot = VerifiedSnapshot(
        identity,
        (json.dumps(spec, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        frozenset(chunk["id"] for chunk in index["chunks"]),
        "trusted_adapter",
    )
    if len(snapshot.evidence_ids) != len(index["chunks"]):
        raise RetrievalError("Duplicate evidence identifiers")
    return snapshot, index, metadata


def _setting_support(index, metadata, spec, question, values):
    # Lexical retrieval is local. Only matching structured spec records may attest.
    query = " ".join((question, *values))
    chunks = rank_verified_index(index, query, "lexical", 20)["results"]["lexical"]
    cited_ids = tuple(chunk["id"] for chunk in chunks)
    by_id = {chunk["id"]: chunk for chunk in index["chunks"]}
    pinned_chunks = [chunk for chunk in chunks if by_id.get(chunk["id"]) == chunk]
    vocab = Vocabulary.from_spec(spec)
    support = []
    for target, proposed in values.items():
        if target in vocab.flags:
            row = vocab.flags[target]
            label = ", ".join(row["flags"])
            section = "arguments"
            choices = row.get("post_parse_choices") or row.get("choices")
            if choices is not None:
                supported = all(value in {str(choice) for choice in choices} for value in proposed)
            else:
                default = row.get("default")
                supported = (
                    row.get("nargs") == 0
                    and row["action"] in {"store_true", "store_false"}
                    and proposed == [""]
                ) or (type(default) in {int, bool} and proposed == [str(default).lower()])
        else:
            row = vocab.env[target]
            label = target
            section = "env"
            default = row.get("default")
            supported = (
                row.get("parser") == "int" and type(default) is int and proposed == [str(default)]
            ) or (
                row.get("parser") in {"bool_strict", "bool_loose"}
                and type(default) is bool
                and proposed == [str(default).lower()]
            )
        if not supported:
            continue
        try:
            citation = _cite(pinned_chunks, metadata, section, label, row)
        except RetrievalError:
            continue
        support.append((target, citation.evidence_id))
    # No current structured record attests defaults-only behavior globally.
    return cited_ids, tuple(support)


def _scrubber(inherited, candidate: Settings):
    # MPML may echo environment values or paths supplied as split or equals-form argv.
    argv_values = [
        token.partition("=")[2] if re.match(r"--|-[A-Za-z][^=]*=", token) else token
        for token in candidate.argv
    ]
    values = {
        value.strip()
        for value in (*inherited.values(), *candidate.env.values(), *argv_values)
        if value.strip()
    }
    variants = (
        values | {repr(value)[1:-1] for value in values} | {ascii(value)[1:-1] for value in values}
    )
    pattern = (
        re.compile(
            "|".join(
                re.escape(value) if len(value) >= 4 else rf"(?<!\w){re.escape(value)}(?!\w)"
                for value in sorted(variants, key=lambda item: (-len(item), item))
            )
        )
        if variants
        else None
    )
    return lambda text: pattern.sub("[redacted]", text) if pattern else text


def _probe(source, candidate, inherited):
    try:
        result = preflight(
            source, list(candidate.argv), overrides=dict(candidate.env), inherited_env=inherited
        )
    except BridgeError:
        return Preflight(outcome="unavailable", diagnostics=[]), None, (), False

    try:
        verification = preflight_verification(result)
    except BridgeError:
        return Preflight(outcome="unavailable", diagnostics=[]), result.exit_code, (), False

    original = tuple(
        CapturedIssue(**{key: row[key] for key in CapturedIssue.__annotations__})
        for row in result.document["issues"]
    )
    scrub = _scrubber(inherited, candidate)
    issues = tuple(
        CapturedIssue(scrub(issue.code), issue.severity, scrub(issue.source), scrub(issue.message))
        for issue in original
    )
    outcome = _OUTCOMES.get(verification, "warnings_only" if issues else "unavailable")
    try:
        diagnostics = [
            Diagnostic(code=issue.code, severity=issue.severity, message=issue.message)
            for issue in issues
        ]
        observed = Preflight(outcome=outcome, diagnostics=diagnostics)
    except ValidationError:
        return Preflight(outcome="unavailable", diagnostics=[]), result.exit_code, (), False
    return (
        observed,
        result.exit_code,
        issues,
        issues != original,
    )


def _environment_status(inherited):
    try:
        return "unchanged" if os.environ.copy() == inherited else "changed"
    except (OSError, RuntimeError):
        return "unavailable"


def assess_fixed_candidate(question: str, settings: Settings, source: Source) -> LiveEvaluation:
    """Use only configured read-only MPML interfaces. Missing completeness always withholds."""
    candidate = Settings.model_validate(settings.model_dump())
    candidate_hash = candidate.fingerprint()
    try:
        inherited = MappingProxyType(os.environ.copy())
    except (OSError, RuntimeError):
        return LiveEvaluation(
            candidate_hash,
            None,
            (),
            None,
            None,
            (),
            False,
            "unchecked",
            "unavailable",
            ("environment",),
        )
    try:
        snapshot, index, metadata = _snapshot(source)
        if snapshot.identity.source_dirty:
            return LiveEvaluation(
                candidate_hash,
                None,
                (),
                None,
                None,
                (),
                False,
                "stale",
                "unchecked",
                ("provenance",),
            )
        spec = snapshot.read_spec()
        request = extract(question, spec)
        binding = bind(snapshot, request, candidate, dict(inherited))
        consistency = check_candidate(request, candidate.argv, candidate.env, spec)
        try:
            _validate_options(candidate, spec)
        except CandidateError:
            structure_passed = False
        else:
            structure_passed = not consistency.candidate_issues
        scope = request.analysis.route in {"launch", "mixed"}
        cited_ids, support = (), ()
        if structure_passed and scope:
            values, _ = _candidate_values(candidate.argv, candidate.env, Vocabulary.from_spec(spec))
            cited_ids, support = _setting_support(index, metadata, spec, question, values)
    except _SOURCE_ERRORS:
        return LiveEvaluation(
            candidate_hash,
            None,
            (),
            None,
            None,
            (),
            False,
            "unavailable",
            "unchecked",
            ("provenance",),
        )

    validation = ValidationObservation(
        binding,
        "trusted_adapter",
        "passed" if structure_passed else "failed",
        "manual_mpml_launch" if scope else "unsupported",
        cited_ids,
        support,
    )
    environment_status = _environment_status(inherited)
    probe = Preflight(outcome="not_run", diagnostics=[]), None, (), False
    if structure_passed and scope and environment_status == "unchanged":
        probe = _probe(source, candidate, inherited)

    outcome, exit_code, issues, redacted = probe
    preflight_observation = PreflightObservation.capture(binding, "trusted_adapter", outcome)
    try:
        final, _, _ = _snapshot(source)
        matches = (
            final.identity == snapshot.identity
            and final.evidence_ids == snapshot.evidence_ids
            and index_sha256() == snapshot.identity.index_sha256
        )
        provenance_status = "verified" if matches else "stale"
        final_identity = final.identity
    except _SOURCE_ERRORS:
        provenance_status = "unavailable"
        final_identity = snapshot.identity
    final_environment_status = _environment_status(inherited)
    if environment_status == "unchanged":
        environment_status = final_environment_status
    evaluation = evaluate(
        request,
        candidate,
        snapshot=snapshot,
        inherited_env=dict(inherited),
        cited_ids=cited_ids,
        validation=validation,
        preflight=preflight_observation,
        final_provenance=FinalProvenance(final_identity, "trusted_adapter", provenance_status),
    )
    blockers = list(evaluation.blockers)
    if environment_status != "unchanged":
        blockers.append("environment")
    if settings.fingerprint() != candidate_hash:
        blockers.append("candidate_changed")
    return LiveEvaluation(
        candidate_hash,
        request.coverage,
        cited_ids,
        evaluation,
        exit_code,
        issues,
        redacted,
        provenance_status,
        environment_status,
        tuple(blockers),
    )
