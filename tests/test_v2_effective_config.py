import json
from copy import deepcopy
from dataclasses import replace

import pytest

from argus_cli.provenance import spec_sha256
from argus_cli.v2_authorization import SnapshotIdentity, VerifiedSnapshot, bind
from argus_cli.v2_contract import Settings
from argus_cli.v2_effective_config import resolve_effective_configuration
from argus_cli.v2_intent import extract

SPEC = {
    "arguments": [
        {
            "flags": [flag],
            "type": kind,
            "action": "store",
            "nargs": None,
            "default": None,
            "choices": choices,
        }
        for flag, kind, choices in (
            ("--experiment-seed", "int", None),
            ("--experiment-variant", "str", ["A", "B", "C"]),
            ("--output-dir", "Path", None),
        )
    ],
    "env": [
        {
            "name": "EXPERIMENT_SEED",
            "scope": "launch_selector",
            "parser": "int",
            "default": 42,
            "semantics": "CLI seed wins. Environment text is stripped; blank uses 42 and malformed nonempty text raises ValueError.",
        },
        {
            "name": "EXPERIMENT_VARIANT",
            "scope": "launch_selector",
            "parser": "enum",
            "default": "A",
            "semantics": "CLI value takes precedence; otherwise environment value, then A.",
        },
    ],
    "precedence": [
        {"setting": "experiment_seed", "order": ["--experiment-seed", "EXPERIMENT_SEED", "42"]},
        {
            "setting": "experiment_variant",
            "order": ["--experiment-variant", "EXPERIMENT_VARIANT", "A"],
        },
    ],
    "source_edit_only": [{"name": "SPREAD_PIPS"}],
}


def inputs(argv=(), overrides=None, inherited=None, spec=SPEC):
    snapshot = VerifiedSnapshot(
        SnapshotIdentity("revision", False, spec_sha256(spec), "a" * 64),
        json.dumps(spec).encode(),
        frozenset(),
        "trusted_adapter",
    )
    request = extract("Use seed 20.", spec)
    candidate = Settings(argv=list(argv), env=overrides or {})
    inherited = inherited or {}
    return snapshot, request, candidate, inherited, bind(snapshot, request, candidate, inherited)


@pytest.mark.parametrize(
    ("argv", "override", "inherited", "winner", "value"),
    [
        (["--experiment-seed", "57"], "bad", "59", "cli", 57),
        (["--experiment-seed=-7"], "52", "58", "cli", -7),
        ([], "52", "58", "explicit_env", 52),
        ([], None, "  +58 ", "inherited_env", 58),
        ([], None, None, "published_fallback", 42),
        ([], "", "58", "published_fallback", 42),
        ([], " \t", "58", "published_fallback", 42),
        ([], None, "", "published_fallback", 42),
        ([], "bad", "58", None, None),
        ([], None, "2.5", None, None),
        (["--experiment-seed", "bad"], None, "58", None, None),
        (["--experiment-seed", "57", "--experiment-seed", "58"], None, None, None, None),
        (["--experiment-seed"], None, None, None, None),
    ],
)
def test_seed(argv, override, inherited, winner, value):
    args = inputs(
        argv,
        {} if override is None else {"EXPERIMENT_SEED": override},
        {} if inherited is None else {"EXPERIMENT_SEED": inherited},
    )
    original = args[2].model_dump()
    (item,) = resolve_effective_configuration(*args, selectors=("experiment_seed",))
    assert (item.winner, item.value, item.independently_verified) == (
        winner,
        value,
        winner is not None,
    )
    assert item.evidence[0] == "precedence / experiment_seed"
    assert bool(item.reason) == (winner is None)
    assert args[2].model_dump() == original


@pytest.mark.parametrize(
    ("argv", "override", "inherited", "winner", "value"),
    [
        (["--experiment-variant=B"], "C", "A", "cli", "B"),
        ([], "B", "C", "explicit_env", "B"),
        ([], None, "C", "inherited_env", "C"),
        ([], None, None, "published_fallback", "A"),
        ([], "", "C", None, None),
        ([], " B ", "C", None, None),
        ([], "b", "C", None, None),
        ([], "D", "C", None, None),
    ],
)
def test_variant(argv, override, inherited, winner, value):
    args = inputs(
        argv,
        {} if override is None else {"EXPERIMENT_VARIANT": override},
        {} if inherited is None else {"EXPERIMENT_VARIANT": inherited},
    )
    (item,) = resolve_effective_configuration(*args, selectors=("experiment_variant",))
    assert (item.winner, item.value, item.independently_verified) == (
        winner,
        value,
        winner is not None,
    )


@pytest.mark.parametrize("change", ["missing", "conflict", "default", "undocumented"])
def test_unpublished_or_conflicting_precedence(change):
    spec = deepcopy(SPEC)
    if change == "missing":
        spec["precedence"].pop(0)
    elif change == "conflict":
        spec["precedence"][0]["order"].reverse()
    elif change == "default":
        spec["env"][0]["default"] = 12
    else:
        spec["env"][0]["semantics"] = "Read an integer."
    result = resolve_effective_configuration(*inputs(spec=spec))
    assert not result[0].independently_verified
    assert result[1].independently_verified


@pytest.mark.parametrize("change", ["snapshot", "env", "argv", "authority", "dirty"])
def test_binding_mismatch_or_untrusted_source_blocks_observations(change):
    snapshot, request, candidate, inherited, binding = inputs()
    if change == "snapshot":
        snapshot = replace(snapshot, identity=replace(snapshot.identity, index_sha256="b" * 64))
    elif change == "env":
        inherited["EXPERIMENT_SEED"] = "222"
    elif change == "argv":
        candidate.argv.extend(["--experiment-seed", "222"])
    elif change == "authority":
        snapshot = replace(snapshot, authority="model")
    else:
        snapshot = replace(snapshot, identity=replace(snapshot.identity, source_dirty=True))
        binding = bind(snapshot, request, candidate, inherited)
    assert all(
        not item.independently_verified and item.value is None
        for item in resolve_effective_configuration(
            snapshot, request, candidate, inherited, binding
        )
    )


def test_partial_result_does_not_infer_output_paths_or_source_edit_settings():
    result = resolve_effective_configuration(
        *inputs(["--output-dir", "relative/path"]),
        selectors=("experiment_seed", "experiment_variant", "output_directory", "SPREAD_PIPS"),
    )
    assert [item.independently_verified for item in result] == [True, True, False, False]
    assert all(item.value is None for item in result[2:])
