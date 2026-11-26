"""Offline interpretation of explicit, bounded MPML launch clauses."""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from argus_cli.v2_answer import _route
from argus_cli.v2_contract import (
    IntentCoverage,
    RequestAnalysis,
    Requirement,
    Span,
    UnresolvedRequirement,
)


@dataclass(frozen=True)
class InterpretationRules:
    """Phrase bindings are usable only if their literal target is published."""

    phrases: tuple[tuple[str, str], ...]


MPML_RULES = InterpretationRules(
    (
        ("strategy", "--strategy"),
        ("strategies", "--strategy"),
        ("phaseaware tf", "--phaseaware-tf"),
        ("phaseaware mr", "--phaseaware-mr"),
        ("trend-following representative", "--phaseaware-tf"),
        ("mean-reversion representative", "--phaseaware-mr"),
        ("pairs", "ACTIVE_PAIRS"),
        ("pair filter", "ACTIVE_PAIRS"),
        ("variant", "--experiment-variant"),
        ("experiment variant", "--experiment-variant"),
        ("seed", "--experiment-seed"),
        ("experiment seed", "--experiment-seed"),
        ("output directory", "--output-dir"),
    )
)

_SPLIT = re.compile(r";|\n|(?<=[.!?])\s+|\s+and\s+", re.IGNORECASE)
_WRAPPER = re.compile(
    r"(?:(?:please\s+)?(?:give me|prepare|write|build|construct|generate) "
    r"(?:an? |the )?(?:mpml |launch )?(?:recipe|command) (?:with|using) )",
    re.IGNORECASE,
)
_CONTEXT = re.compile(
    r'["“”‘\x60]|(?<!\w)[\x27’]|\b(?:if|unless|suppose|imagine|hypothetically|example|for instance|'
    r"maybe|or|previous|earlier|same|other|not sure|somehow|tbd|unspecified|unsure)\b",
    re.IGNORECASE,
)
_INFO = re.compile(r"(?:what|which|why|when|does|explain|describe|tell me)\b", re.IGNORECASE)
_NEGATE = re.compile(
    r"(?:do not|don't|never|exclude|omit|without)\s+(?:use\s+|set\s+)?", re.IGNORECASE
)
_ACTION = re.compile(r"(?:please\s+)?(?:use|set|select|choose|pin)\s+", re.IGNORECASE)
_DEFAULT = re.compile(
    r"(?:use |keep )?(?:the )?(?:documented |unchanged )?defaults(?: only)?", re.IGNORECASE
)
_CHANNEL = re.compile(
    r"(?:(cli|env(?:ironment)?) only|only via (cli|env(?:ironment)?))$", re.IGNORECASE
)
_VALUE = re.compile(r"[A-Za-z0-9_./][A-Za-z0-9_./:+-]*")
_LITERAL = re.compile(r"--[\w-]+|[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")
_NO_SUB = re.compile(r",?\s+(?:without substitutions|no substitutions)$", re.IGNORECASE)
_UNSAFE_CONTEXT = re.compile(
    r"\b(?:ignore|override|disregard)\b.*\b(?:instructions|rules|policy)\b",
    re.IGNORECASE | re.DOTALL,
)
_ZERO_ARG = {"store_true", "store_false", "store_const", "count"}


@dataclass(frozen=True)
class Interpretation:
    analysis: RequestAnalysis
    coverage: IntentCoverage


@dataclass(frozen=True)
class Consistency:
    satisfied: tuple[Requirement, ...]
    violated: tuple[Requirement, ...]
    unresolved: tuple[UnresolvedRequirement, ...]
    candidate_issues: tuple[str, ...]
    candidate_targets: tuple[str, ...]


@dataclass(frozen=True)
class Vocabulary:
    flags: dict[str, dict]
    env: dict[str, dict]
    peers: dict[str, str]

    @classmethod
    def from_spec(cls, spec):
        flags = {flag: row for row in spec["arguments"] for flag in row["flags"]}
        env = {row["name"]: row for row in spec["env"] if row["scope"] == "launch_selector"}
        peers = {}
        for row in spec["precedence"]:
            cli_keys = [key for key in row["order"] if key in flags]
            env_keys = [key for key in row["order"] if key in env]
            if len(cli_keys) == len(env_keys) == 1:
                flag, name = cli_keys[0], env_keys[0]
                for alias in flags[flag]["flags"]:
                    peers[alias] = name
                peers[name] = flags[flag]["flags"][0]
        return cls(flags, env, peers)

    def canonical(self, target):
        return self.flags[target]["flags"][0] if target in self.flags else target

    def channel(self, target):
        if target in self.flags:
            return "cli"
        if target in self.env:
            return "env"
        return None

    def accepts_many(self, target):
        return (
            target in self.flags
            and self.flags[target]["action"] in {"append", "count"}
            or target in self.env
            and self.env[target]["parser"] == "csv"
        )


def _clauses(question):
    start = 0
    for match in (*_SPLIT.finditer(question), None):
        end = len(question) if match is None else match.start()
        text = question[start:end]
        left = start + len(text) - len(text.lstrip())
        right = start + len(text.rstrip())
        if left < right:
            yield Span(start=left, end=right, text=question[left:right])
        if match is not None:
            start = match.end()


def _split_values(text, csv):
    if csv:
        return tuple(piece.strip().upper() for piece in text.split(","))
    return tuple(re.split(r"\s*,\s*|\s+(?:then|before)\s+", text, flags=re.IGNORECASE))


def _parse_clause(span, vocab, rules, *, continuation=False):
    text = span.text.rstrip(".;!?").strip()
    wrapper = _WRAPPER.match(text)
    if wrapper:
        text = text[wrapper.end() :]
    default = _DEFAULT.fullmatch(text)
    if default:
        return [
            Requirement(
                target="*", operator="defaults_only", channel="either", values=[], span=span
            )
        ]

    negative = _NEGATE.match(text)
    action = negative or _ACTION.match(text)
    if action:
        text = text[action.end() :]
    literal = _LITERAL.match(text)
    if literal and not (wrapper or action or continuation) and span.text.endswith("?"):
        return []
    if not (wrapper or action or literal or continuation):
        return []
    if literal:
        target = literal.group()
        text = text[literal.end() :]
    else:
        for phrase, binding in sorted(rules.phrases, key=lambda pair: -len(pair[0])):
            phrase_match = re.match(rf"{re.escape(phrase)}\b", text, re.IGNORECASE)
            if phrase_match:
                target = binding
                text = text[phrase_match.end() :]
                break
        else:
            return []

    channel = vocab.channel(target)
    if channel is None:
        return []
    exclusive = _CHANNEL.search(text)
    if exclusive:
        if negative:
            return []
        requested_channel = "cli" if (exclusive[1] or exclusive[2]).lower() == "cli" else "env"
        if requested_channel != channel and not literal and target in vocab.peers:
            target = vocab.peers[target]
            channel = vocab.channel(target)
        if requested_channel != channel:
            return []
        text = text[: exclusive.start()]
    peer = vocab.peers.get(target)
    target = vocab.canonical(target)
    text = re.sub(r"^\s*(?:=|to\b)?\s*", "", text, flags=re.IGNORECASE).strip()
    no_sub = _NO_SUB.search(text)
    if no_sub:
        text = text[: no_sub.start()].rstrip()
    ordered = bool(re.search(r"\b(?:then|before|in that order)\b", text, re.IGNORECASE))
    text = re.sub(r",?\s+in that order$", "", text, flags=re.IGNORECASE)
    csv = target in vocab.env and vocab.env[target]["parser"] == "csv"
    values = _split_values(text, csv) if text else ()
    if target in vocab.flags and vocab.accepts_many(target):
        values = tuple(re.sub(rf"^{re.escape(target)}(?:=|\s+)", "", value) for value in values)
    zero_arg = target in vocab.flags and vocab.flags[target]["action"] in _ZERO_ARG
    if (
        any(
            not _VALUE.fullmatch(value) or value.casefold() in {"not", "only", "the", "default"}
            for value in values
        )
        or (csv and any(not re.fullmatch(r"[A-Z]{6}", value) for value in values))
        or (len(values) > 1 and not vocab.accepts_many(target))
        or (zero_arg and values)
        or (not values and (no_sub or ordered or (not negative and not zero_arg)))
        or (negative and (no_sub or ordered))
    ):
        return []
    operator = (
        "forbid"
        if negative
        else "ordered"
        if ordered
        else "no_substitution"
        if no_sub
        else "require"
    )
    result = [
        Requirement(
            target=target, operator=operator, channel=channel, values=list(values), span=span
        )
    ]
    if exclusive and peer:
        result.append(
            Requirement(
                target=vocab.canonical(peer),
                operator="forbid",
                channel=vocab.channel(peer),
                values=[],
                span=span,
            )
        )
    return result


def _conflicts(requirements, vocab):
    positives = defaultdict(list)
    forbids = defaultdict(list)
    defaults = [item for item in requirements if item.operator == "defaults_only"]
    for item in requirements:
        if item.operator == "forbid":
            forbids[item.target].append(item)
        elif item.operator != "defaults_only":
            positives[item.target].append(item)
    for target, items in positives.items():
        values = {tuple(item.values) for item in items}
        if (
            defaults
            or (
                len(items) > 1
                and vocab.accepts_many(target)
                and any(item.operator in {"ordered", "no_substitution"} for item in items)
            )
            or (len(values) > 1 and (not vocab.accepts_many(target) or target in vocab.env))
            or any(
                not forbidden.values or set(forbidden.values) & set(item.values)
                for forbidden in forbids[target]
                for item in items
            )
        ):
            yield UnresolvedRequirement(
                reason="Conflicting explicit requirements.", span=items[-1].span
            )


def extract(question: str, spec: dict, rules: InterpretationRules = MPML_RULES) -> Interpretation:
    """Extract requirements and retain every clause outside the bounded grammar."""
    vocab = Vocabulary.from_spec(spec)
    route = _route(question)
    requirements = []
    unresolved = []
    # Do not split quotations or conditionals into independently actionable fragments.
    # Conjunctions are safe to split only after these whole-question context checks.
    if _UNSAFE_CONTEXT.search(question):
        route = "unsupported"
    if (
        route == "unsupported"
        or _CONTEXT.search(question)
        or re.search(
            r"\b(?:do not|don't|never|exclude|omit|without)\b[^;.!?]*\band\s+(?:--|[A-Z][A-Z0-9]*_)",
            question,
            re.IGNORECASE,
        )
    ):
        if route != "unsupported":
            route = "ambiguous"
        unresolved.append(
            UnresolvedRequirement(
                reason="Unsupported, quoted, conditional or ambiguous request context.",
                span=Span(start=0, end=len(question), text=question),
            )
        )
    else:
        previous = None
        prior_positive = False
        informational = []
        for span in _clauses(question):
            continuation = (
                prior_positive and question[previous.end : span.start].strip().casefold() == "and"
            )
            previous = span
            prior_positive = False
            if _INFO.match(span.text) and not _WRAPPER.match(span.text):
                informational.append(span)
                continue
            parsed = _parse_clause(span, vocab, rules, continuation=continuation)
            if parsed:
                requirements.extend(parsed)
                prior_positive = all(item.operator == "require" for item in parsed)
            else:
                unresolved.append(
                    UnresolvedRequirement(
                        reason="Clause is incomplete or outside launch grammar.", span=span
                    )
                )
        if requirements or route != "informational":
            unresolved.extend(
                UnresolvedRequirement(
                    reason="Informational clause is outside launch grammar.", span=span
                )
                for span in informational
            )
        unresolved.sort(key=lambda item: item.span.start)
    unresolved.extend(_conflicts(requirements, vocab))
    if requirements:
        coverage = "partial" if unresolved else "enforced"
        if route in {"ambiguous", "informational"}:
            route = (
                "mixed" if any(_INFO.match(span.text) for span in _clauses(question)) else "launch"
            )
    elif not unresolved:
        coverage = "not_covered"
    else:
        coverage = "unresolved"
    if route == "ambiguous" and not unresolved:
        unresolved.append(
            UnresolvedRequirement(
                reason="Launch intent could not be established.",
                span=Span(start=0, end=len(question), text=question),
            )
        )
        coverage = "unresolved"
    return Interpretation(
        RequestAnalysis(
            question=question,
            route=route,
            requirements=requirements,
            unresolved_material=unresolved,
        ),
        coverage,
    )


def _candidate_values(argv, env, vocab):
    actual = defaultdict(list)
    issues = []
    args = iter(argv)
    for token in args:
        flag, separator, inline = token.partition("=")
        row = vocab.flags.get(flag)
        if row is None:
            issues.append(f"Unrecognized CLI option or token: {flag}")
            continue
        target = vocab.canonical(flag)
        action = row["action"]
        if action in _ZERO_ARG and not separator:
            value = ""
        elif action in {"store", "append"} and row.get("nargs") in {None, 1}:
            value = inline if separator else next(args, None)
            if value is None or not value or value.startswith("--"):
                issues.append(f"Missing or unsupported CLI value for {flag}")
                continue
            choices = row.get("post_parse_choices") or row.get("choices")
            if choices is not None and value not in {str(choice) for choice in choices}:
                issues.append(f"Value outside published choices for {flag}")
        else:
            issues.append(f"Unsupported CLI argument shape for {flag}")
            continue
        if actual[target] and not vocab.accepts_many(target):
            issues.append(f"Repeated scalar CLI option: {flag}")
        actual[target].append(value)
    for name, value in env.items():
        if name not in vocab.env:
            issues.append(f"Unrecognized launch environment override: {name}")
            continue
        if vocab.env[name]["parser"] == "csv":
            actual[name] = list(_split_values(value, True))
        else:
            actual[name] = [value]
    return actual, issues


def check_candidate(
    interpretation: Interpretation, argv: list[str], env: dict[str, str], spec: dict
) -> Consistency:
    """Compare explicit constraints only. No structural or release verdict is issued."""
    vocab = Vocabulary.from_spec(spec)
    actual, issues = _candidate_values(argv, env, vocab)
    satisfied = []
    violated = []
    requested = defaultdict(list)
    for item in interpretation.analysis.requirements:
        if item.operator not in {"forbid", "defaults_only"}:
            requested[item.target].extend(item.values)
    for item in interpretation.analysis.requirements:
        target = item.target
        values = actual.get(target, [])
        if item.operator == "defaults_only":
            matches = not actual and not issues
        elif item.channel != vocab.channel(target):
            issues.append(f"Requirement target or channel is not published: {target}")
            matches = False
        elif item.operator == "forbid":
            matches = not (set(item.values) & set(values)) if item.values else target not in actual
        elif item.channel == "env" and (
            (peer := vocab.peers.get(target)) in actual and peer not in requested
        ):
            matches = False
        elif item.operator in {"ordered", "no_substitution"}:
            matches = values == item.values
        else:
            expected = (
                requested[target]
                if vocab.accepts_many(target) and target not in vocab.env
                else item.values
            )
            matches = (Counter(values) == Counter(expected)) if expected else target in actual
        (satisfied if matches else violated).append(item)
    return Consistency(
        tuple(satisfied),
        tuple(violated),
        tuple(interpretation.analysis.unresolved_material),
        tuple(issues),
        tuple(actual),
    )
