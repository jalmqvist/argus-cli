"""Offline graph foundation. All external stages are supplied by trusted callers."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict

from argus_cli.adapters.mpml import BridgeError, BridgeResult, preflight_verification
from argus_cli.config import Source
from argus_cli.intent import Intent, IntentCheck, check, extract


class Proposal(Protocol):
    outcome: Literal["recipe", "abstain"]
    argv: list[str]
    env: dict[str, str]
    evidence_ids: list[str]
    uncertainty: list[str]


MAX_CALLS = 3
Disposition = Literal["validated", "validated_with_warnings", "rejected", "abstained", "unverified"]


@dataclass(frozen=True)
class Snapshot:
    git_sha: str
    dirty: bool
    spec_sha256: str
    index_sha256: str
    spec: dict


@dataclass(frozen=True)
class Evidence:
    snapshot: Snapshot
    ids: tuple[str, ...]


@dataclass(frozen=True)
class Validation:
    accepted: bool
    reason: str = ""
    retryable: bool = False
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Attempt:
    ordinal: int
    candidate: Proposal | None
    validation: Validation | None
    preflight: BridgeResult | None
    preflight_status: str
    intent: IntentCheck | None
    reason: str
    generation_seconds: float


class State(TypedDict, total=False):
    question: str
    source: Source
    snapshot: Snapshot
    evidence_ids: tuple[str, ...]
    intent: Intent
    candidate: Proposal | None
    validation: Validation | None
    preflight: BridgeResult | None
    preflight_status: str
    intent_check: IntentCheck | None
    attempts: tuple[Attempt, ...]
    reserved_calls: int
    model_calls: int
    repair_count: int
    started: float
    wall_seconds: float
    generation_seconds: float
    disposition: Disposition
    reason: str
    retry: bool
    released: bool
    citations: tuple[str, ...]
    warnings: tuple[dict, ...]


@dataclass(frozen=True)
class Stages:
    verify: Callable[[Source], Snapshot]
    retrieve: Callable[[str, Snapshot], Evidence]
    generate: Callable[[str, tuple[str, ...], int], Proposal]
    validate: Callable[[Proposal, Evidence], Validation]
    preflight: Callable[[Source, Proposal], BridgeResult]


def _fingerprint(candidate: Proposal) -> tuple:
    return (
        candidate.outcome,
        tuple(candidate.argv),
        tuple(sorted(candidate.env.items())),
        tuple(sorted(candidate.evidence_ids)),
        tuple(candidate.uncertainty),
    )


def build_graph(stages: Stages):
    """Compile an in-memory graph. No CLI route or live stage factories are provided."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ModuleNotFoundError as exc:
        if exc.name not in {"langgraph", "langgraph.graph"}:
            raise
        raise RuntimeError("Graph support requires the optional agent extra.") from exc

    def stop(disposition, reason):
        return {"disposition": disposition, "reason": reason, "retry": False}

    def fresh(state):
        try:
            return stages.verify(state["source"]) == state["snapshot"]
        except (BridgeError, OSError, RuntimeError, ValueError):
            return False

    def verify(state):
        initial = {
            "started": time.monotonic(),
            "attempts": (),
            "reserved_calls": 0,
            "model_calls": 0,
            "repair_count": 0,
            "released": False,
            "citations": (),
            "warnings": (),
            "retry": False,
            "reason": "",
        }
        try:
            return {**initial, "snapshot": deepcopy(stages.verify(state["source"]))}
        except (BridgeError, OSError, RuntimeError, ValueError) as exc:
            return {**initial, **stop("unverified", str(exc))}

    def retrieve(state):
        try:
            result = stages.retrieve(state["question"], deepcopy(state["snapshot"]))
        except (BridgeError, OSError, RuntimeError, ValueError) as exc:
            return stop("unverified", str(exc))
        if result.snapshot != state["snapshot"]:
            return stop("unverified", "Source or index changed during retrieval.")
        if not result.ids:
            return stop("abstained", "No verified evidence was retrieved.")
        return {"evidence_ids": result.ids}

    def extract_intent(state):
        intent = extract(state["question"], state["snapshot"].spec)
        if intent.coverage != "enforced":
            return {"intent": intent, **stop("abstained", " ".join(intent.uncertainty))}
        return {"intent": intent}

    def reserve(state):
        if state["reserved_calls"] >= MAX_CALLS:
            return stop("unverified", "Generation-call limit reached.")
        if not fresh(state):
            return stop("unverified", "Source or index changed before generation.")
        return {
            "reserved_calls": state["reserved_calls"] + 1,
            "repair_count": state["reserved_calls"],
            "candidate": None,
            "validation": None,
            "preflight": None,
            "preflight_status": "not_run",
            "warnings": (),
            "intent_check": None,
            "retry": False,
            "reason": "",
        }

    def generate(state):
        calls = {"model_calls": state["model_calls"] + 1}
        started = time.monotonic()
        try:
            candidate = stages.generate(
                state["question"], state["evidence_ids"], state["reserved_calls"]
            )
        # Keep accounting even if a supplied generator fails after it starts.
        except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001
            reason = f"Generation failed: {str(exc) or type(exc).__name__}"
            return {
                **calls,
                "generation_seconds": time.monotonic() - started,
                **stop("unverified", reason),
            }
        return {
            **calls,
            "generation_seconds": time.monotonic() - started,
            "candidate": deepcopy(candidate),
        }

    def validate(state):
        evidence = Evidence(deepcopy(state["snapshot"]), state["evidence_ids"])
        result = stages.validate(deepcopy(state["candidate"]), evidence)
        return {"validation": result}

    def preflight(state):
        if not fresh(state):
            return stop("unverified", "Source or index changed before preflight.")
        result = None
        try:
            result = deepcopy(stages.preflight(state["source"], deepcopy(state["candidate"])))
            status = preflight_verification(result)
        except (BridgeError, OSError, RuntimeError, ValueError) as exc:
            return {
                "preflight": result,
                "preflight_status": "unverified",
                **stop("unverified", str(exc)),
            }
        observed = {
            "preflight": result,
            "preflight_status": status,
            "warnings": tuple(
                item for item in result.document["issues"] if item["severity"] == "warning"
            ),
        }
        if status == "unverified" or not fresh(state):
            return {
                **observed,
                **stop("unverified", "Preflight or source provenance is unverified."),
            }
        return observed

    def check_intent(state):
        candidate = state["candidate"]
        if candidate.outcome == "abstain":
            return stop("abstained", " ".join(candidate.uncertainty))
        result = check(state["intent"], candidate.argv, candidate.env)
        return {"intent_check": result}

    def decide(state):
        if state.get("disposition"):
            return {}
        validation = state["validation"]
        intent = state["intent_check"]
        status = state["preflight_status"]
        if not validation.accepted:
            return {"retry": validation.retryable, "reason": validation.reason}
        if status == "rejected":
            return stop("rejected", "MPML preflight rejected the candidate.")
        dl_value = state["candidate"].env.get(
            "DL_SIGNALS_ENABLED", os.environ.get("DL_SIGNALS_ENABLED", "")
        )
        if dl_value.casefold() not in {"", "false"}:
            return stop(
                "abstained", "MPML preflight cannot verify DL activation or artifact loading."
            )
        if intent.violated or intent.unresolved or state["candidate"].uncertainty:
            return {
                "retry": not intent.unresolved and not state["candidate"].uncertainty,
                "reason": "Proposal does not establish the explicit constraints.",
            }
        return stop(status, "All release gates passed.")

    def record(state):
        candidate = state["candidate"]
        attempts = state["attempts"]
        reason = state["reason"]
        retry = state["retry"]
        if retry:
            if state["reserved_calls"] >= MAX_CALLS:
                retry, reason = False, f"{reason} Generation-call budget exhausted."
            elif candidate is not None and any(
                prior.candidate is not None
                and _fingerprint(prior.candidate) == _fingerprint(candidate)
                for prior in attempts
            ):
                retry, reason = False, f"{reason} Repeated failed candidate."
        record = Attempt(
            state["reserved_calls"],
            candidate,
            state["validation"],
            state["preflight"],
            state["preflight_status"],
            state["intent_check"],
            reason,
            state["generation_seconds"],
        )
        updates = {"attempts": (*attempts, record), "retry": retry, "reason": reason}
        if not retry and not state.get("disposition"):
            updates["disposition"] = "rejected" if not state["validation"].accepted else "abstained"
        return updates

    def finish(state):
        result = {"wall_seconds": time.monotonic() - state["started"]}
        status = state["disposition"]
        if state.get("validation") and state["validation"].accepted:
            result["citations"] = state["validation"].citations
        if status in {"validated", "validated_with_warnings"}:
            if not fresh(state):
                return {**result, **stop("unverified", "Source or index changed before release.")}
            result["released"] = True
        return result

    # Only explicit request inputs cross the initial graph boundary.
    class Request(TypedDict):
        question: str
        source: Source

    graph = StateGraph(State, input_schema=Request)
    for name, node in (
        ("verify", verify),
        ("retrieve", retrieve),
        ("extract_intent", extract_intent),
        ("reserve", reserve),
        ("generate", generate),
        ("validate", validate),
        ("preflight", preflight),
        ("check_intent", check_intent),
        ("decide", decide),
        ("record", record),
        ("finish", finish),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "verify")
    for node, next_node in (
        ("verify", "retrieve"),
        ("retrieve", "extract_intent"),
        ("extract_intent", "reserve"),
        ("reserve", "generate"),
    ):
        graph.add_conditional_edges(
            node,
            lambda state, target=next_node: "finish" if state.get("disposition") else target,
            ["finish", next_node],
        )
    graph.add_conditional_edges(
        "generate",
        lambda state: "record" if state.get("disposition") else "validate",
        ["record", "validate"],
    )
    graph.add_conditional_edges(
        "validate",
        lambda state: (
            "decide"
            if not state["validation"].accepted
            else "check_intent"
            if state["candidate"].outcome == "abstain"
            else "preflight"
        ),
        ["decide", "check_intent", "preflight"],
    )
    graph.add_conditional_edges(
        "preflight",
        lambda state: "record" if state.get("disposition") else "check_intent",
        ["record", "check_intent"],
    )
    graph.add_edge("check_intent", "decide")
    graph.add_edge("decide", "record")
    graph.add_conditional_edges(
        "record", lambda state: "reserve" if state["retry"] else "finish", ["reserve", "finish"]
    )
    graph.add_edge("finish", END)
    return graph.compile().with_config({"recursion_limit": 32})
