"""Proposed M4 v2 contracts. Imported by offline tests, with no CLI integration."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Digest = Annotated[str, StringConstraints(pattern="^[0-9a-f]{64}$")]
Route = Literal["informational", "launch", "mixed", "unsupported", "ambiguous"]
AnswerStatus = Literal["grounded", "limited", "withheld", "unverified"]
RecipeStatus = Literal[
    "not_requested", "withheld", "rejected", "validated", "validated_with_warnings", "unverified"
]
IntentCoverage = Literal["enforced", "partial", "unresolved", "not_covered"]
ConstraintsStatus = Literal["verified", "unresolved", "contradicted"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Span(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: Text


class Requirement(Contract):
    target: Text
    operator: Literal["require", "forbid", "ordered", "defaults_only", "no_substitution"]
    channel: Literal["cli", "env", "either"]
    values: list[Text]
    span: Span


class UnresolvedRequirement(Contract):
    reason: Text
    span: Span


class RequestAnalysis(Contract):
    question: Text
    route: Route
    requirements: list[Requirement]
    unresolved_material: list[UnresolvedRequirement]

    @model_validator(mode="after")
    def check_spans(self):
        for requirement in (*self.requirements, *self.unresolved_material):
            span = requirement.span
            if (
                not span.start < span.end <= len(self.question)
                or self.question[span.start : span.end] != span.text
            ):
                raise ValueError("requirement span must match the original question")
        if self.route == "ambiguous" and not self.unresolved_material:
            raise ValueError("ambiguous routing requires a recorded material gap")
        return self


class Citation(Contract):
    evidence_id: Text
    path: Text
    heading: str | None


class Provenance(Contract):
    source_revision: Text
    source_dirty: bool
    spec_sha256: Digest
    index_sha256: Digest


class Diagnostic(Contract):
    code: Text
    severity: Literal["error", "warning", "info"]
    message: Text


class Preflight(Contract):
    outcome: Literal[
        "not_run", "unavailable", "rejected", "warnings_only", "accepted", "accepted_with_warnings"
    ]
    diagnostics: list[Diagnostic]

    @model_validator(mode="after")
    def check_diagnostics(self):
        severities = {item.severity for item in self.diagnostics}
        if self.outcome in {"not_run", "unavailable"} and severities:
            raise ValueError("unobserved preflight cannot have authoritative diagnostics")
        if self.outcome in {"accepted", "accepted_with_warnings", "warnings_only"}:
            requires_warnings = self.outcome != "accepted"
            if "error" in severities or ("warning" in severities) != requires_warnings:
                raise ValueError("preflight outcome contradicts authoritative diagnostics")
        return self


class Settings(Contract):
    argv: list[str]
    env: dict[str, str]

    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PrivateCandidateTrace(Contract):
    """Local-only trace. Persist only resolved evidence IDs and allowlisted settings."""

    candidate_sha256: Digest
    settings: Settings | None
    evidence_ids: list[Text]


class ReleaseAudit(Contract):
    """Gate observations recorded by trusted adapters for one exact candidate."""

    candidate_sha256: Digest | None
    provenance: Literal["verified", "stale", "unavailable", "unchecked"]
    structure: Literal["passed", "failed", "unchecked"]
    evidence: Literal["passed", "failed", "unchecked"]
    release_scope: Literal["manual_mpml_launch", "unsupported", "unchecked"]
    evidence_ids: list[Text]


class ResponseV2(Contract):
    schema_version: Literal["argus-response-v2.0"]
    request: RequestAnalysis
    response_kind: Literal["answer", "recipe", "rejection_explanation", "abstention", "unverified"]
    answer_status: AnswerStatus
    recipe_status: RecipeStatus
    intent_coverage: IntentCoverage
    material_constraints_status: ConstraintsStatus
    explanation: Text | None
    citations: list[Citation]
    provenance: Provenance | None
    preflight: Preflight
    audit: ReleaseAudit
    settings: Settings | None
    command: Text | None

    def release_blockers(self) -> tuple[str, ...]:
        """Inspect trusted facts. Routing and outcome labels remain separate."""
        gates = {
            "recipe_requested": self.request.route in {"launch", "mixed"},
            "manual_launch_scope": self.audit.release_scope == "manual_mpml_launch",
            "provenance": (
                self.audit.provenance == "verified"
                and self.provenance is not None
                and not self.provenance.source_dirty
            ),
            "structure": self.audit.structure == "passed"
            and self.audit.candidate_sha256 is not None,
            "evidence": (
                self.audit.evidence == "passed"
                and bool(self.audit.evidence_ids)
                and set(self.audit.evidence_ids) <= {item.evidence_id for item in self.citations}
            ),
            "material_constraints": (
                self.material_constraints_status == "verified"
                and not self.request.unresolved_material
            ),
            "preflight": self.preflight.outcome in {"accepted", "accepted_with_warnings"},
        }
        return tuple(gate for gate, passed in gates.items() if not passed)

    @model_validator(mode="after")
    def check_response(self):
        if self.answer_status == "grounded" and (
            not self.explanation
            or not self.citations
            or not self.provenance
            or self.provenance.source_dirty
            or self.audit.provenance != "verified"
        ):
            raise ValueError(
                "grounded answers require explanation, citations and verified provenance"
            )
        if self.answer_status == "withheld" and self.explanation is not None:
            raise ValueError("withheld answers cannot have an explanation")
        if self.recipe_status == "not_requested" and self.request.route in {"launch", "mixed"}:
            raise ValueError("request explicitly includes a recipe")
        accepted = {"validated": "accepted", "validated_with_warnings": "accepted_with_warnings"}
        if self.recipe_status in accepted:
            if blockers := self.release_blockers():
                raise ValueError("command release blocked: " + ", ".join(blockers))
            if (
                self.response_kind != "recipe"
                or self.preflight.outcome != accepted[self.recipe_status]
                or self.command is None
                or self.settings is None
                or self.settings.fingerprint() != self.audit.candidate_sha256
            ):
                raise ValueError(
                    "validated recipe requires matching preflight and released settings"
                )
        elif (
            self.command is not None or self.settings is not None or self.response_kind == "recipe"
        ):
            raise ValueError("only a validated recipe may expose a command or candidate settings")
        return self
