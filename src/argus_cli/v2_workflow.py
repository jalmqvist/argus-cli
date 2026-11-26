"""Opt-in v2 explanation and one-shot proposal workflow."""

import os
import re
import time
from types import MappingProxyType

from pydantic import JsonValue, ValidationError

from argus_cli.ask import _lookup_query
from argus_cli.config import Source
from argus_cli.generation import (
    Candidate,
    GenerationError,
    GenerationSettings,
    InvalidCandidateError,
    evidence_by_prompt_id,
    generate,
)
from argus_cli.retrieval import rank_verified_index
from argus_cli.v2_answer import _REFERENCE, _report, _route, answer, unavailable
from argus_cli.v2_contract import Citation, Preflight, Provenance, ResponseV2, Settings
from argus_cli.v2_intent import _UNSAFE_CONTEXT
from argus_cli.v2_live_validation import (
    _SOURCE_ERRORS,
    ProposalContext,
    _snapshot,
    assess_fixed_candidate,
)

_TOPIC = re.compile(
    r"\b(?:mpml|strateg(?:y|ies)|phaseaware|seed|variant|pairs?|"
    r"output (?:dir(?:ectory)?|path)|behavioral surface|(?:mr|tf)\d+|"
    r"experiment_(?:seed|variant)|active_pairs|mpml_output_dir)\b|--[a-z]",
    re.IGNORECASE,
)
_PROPOSE = re.compile(
    r"^\s*(?:please\s+)?(?:use|choose|select|pin)\b"
    r"|^\s*(?:i['’]d like|i would like|i want)\s+"
    r"(?:to (?:use|choose|select|pin|configure)\b|(?:an? |the )?(?:mpml )?configuration\b)"
    r"|^\s*(?:(?:can|could|would) you )?help me configure\b",
    re.IGNORECASE,
)
_UNRESOLVED_REFERENCE = re.compile(
    r"\b(?:that|this|same|previous|other) (?:strategy|variant|seed|configuration)\b", re.IGNORECASE
)
_SETTING_LABELS = {
    "--strategy": "strategy selection",
    "--phaseaware-tf": "PhaseAware trend representative",
    "--phaseaware-mr": "PhaseAware mean-reversion representative",
    "--experiment-seed": "experiment seed",
    "EXPERIMENT_SEED": "experiment seed",
    "--experiment-variant": "experiment variant",
    "EXPERIMENT_VARIANT": "experiment variant",
    "ACTIVE_PAIRS": "active pair filter",
    "--output-dir": "output directory",
    "MPML_OUTPUT_DIR": "output directory",
}
_PRECEDENCE_LABELS = {
    "experiment_seed": "experiment seed",
    "experiment_variant": "experiment variant",
}
_WINNER_LABELS = {
    "cli": "the command line",
    "explicit_env": "an explicit environment override",
    "inherited_env": "the inherited environment",
    "published_fallback": "the published fallback",
}
_EXECUTE = re.compile(
    r"(?:^|[;.!?]\s*|\b(?:please|can you|could you|and then|i want you to|i['’]d like you to)\s+)"
    r"(?:run|execute|start|launch|backtest|evaluate|place|trade|buy|sell)\b"
    r"|\b(?:execute|run|launch)\b[^.!?;]*\b(?:for me|right now)\b",
    re.IGNORECASE,
)
_EVIDENCE_LIMIT = 8


class WorkflowResponse(ResponseV2):
    """Additive telemetry for the opt-in CLI workflow."""

    workflow: dict[str, JsonValue]


def _proposal_route(question, route):
    if route == "unsupported" or _UNSAFE_CONTEXT.search(question) or _EXECUTE.search(question):
        return "unsupported"
    if _REFERENCE.search(question.casefold()) or _UNRESOLVED_REFERENCE.search(question):
        return None
    if _TOPIC.search(question):
        if route in {"launch", "mixed"}:
            return route
        if _PROPOSE.search(question):
            return "launch"
    return None


def run(
    source: Source, question: str, *, model: str, settings: GenerationSettings
) -> tuple[dict, int]:
    start = time.monotonic()
    route = _route(question)
    proposed_route = _proposal_route(question, route)
    trace = {
        "request_route": proposed_route or route,
        "deterministic_answer": False,
        "generation_attempted": False,
        "model_calls": 0,
        "candidate_outcome": "not_attempted",
        "structure_valid": None,
        "citations_resolved": None,
        "setting_evidence_valid": None,
        "preflight_attempted": False,
        "preflight_outcome": "not_run",
        "material_intent": "unresolved",
        "effective_configuration": "unresolved",
        "effective_observations": [],
        "blockers": [],
        "model": model,
        "model_digest": None,
        "generation_seconds": None,
        "error": None,
    }

    def finish(response: ResponseV2, code: int):
        trace.update(
            answer_delivered=response.response_kind == "answer"
            and response.explanation is not None,
            recipe_released=False,
            recipe_withheld=response.recipe_status == "withheld",
            elapsed_seconds=round(time.monotonic() - start, 6),
        )
        report = WorkflowResponse.model_validate({**response.model_dump(), "workflow": trace})
        return report.model_dump(mode="json"), code

    def fail(reason, explanation, code=1):
        trace["error"] = reason
        response = _report(
            question,
            proposed_route or route,
            "unverified" if code == 2 else "abstention",
            "unverified" if code == 2 else "limited",
            explanation,
        )
        return finish(response, code)

    if proposed_route == "unsupported":
        return finish(
            _report(
                question,
                "unsupported",
                "rejection_explanation",
                "limited",
                "Argus can explain launch settings or check a proposal. Execution and external actions are outside its scope.",
            ),
            1,
        )

    if route == "informational" or proposed_route is None:
        response, code = answer(source, question)
        trace["deterministic_answer"] = code == 0
        if code != 1 or proposed_route is None:
            return finish(response, code)

    try:
        inherited = MappingProxyType(os.environ.copy())
        snapshot, index, _ = _snapshot(source)
        if snapshot.identity.source_dirty:
            raise ValueError("Dirty source")
        evidence = rank_verified_index(index, _lookup_query(question), "lexical", _EVIDENCE_LIMIT)[
            "results"
        ]["lexical"]
        pinned = {chunk["id"]: chunk for chunk in index["chunks"]}
        if any(pinned.get(chunk["id"]) != chunk for chunk in evidence):
            raise ValueError("Unpinned retrieval result")
    except (*_SOURCE_ERRORS, RuntimeError):
        trace["error"] = "provenance"
        return finish(unavailable(question), 2)
    if not evidence:
        return fail("no_evidence", "No matching indexed evidence supports a proposal.")

    def count_call():
        trace["model_calls"] += 1

    generation_start = time.monotonic()
    trace["generation_attempted"] = True
    try:
        proposal, digest = generate(question, evidence, model, settings, on_model_call=count_call)
        proposal = Candidate.model_validate(proposal.model_dump())
    except (InvalidCandidateError, ValidationError, AttributeError):
        trace["generation_seconds"] = round(time.monotonic() - generation_start, 6)
        trace["candidate_outcome"] = "invalid"
        return fail(
            "invalid_proposal", "The local model did not produce a usable structured proposal."
        )
    except (GenerationError, TimeoutError) as exc:
        trace["generation_seconds"] = round(time.monotonic() - generation_start, 6)
        timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).casefold()
        return fail(
            "ollama_timeout" if timeout else "ollama_unavailable",
            "Local model generation timed out."
            if timeout
            else "Local model generation could not be verified.",
            2,
        )
    trace["generation_seconds"] = round(time.monotonic() - generation_start, 6)
    trace["model_digest"] = digest

    if proposal.outcome == "abstain":
        if proposal.argv or proposal.env or not proposal.uncertainty:
            trace["candidate_outcome"] = "invalid"
            return fail("invalid_abstention", "The model returned an inconsistent abstention.")
        trace["candidate_outcome"] = "abstained"
        return fail(
            "model_abstained",
            "The model withheld a proposal. Try naming the exact MPML settings and values.",
        )

    trace["candidate_outcome"] = "produced"
    prompt_ids = evidence_by_prompt_id(evidence)
    if not proposal.evidence_ids or any(key not in prompt_ids for key in proposal.evidence_ids):
        trace["citations_resolved"] = False
        return fail(
            "invalid_citations",
            "The proposal did not cite evidence from the verified retrieval results.",
        )

    cited_ids = tuple(dict.fromkeys(prompt_ids[key]["id"] for key in proposal.evidence_ids))
    report = assess_fixed_candidate(
        question,
        Settings(argv=proposal.argv, env=proposal.env),
        source,
        proposal=ProposalContext(snapshot.identity, inherited, cited_ids),
    )
    result = report.evaluation
    trace["blockers"] = list(report.blockers)
    trace["preflight_attempted"] = report.preflight_attempted
    if result is not None:
        trace["preflight_outcome"] = result.preflight.outcome
    if result is None or report.final_provenance != "verified" or report.environment != "unchanged":
        return fail(
            "validation_drift",
            "Source, index or process environment could not be verified across proposal validation.",
            2,
        )

    spec = snapshot.read_spec()
    trace.update(
        structure_valid=result.structure_valid,
        citations_resolved=result.citations_resolved,
        setting_evidence_valid=result.setting_evidence_valid,
        material_intent=result.material_intent,
        effective_configuration=result.effective_configuration,
        effective_observations=[
            {"setting": item.setting, "winner": item.winner}
            for item in report.effective_observations
            if item.independently_verified
        ],
        recognized_violations=len(result.consistency.violated),
        unresolved_requirements=len(result.consistency.unresolved),
    )
    details = [
        "The proposal uses supported argument shapes."
        if result.structure_valid
        else "The proposal contains unsupported arguments, values or environment overrides."
    ]
    supported = set()
    for key in report.supported_evidence_ids:
        heading = pinned[key]["citation"]["heading"]
        for target in heading.partition(" / ")[2].split(", "):
            if target in _SETTING_LABELS:
                supported.add(_SETTING_LABELS[target])
    if supported:
        details.append(
            f"Published MPML records support the proposed {', '.join(sorted(supported))}."
        )
    if result.structure_valid and not result.setting_evidence_valid:
        details.append(
            "The cited specification does not directly establish every proposed setting."
        )
    for constraints, outcome in (
        (result.consistency.satisfied, "matches"),
        (result.consistency.violated, "conflicts with"),
    ):
        labels = sorted(
            {_SETTING_LABELS[item.target] for item in constraints if item.target in _SETTING_LABELS}
        )
        if constraints:
            scope = f" for {', '.join(labels)}" if labels else ""
            details.append(f"The proposal {outcome} the recognized request constraints{scope}.")
    details.append(
        {
            "not_run": "MPML preflight was not run.",
            "unavailable": "MPML preflight was unavailable or returned an unverifiable result.",
            "rejected": "MPML preflight rejected the proposal.",
            "warnings_only": "MPML returned warnings without verified preflight acceptance.",
            "accepted": "MPML preflight accepted the proposal.",
            "accepted_with_warnings": "MPML preflight accepted the proposal with warnings.",
        }[result.preflight.outcome]
    )
    for item in trace["effective_observations"]:
        label = _PRECEDENCE_LABELS[item["setting"]]
        winner = _WINNER_LABELS[item["winner"]]
        details.append(
            f"For {label}, MPML uses the command line first, then the environment, "
            f"then the published fallback. The winning source here was {winner}."
        )
    if result.consistency.unresolved:
        details.append("Some parts of the request could not be interpreted independently.")
    if proposal.uncertainty:
        details.append("The model flagged uncertainty about the proposal.")
    details.append(
        "Complete intent and effective configuration remain unverified. The recipe is withheld."
    )
    issues = {rule["code"] for rule in spec["rules"]}
    diagnostics = [
        {
            "code": issue.code if issue.code in issues else "UNPUBLISHED_DIAGNOSTIC",
            "severity": issue.severity,
            "message": "MPML reported a launch diagnostic; private diagnostic text was withheld.",
        }
        for issue in result.preflight.diagnostics
    ]
    citations = [
        Citation(
            evidence_id=key,
            path=pinned[key]["citation"]["path"],
            heading=pinned[key]["citation"]["heading"],
        )
        for key in report.supported_evidence_ids
    ]
    response = _report(
        question,
        proposed_route,
        "answer",
        "limited",
        " ".join(details),
        provenance=Provenance(
            source_revision=snapshot.identity.source_revision,
            source_dirty=False,
            spec_sha256=snapshot.identity.spec_sha256,
            index_sha256=snapshot.identity.index_sha256,
        ),
        citations=citations,
    )
    return finish(
        ResponseV2.model_validate(
            {
                **response.model_dump(),
                "intent_coverage": report.coverage,
                "preflight": Preflight(
                    outcome=result.preflight.outcome, diagnostics=diagnostics
                ).model_dump(),
            }
        ),
        2 if result.preflight.outcome == "unavailable" else 1,
    )
