"""Offline assessment of trusted observations. No rendering or live adapters."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from argus_cli.provenance import spec_sha256
from argus_cli.v2_contract import ConstraintsStatus, Preflight, Provenance, Settings
from argus_cli.v2_intent import Consistency, Interpretation, Vocabulary, check_candidate

Authority = Literal["trusted_adapter", "model", "unverified"]
GateStatus = Literal["passed", "failed", "unchecked"]


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnapshotIdentity:
    source_revision: str
    source_dirty: bool
    spec_sha256: str
    index_sha256: str

    @classmethod
    def from_provenance(cls, provenance: Provenance):
        return cls(**provenance.model_dump())


@dataclass(frozen=True)
class VerifiedSnapshot:
    """Captured by a trusted caller after verifying the repository and index."""

    identity: SnapshotIdentity
    spec_json: bytes
    evidence_ids: frozenset[str]
    authority: Authority

    def __post_init__(self):
        if not isinstance(self.spec_json, bytes) or not isinstance(self.evidence_ids, frozenset):
            raise TypeError("Use immutable spec bytes and a frozen set of evidence IDs")
        if spec_sha256(self.read_spec()) != self.identity.spec_sha256:
            raise ValueError("Specification does not match the snapshot hash")

    def read_spec(self) -> dict:
        return json.loads(self.spec_json)


@dataclass(frozen=True)
class Binding:
    snapshot: SnapshotIdentity
    candidate_sha256: str
    request_sha256: str
    inherited_env_sha256: str
    evidence_ids_sha256: str


def bind(
    snapshot: VerifiedSnapshot,
    request: Interpretation,
    settings: Settings,
    inherited_env: dict[str, str],
) -> Binding:
    """Fingerprint exact inputs. A matching fingerprint alone establishes no authority."""
    return Binding(
        snapshot.identity,
        settings.fingerprint(),
        _digest({"analysis": request.analysis.model_dump(), "coverage": request.coverage}),
        _digest(inherited_env),
        _digest(sorted(snapshot.evidence_ids)),
    )


@dataclass(frozen=True)
class ValidationObservation:
    binding: Binding
    authority: Authority
    structure: GateStatus
    release_scope: Literal["manual_mpml_launch", "unsupported", "unchecked"]
    cited_ids: tuple[str, ...]
    # Each pair attests that a cited chunk supports the exact candidate setting
    # identified by its canonical flag or environment key.
    setting_support: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PreflightObservation:
    binding: Binding
    authority: Authority
    # Serialize at capture so the observation cannot be mutated after binding.
    result_json: bytes

    @classmethod
    def capture(cls, binding: Binding, authority: Authority, result: Preflight):
        return cls(binding, authority, result.model_dump_json().encode("utf-8"))

    def result(self) -> Preflight:
        return Preflight.model_validate_json(self.result_json)


@dataclass(frozen=True)
class MaterialIntentAssessment:
    binding: Binding
    authority: Authority
    status: ConstraintsStatus
    # Includes effective CLI/env precedence and inherited settings where material.
    effective_configuration: ConstraintsStatus = "unresolved"


@dataclass(frozen=True)
class FinalProvenance:
    identity: SnapshotIdentity
    authority: Authority
    status: Literal["verified", "stale", "unavailable", "unchecked"]


@dataclass(frozen=True)
class CandidateEvaluation:
    binding: Binding
    consistency: Consistency
    material_intent: ConstraintsStatus
    effective_configuration: ConstraintsStatus
    structure_valid: bool
    citations_resolved: bool
    setting_evidence_valid: bool
    preflight: Preflight
    blockers: tuple[str, ...]

    @property
    def eligible_from_trusted_offline_observations(self) -> bool:
        return not self.blockers


def _bound(observation, binding: Binding) -> bool:
    return observation.authority == "trusted_adapter" and observation.binding == binding


def evaluate(
    request: Interpretation,
    settings: Settings,
    *,
    snapshot: VerifiedSnapshot,
    inherited_env: dict[str, str],
    cited_ids: tuple[str, ...],
    validation: ValidationObservation,
    preflight: PreflightObservation,
    final_provenance: FinalProvenance,
    material: MaterialIntentAssessment | None = None,
) -> CandidateEvaluation:
    """Assess observations supplied by trusted Python adapters, never by model payloads."""
    request = Interpretation(request.analysis.model_copy(deep=True), request.coverage)
    settings = settings.model_copy(deep=True)
    binding = bind(snapshot, request, settings, inherited_env)
    spec = snapshot.read_spec()
    consistency = check_candidate(request, settings.argv, settings.env, spec)
    vocab = Vocabulary.from_spec(spec)
    # check_candidate guards option shapes. Walk the same single-value forms
    # here using its parser so values cannot masquerade as cited options.
    targets = set(consistency.candidate_targets) or {"*"}
    validation_bound = _bound(validation, binding)
    structure_valid = (
        validation_bound and validation.structure == "passed" and not consistency.candidate_issues
    )
    citations_resolved = bool(cited_ids) and set(cited_ids) <= snapshot.evidence_ids
    support = {
        vocab.canonical(target)
        for target, citation in validation.setting_support
        if citation in cited_ids and citation in snapshot.evidence_ids
    }
    evidence_valid = (
        validation_bound
        and citations_resolved
        and validation.cited_ids == cited_ids
        and targets <= support
    )

    try:
        preflight_result = preflight.result()
    except ValidationError:
        preflight_result = Preflight(outcome="unavailable", diagnostics=[])
    material_bound = material is not None and _bound(material, binding)
    material_status = material.status if material_bound else "unresolved"
    effective_status = material.effective_configuration if material_bound else "unresolved"
    final_verified = (
        snapshot.authority == final_provenance.authority == "trusted_adapter"
        and final_provenance.status == "verified"
        and snapshot.identity == final_provenance.identity
        and not snapshot.identity.source_dirty
    )
    gates = {
        "request_scope": (
            request.analysis.route in {"launch", "mixed"}
            and validation_bound
            and validation.release_scope == "manual_mpml_launch"
        ),
        "provenance": final_verified,
        "structure": structure_valid,
        "citation_resolution": citations_resolved,
        "setting_support": evidence_valid,
        "recognized_constraints": not consistency.violated,
        "unresolved_requirements": not consistency.unresolved,
        "material_intent": material_status == "verified",
        "effective_configuration": effective_status == "verified",
        "preflight_binding": _bound(preflight, binding),
        "preflight_acceptance": preflight_result.outcome in {"accepted", "accepted_with_warnings"},
    }
    return CandidateEvaluation(
        binding=binding,
        consistency=consistency,
        material_intent=material_status,
        effective_configuration=effective_status,
        structure_valid=structure_valid,
        citations_resolved=citations_resolved,
        setting_evidence_valid=evidence_valid,
        preflight=preflight_result,
        blockers=tuple(name for name, passed in gates.items() if not passed),
    )
