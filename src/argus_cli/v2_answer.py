"""Deterministic, specification-backed answers for the opt-in v2 workflow."""

import json
import re
import subprocess

from argus_cli.adapters.mpml import BridgeError
from argus_cli.mpml_help import _parameter
from argus_cli.retrieval import RetrievalError, index_sha256, source_matches, verified_index
from argus_cli.v2_contract import Citation, Provenance, RequestAnalysis, ResponseV2, Route

_OPTIONS = re.compile(r"(?<![\w-])--[a-zA-Z][\w-]*|\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_INFO = re.compile(
    r"\b(?:which|what|when|why|explain|describe|documented|meaning|default|"
    r"precedence|override|wins|mean|recognized|supported|normal|affect|scope|"
    r"filter|count as|applies|import.time|ever|is there|could|would|does|how)\b"
)
_UNSUPPORTED = re.compile(
    r"\b(?:broker|place (?:an? |the )?(?:limit |market )?order|"
    r"(?:execute|start|run|launch) (?:an? |the )?(?:mpml )?experiment now|"
    r"(?:^|please |can you |could you )(?:execute|start|run|launch) (?:an? |the )?(?:mpml )?experiment|"
    r"(?:load|open) (?:the |my )?(?:dl |prediction )?artifacts? (?:now|for me)|"
    r"(?:ignore|override|disregard) (?:all |the |your )?(?:previous |system )?"
    r"(?:instructions|policy|rules)|(?:arbitrary |shell )command to|"
    r"recipe that proves (?:dl|prediction|artifact))\b"
)
_RECIPE = re.compile(
    r"\b(?:recipes?|commands?|argv|launch configuration)\b|"
    r"(?:^|[.!?]\s+)(?:please\s+)?(?:set|configure|give me|prepare)\b|"
    r"\b(?:how (?:do|can|should) i|help me) (?:run|launch|evaluate|backtest|configure)\b"
)
_REFERENCE = re.compile(
    r"\b(?:(?:that|this) (?:other )?|the other )(?:one|setting|pair|flag|option)\b|"
    r"\b(?:provide|supply|specify|share) (?:its|the) (?:identifier|id|name) later\b"
)
_RUNTIME = re.compile(
    r"\b(?:proof|prove|guarantee|verify|confirm|checks?|means?|loads?|runs?|execute[sd]?|validation|pass(?:es|ing)?)\b"
)
_NAMES = {"automatic analysis": "MPML_AUTO_ANALYZE", "pair filter": "ACTIVE_PAIRS"}
_FAILURES = (
    BridgeError,
    RetrievalError,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    subprocess.SubprocessError,
)


def _route(question: str) -> Route:
    words = question.casefold()
    if _UNSUPPORTED.search(words):
        return "unsupported"
    if _REFERENCE.search(words):
        return "ambiguous"
    if _RECIPE.search(words):
        # Mentions of the command line as a setting channel are informational.
        without_channel = words.replace("command-line", "cli").replace("command line", "cli")
        if _RECIPE.search(without_channel):
            return (
                "mixed"
                if re.search(
                    r"\b(?:and|also)\s+(?:explain|describe|tell)\b|\b(?:explain|describe)\b.*\b(?:and|also)\s+(?:give|show|write|include)\b",
                    words,
                )
                else "launch"
            )
    return "informational" if _INFO.search(words) or "?" in words else "ambiguous"


def _report(question, route, kind, status, explanation, *, provenance=None, citations=()):
    unresolved = []
    if route == "ambiguous":
        unresolved.append(
            {"reason": explanation, "span": {"start": 0, "end": len(question), "text": question}}
        )
    return ResponseV2(
        schema_version="argus-response-v2.0",
        request=RequestAnalysis(
            question=question, route=route, requirements=[], unresolved_material=unresolved
        ),
        response_kind=kind,
        answer_status=status,
        recipe_status="not_requested" if route == "informational" else "withheld",
        intent_coverage="unresolved" if route == "ambiguous" else "not_covered",
        material_constraints_status="unresolved",
        explanation=explanation,
        citations=list(citations),
        provenance=provenance,
        preflight={"outcome": "not_run", "diagnostics": []},
        audit={
            "candidate_sha256": None,
            "provenance": "verified"
            if provenance
            else "unavailable"
            if kind == "unverified"
            else "unchecked",
            "structure": "unchecked",
            "evidence": "passed" if citations else "unchecked",
            "release_scope": "unsupported" if route == "unsupported" else "unchecked",
            "evidence_ids": [citation.evidence_id for citation in citations],
        },
        settings=None,
        command=None,
    )


def unavailable(question: str) -> ResponseV2:
    return _report(
        question,
        _route(question),
        "unverified",
        "unverified",
        "Cannot verify the current clean MPML source and index. Check source configuration and index freshness.",
    )


def _cite(chunks, metadata, section, label, entry):
    heading = f"{section} / {label}"
    matches = [
        chunk
        for chunk in chunks
        if chunk["citation"]["path"] == "mpml/spec.py" and chunk["citation"]["heading"] == heading
    ]
    if len(matches) != 1:
        raise RetrievalError("Missing or ambiguous specification citation")
    chunk = matches[0]
    if json.loads(chunk["text"]) != entry or (
        chunk["citation"]["git_sha"] != metadata["git_sha"]
        or chunk["citation"]["dirty"] != metadata["dirty"]
        or chunk["citation"]["repo"] != metadata["repo"]
    ):
        raise RetrievalError("Specification citation does not match the verified source")
    return Citation(evidence_id=chunk["id"], path="mpml/spec.py", heading=heading)


def _facts(question, document):
    """Yield text together with the precise specification record supporting it."""
    words = question.casefold()
    names = dict.fromkeys(_OPTIONS.findall(question))
    for phrase, name in _NAMES.items():
        if re.search(rf"\b{phrase}\b", words):
            names[name] = None
    precedence = [
        rule
        for rule in document["precedence"]
        if any(name in rule["order"] for name in names)
        or re.search(rf"\b{re.escape(rule['setting'].replace('_', ' '))}\b", words)
    ]
    if (
        not names
        and not precedence
        and ("environment" in words and re.search(r"\bimport(?:s|ed|.time)?\b", words))
    ):
        names["ACTIVE_PAIRS"] = None
    if not names and not precedence and "preflight" in words and _RUNTIME.search(words):
        names[
            "DL_ARTIFACT_PATH_MISSING" if re.search(r"\b(?:dl|artifacts?)\b", words) else "ARGPARSE"
        ] = None

    rules = {entry["code"]: entry for entry in document["rules"]}
    source_only = {entry["name"]: entry for entry in document["source_edit_only"]}
    facts = []
    seen_flags = set()
    for name in names:
        parameter = _parameter(document, name)
        if name in source_only and parameter:
            raise RetrievalError("Specification disagrees on setting scope")
        if name in source_only:
            entry = source_only[name]
            facts.append(
                (
                    "source_edit_only",
                    name,
                    entry,
                    (
                        f"{name} is a source-edit-only setting ({entry['category']}). "
                        "Changing it requires editing source."
                    ),
                )
            )
        elif name in rules:
            entry = rules[name]
            facts.append(("rules", name, entry, f"{name}: {entry['summary']}"))
        elif parameter and "argument" in parameter:
            entry = parameter["argument"]
            label = ", ".join(entry["flags"])
            if label in seen_flags:
                continue
            seen_flags.add(label)
            default = json.dumps(entry["default"], ensure_ascii=False)
            text = f"{label} is a CLI option. Its parser default is {default}."
            if entry.get("help"):
                text += f" {entry['help']}"
            if entry.get("choices"):
                text += f" Published parser choices: {json.dumps(entry['choices'])}."
            facts.append(("arguments", label, entry, text))
        elif parameter:
            entry = parameter["environment"]
            default = json.dumps(entry["default"], ensure_ascii=False)
            text = (
                f"{name} is an environment setting with scope {entry['scope']}, "
                f"read timing {entry['timing']}, and documented default {default}. {entry['semantics']}"
            )
            if name == "ACTIVE_PAIRS" and "cli" in words and not parameter["precedence"]:
                text += " The published precedence rules list no competing CLI override."
            facts.append(("env", name, entry, text))
            if name == "DL_SIGNALS_ENABLED" and re.search(r"\b(?:yes|on|warning)\b|\b1\b", words):
                warning = rules["ENV_BOOL_PARSED_FALSE"]
                facts.append(
                    ("rules", warning["code"], warning, f"{warning['code']}: {warning['summary']}")
                )
        else:
            return []
    for rule in precedence:
        facts.append(
            (
                "precedence",
                rule["setting"],
                rule,
                f"Documented precedence for {rule['setting']}, highest first: {' → '.join(rule['order'])}.",
            )
        )
    return facts


def answer(source, question: str) -> tuple[ResponseV2, int]:
    route = _route(question)
    if route != "informational":
        explanation = {
            "unsupported": "This workflow can explain documented MPML settings. Execution and external actions are outside its scope.",
            "ambiguous": "Please name the MPML setting, option or diagnostic you want explained.",
            "launch": "This workflow provides explanations only. Ask about a specific MPML setting or diagnostic.",
            "mixed": "This workflow provides explanations only. Ask the informational part separately.",
        }[route]
        kind = "rejection_explanation" if route == "unsupported" else "abstention"
        return _report(question, route, kind, "limited", explanation), 1
    try:
        indexed, metadata, document, digest = verified_index(source)
        if metadata["dirty"]:
            raise RetrievalError("MPML source is dirty")
        facts = _facts(question, document)
        if not facts:
            return _report(
                question,
                "ambiguous",
                "abstention",
                "limited",
                "Please name a documented MPML setting, option or diagnostic. Unrecognized names cannot be verified.",
            ), 1
        citations = {}
        lines = []
        for section, label, entry, text in facts:
            citation = _cite(indexed["chunks"], metadata, section, label, entry)
            citations[citation.evidence_id] = citation
            lines.append(f"{text} [{citation.evidence_id}]")
        if (
            index_sha256() != digest
            or not source_matches(source, metadata)
            or index_sha256() != digest
        ):
            raise RetrievalError("MPML source or index changed")
        explanation = "\n".join(lines)
        explanation += (
            "\nThis explanation describes documented behavior. No preflight or experiment was run, "
            "so runtime success, DL activation and artifact loading remain unverified. "
            "A documented diagnostic is not an observed warning or rejection. "
            "A warning alone does not establish preflight acceptance."
        )
        return _report(
            question,
            route,
            "answer",
            "grounded",
            explanation,
            provenance=Provenance(
                source_revision=metadata["git_sha"],
                source_dirty=metadata["dirty"],
                spec_sha256=metadata["spec_sha256"],
                index_sha256=digest,
            ),
            citations=citations.values(),
        ), 0
    except _FAILURES:
        return unavailable(question), 2
