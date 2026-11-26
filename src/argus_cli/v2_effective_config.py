"""Bound effective values for the documented seed and variant selectors."""

from dataclasses import dataclass, field
from typing import Literal

from argus_cli.v2_authorization import Binding, VerifiedSnapshot, bind
from argus_cli.v2_contract import Settings
from argus_cli.v2_intent import Interpretation, Vocabulary, _candidate_values

Winner = Literal["cli", "explicit_env", "inherited_env", "published_fallback"]
_SUPPORTED = {
    "experiment_seed": ("--experiment-seed", "EXPERIMENT_SEED", "int"),
    "experiment_variant": ("--experiment-variant", "EXPERIMENT_VARIANT", "enum"),
}
_SEED_SEMANTICS = (
    "CLI seed wins. Environment text is stripped; blank uses {fallback} "
    "and malformed nonempty text raises ValueError."
)
_VARIANT_SEMANTICS = "CLI value takes precedence; otherwise environment value, then {fallback}."


@dataclass(frozen=True)
class EffectiveObservation:
    setting: str
    independently_verified: bool
    winner: Winner | None = None
    evidence: tuple[str, ...] = ()
    reason: str | None = None
    # Private result for trusted callers. Live reports omit all values.
    value: int | str | None = field(default=None, repr=False)


def _published_rule(spec, vocab, setting):
    flag, key, parser = _SUPPORTED[setting]
    rows = [row for row in spec["precedence"] if row["setting"] == setting]
    args = [row for row in spec["arguments"] if flag in row["flags"]]
    env = [row for row in spec["env"] if row["name"] == key]
    if len(rows) != 1 or len(args) != 1 or len(env) != 1 or key not in vocab.env:
        return None
    order = rows[0]["order"]
    argument, variable = args[0], env[0]
    if (
        len(order) != 3
        or order[:2] != [flag, key]
        or argument.get("action") != "store"
        or argument.get("nargs") is not None
        or argument.get("default") is not None
        or variable.get("alias_of", None) is not None
        or variable.get("parser") != parser
    ):
        return None

    fallback = variable.get("default")
    choices = argument.get("choices")
    if parser == "int":
        if type(fallback) is not int or argument.get("type") != "int":
            return None
        semantics = _SEED_SEMANTICS
    else:
        if (
            argument.get("type") != "str"
            or not isinstance(choices, list)
            or not choices
            or any(not isinstance(value, str) or not value for value in choices)
            or fallback not in choices
        ):
            return None
        semantics = _VARIANT_SEMANTICS
    if order[2] != str(fallback) or variable.get("semantics") != semantics.format(
        fallback=fallback
    ):
        return None
    return flag, key, parser, fallback, choices


def resolve_effective_configuration(
    snapshot: VerifiedSnapshot,
    request: Interpretation,
    settings: Settings,
    inherited_env: dict[str, str],
    expected_binding: Binding,
    *,
    selectors: tuple[str, ...] = (*_SUPPORTED, "output_directory"),
) -> tuple[EffectiveObservation, ...]:
    """Resolve exact inputs against the pinned spec, without a complete-config verdict."""
    candidate = settings.model_copy(deep=True)
    inherited_env = inherited_env.copy()
    if (
        snapshot.authority != "trusted_adapter"
        or snapshot.identity.source_dirty
        or bind(snapshot, request, candidate, inherited_env) != expected_binding
    ):
        return tuple(
            EffectiveObservation(
                setting, False, reason="Unverified snapshot or input binding mismatch."
            )
            for setting in selectors
        )
    spec = snapshot.read_spec()
    vocab = Vocabulary.from_spec(spec)
    values, issues = _candidate_values(candidate.argv, candidate.env, vocab)
    observations = []
    for setting in selectors:
        if setting not in _SUPPORTED:
            observations.append(
                EffectiveObservation(setting, False, reason="Selector outside supported scope.")
            )
            continue
        rule = _published_rule(spec, vocab, setting)
        if rule is None:
            observations.append(
                EffectiveObservation(
                    setting, False, reason="Missing or unsupported published semantics."
                )
            )
            continue
        flag, key, parser, fallback, choices = rule
        evidence = (
            f"precedence / {setting}",
            f"arguments / {', '.join(vocab.flags[flag]['flags'])}",
            f"env / {key}",
        )
        if issues:
            observations.append(
                EffectiveObservation(
                    setting,
                    False,
                    evidence=evidence,
                    reason="Candidate option structure or choices could not be verified.",
                )
            )
            continue
        winner: Winner
        if vocab.canonical(flag) in values:
            winner, raw = "cli", values[vocab.canonical(flag)][0]
        elif key in candidate.env:
            winner, raw = "explicit_env", candidate.env[key]
        elif key in inherited_env:
            winner, raw = "inherited_env", inherited_env[key]
        else:
            winner, raw = "published_fallback", str(fallback)

        value: int | str
        if parser == "int":
            if winner in {"explicit_env", "inherited_env"}:
                raw = raw.strip()
                if not raw:
                    winner, raw = "published_fallback", str(fallback)
            try:
                value = int(raw)
            except ValueError:
                observations.append(
                    EffectiveObservation(
                        setting, False, evidence=evidence, reason="Winning seed is not an integer."
                    )
                )
                continue
        elif raw in choices:
            value = raw
        else:
            observations.append(
                EffectiveObservation(
                    setting,
                    False,
                    evidence=evidence,
                    reason="Winning variant is outside documented canonical choices.",
                )
            )
            continue
        observations.append(EffectiveObservation(setting, True, winner, evidence, value=value))
    return tuple(observations)
