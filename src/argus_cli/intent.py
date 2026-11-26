"""Narrow checks of explicit MPML requirements, independent of preflight."""

import re
from dataclasses import dataclass
from typing import Literal

Coverage = Literal["enforced", "unresolved", "not_covered"]
Operator = Literal["exact", "absent", "pairs"]
_ID = r"[A-Z][A-Z0-9_]*[0-9][A-Z0-9_]*"
_PAIR = r"[A-Z]{6}"
_SETTING = {
    "random seed": ("--experiment-seed", "EXPERIMENT_SEED", r"[0-9]+"),
    "experiment variant": ("--experiment-variant", "EXPERIMENT_VARIANT", r"[A-Z]"),
    "behavioral surface": ("--behavioral-surface", "BEHAVIORAL_SURFACE", r"[a-z_]+"),
}


@dataclass(frozen=True)
class Constraint:
    span: tuple[int, int]
    channel: Literal["argv", "env"]
    target: str
    operator: Operator
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Intent:
    coverage: Coverage
    constraints: tuple[Constraint, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntentCheck:
    satisfied: tuple[Constraint, ...]
    violated: tuple[Constraint, ...]
    unresolved: tuple[str, ...]


def extract(question: str, spec: dict) -> Intent:
    """Recognize complete, anchored requests. Values still belong to MPML preflight."""
    text = question.rstrip().rstrip(".?").lstrip()
    offset = len(question) - len(question.lstrip())
    flags = {name for item in spec["arguments"] for name in item["flags"]}
    env = {item["name"] for item in spec["env"] if item.get("scope") == "launch_selector"}

    def make(match, channel, target, values=(), operator="exact", group=0):
        start, end = match.span(group)
        return Constraint((start + offset, end + offset), channel, target, operator, tuple(values))

    def enforce(*constraints):
        if any(
            item.target not in (flags if item.channel == "argv" else env) for item in constraints
        ):
            return Intent(
                "unresolved", uncertainty=("Required setting is absent from the live spec.",)
            )
        return Intent("enforced", constraints)

    if re.fullmatch(
        r"(?:which MPML launch flags )?(?:place|submit|execute) (?:a )?live broker order(?: for [A-Z]{6})?",
        text,
        re.IGNORECASE,
    ):
        return Intent("unresolved", uncertainty=("Live broker orders are unsupported.",))
    if re.fullmatch(
        r"can preflight (?:prove|confirm) (?:DL (?:is active|activation)"
        r"(?: and (?:the prediction artifact was actually loaded|artifact loading))?"
        r"|the prediction artifact was actually loaded|artifact loading)",
        text,
        re.IGNORECASE,
    ):
        return Intent(
            "unresolved", uncertainty=("Preflight cannot prove DL activation or artifact loading.",)
        )
    if re.fullmatch(
        r"(?:use|evaluate) the (?:previous strategy|same strategy|strategy we agreed on earlier)"
        r"(?: and no other strategies)?(?:\. I have not provided the strategy name in this question)?",
        text,
        re.IGNORECASE,
    ):
        return Intent("unresolved", uncertainty=("An explicit strategy identifier is missing.",))

    match = re.fullmatch(
        rf"(?:how do I )?evaluate (?:only )?(?P<strategy>{_ID})(?: on (?P<pair>{_PAIR}))?"
        r"(?:\. Do not replace it with another strategy)?",
        text,
        re.IGNORECASE,
    )
    if match:
        strategy = make(match, "argv", "--strategy", [match["strategy"].upper()], group="strategy")
        if match["pair"] is None:
            return enforce(strategy)
        return enforce(
            strategy, make(match, "env", "ACTIVE_PAIRS", [match["pair"].upper()], "pairs", "pair")
        )

    match = re.fullmatch(
        rf"evaluate (?P<first>{_ID}) followed by (?P<second>{_ID})(?: in the same launch)?, in that order",
        text,
        re.IGNORECASE,
    )
    if match:
        return enforce(
            make(match, "argv", "--strategy", [match["first"].upper(), match["second"].upper()])
        )
    match = re.fullmatch(
        rf"(?:(?i:use) )?(?P<options>--strategy(?:=| ){_ID}(?: --strategy(?:=| ){_ID})*)", text
    )
    if match:
        values = re.findall(rf"--strategy(?:=| )({_ID})", match["options"])
        return enforce(make(match, "argv", "--strategy", values, group="options"))

    match = re.fullmatch(
        rf"use only (?P<pairs>{_PAIR}(?:, {_PAIR})*(?: and {_PAIR})?)(?:, in that order)?"
        r"(?P<default>, with the default strategy selection)?",
        text,
        re.IGNORECASE,
    )
    if match:
        values = re.split(r", | AND ", match["pairs"].upper())
        pairs = make(match, "env", "ACTIVE_PAIRS", values, "pairs", "pairs")
        if match["default"]:
            return enforce(
                pairs, make(match, "argv", "--strategy", operator="absent", group="default")
            )
        return enforce(pairs)
    match = re.fullmatch(rf"(?:(?i:set|use) )?ACTIVE_PAIRS=(?P<pairs>{_PAIR}(?:, ?{_PAIR})*)", text)
    if match:
        return enforce(make(match, "env", "ACTIVE_PAIRS", [match["pairs"]], group="pairs"))
    match = re.fullmatch(r"use (?:only )?the default strategy selection", text, re.IGNORECASE)
    if match:
        return enforce(make(match, "argv", "--strategy", operator="absent"))

    match = re.fullmatch(
        rf"(?:use|set) (?P<strategy>{_ID}) as the PhaseAware "
        r"(?P<role>trend-following|mean-reversion) representative(?:\. Do not substitute another strategy)?",
        text,
        re.IGNORECASE,
    )
    if match:
        flag, other = ("--phaseaware-tf", "--phaseaware-mr")
        if match["role"].lower() == "mean-reversion":
            flag, other = other, flag
        return enforce(
            make(match, "argv", flag, [match["strategy"].upper()]),
            make(match, "argv", other, operator="absent"),
        )
    match = re.fullmatch(
        rf"set (?P<tf>{_ID}) as the PhaseAware trend-following representative and "
        rf"(?P<mr>{_ID}) as the mean-reversion representative, without filtering the evaluated strategies",
        text,
        re.IGNORECASE,
    )
    if match:
        return enforce(
            make(match, "argv", "--phaseaware-tf", [match["tf"].upper()], group="tf"),
            make(match, "argv", "--phaseaware-mr", [match["mr"].upper()], group="mr"),
            make(match, "argv", "--strategy", operator="absent"),
        )

    for name, (flag, key, value) in _SETTING.items():
        match = re.fullmatch(
            rf"set (?:the MPML )?{name}(?: to)? (?P<value>{value}) "
            r"(?:using|through) (?:an? |the )?(?P<channel>environment(?: override)?|CLI(?: flag)?) only",
            text,
            re.IGNORECASE,
        )
        if match:
            if match["channel"].lower().startswith("cli"):
                return enforce(
                    make(match, "argv", flag, [match["value"]]),
                    make(match, "env", key, operator="absent"),
                )
            return enforce(
                make(match, "env", key, [match["value"]]),
                make(match, "argv", flag, operator="absent"),
            )
        match = re.fullmatch(
            rf"use the {flag} flag to set (?:the MPML )?{name} to (?P<value>{value})",
            text,
            re.IGNORECASE,
        )
        if match:
            return enforce(
                make(match, "argv", flag, [match["value"]]),
                make(match, "env", key, operator="absent"),
            )

    precedence = (
        ("EXPERIMENT_SEED", "--experiment-seed", r"[0-9]+", r"make this run use seed"),
        ("EXPERIMENT_VARIANT", "--experiment-variant", r"[A-Z]", r"select variant"),
        ("BEHAVIORAL_SURFACE", "--behavioral-surface", r"[a-z_]+", r"select"),
    )
    for key, flag, value, action in precedence:
        match = re.fullmatch(
            rf"keep (?P<env>{key}={value})(?: as an environment override| in the environment),? but "
            rf"(?P<cli>{action} ({value}) (?:through the CLI|on the command line))",
            text,
            re.IGNORECASE,
        )
        if match:
            return enforce(
                make(match, "env", key, [match["env"].split("=", 1)[1]], group="env"),
                make(match, "argv", flag, [match[3]], group="cli"),
            )

    if re.search(
        r"\b(?:only|except|must|require|substitute|contradict)\b|--[a-z]", text, re.IGNORECASE
    ):
        return Intent(
            "unresolved",
            uncertainty=("An explicit requirement is outside the supported patterns.",),
        )
    return Intent(
        "not_covered", uncertainty=("The request is outside deterministic intent coverage.",)
    )


def check(intent: Intent, argv: list[str], env: dict[str, str]) -> IntentCheck:
    """Inspect only targeted settings after the existing structural gate."""
    options: dict[str, list[str]] = {}
    for index, token in enumerate(argv):
        if not token.startswith("--"):
            continue
        key, equals, value = token.partition("=")
        if not equals:
            value = argv[index + 1] if index + 1 < len(argv) else ""
        options.setdefault(key, []).append(value)

    satisfied, violated = [], []
    for item in intent.constraints:
        if item.channel == "argv":
            actual = tuple(options.get(item.target, ()))
        elif item.target in env:
            value = env[item.target]
            actual = (
                (value,)
                if item.operator != "pairs"
                else tuple(part.strip().upper() for part in value.split(","))
            )
        else:
            actual = ()
        matches = not actual if item.operator == "absent" else actual == item.values
        (satisfied if matches else violated).append(item)
    return IntentCheck(tuple(satisfied), tuple(violated), intent.uncertainty)
