"""Load versioned evaluation fixtures from the repository's fixture directory."""

import hashlib
import json
import re
from pathlib import Path

DEFAULT_DATASET = "baseline-v1"
_BASELINE = Path(__file__).with_name("baseline-v1.json")
_FIXTURES = Path(__file__).with_name("fixtures")
_VERSIONED_ID = re.compile(r"(holdout|development)-v[1-9][0-9]{0,5}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DISPOSITIONS = {"validated", "validated_with_warnings", "rejected", "abstained"}


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _strings(value):
    return isinstance(value, list) and all(
        isinstance(item, str) and "\x00" not in item for item in value
    )


def _validate_gold(alternative):
    if not isinstance(alternative, dict) or alternative.get("verification") not in _DISPOSITIONS:
        raise ValueError("Invalid expected verification disposition")
    codes = alternative.get("diagnostic_codes")
    if not _strings(codes) or not all(_text(code) for code in codes):
        raise ValueError("Expected diagnostic_codes must be a list of nonempty strings")
    if "argv" not in alternative and "env" not in alternative:
        if alternative["verification"] != "abstained" or codes:
            raise ValueError("Only an abstention without preflight can omit argv and env")
        return
    argv, env = alternative.get("argv"), alternative.get("env")
    if (
        not _strings(argv)
        or not isinstance(env, dict)
        or any(
            not _text(key) or not isinstance(value, str) or "\x00" in value
            for key, value in env.items()
        )
    ):
        raise ValueError(
            "A candidate alternative must provide string argv tokens and env overrides"
        )


def _validate_constraint(constraint, question):
    if not isinstance(constraint, dict):
        raise TypeError("Each constraint must be an object")
    span = constraint.get("span")
    if (
        constraint.get("channel") not in {"argv", "env"}
        or not _text(constraint.get("target"))
        or not _text(constraint.get("operator"))
        or not _strings(constraint.get("values"))
        or not isinstance(span, list)
        or len(span) != 2
        or any(type(offset) is not int for offset in span)
        or not 0 <= span[0] < span[1] <= len(question)
    ):
        raise ValueError("Invalid constraint annotation or question span")


def _validate(dataset, dataset_id):
    if not isinstance(dataset, dict) or not _text(dataset.get("version")):
        raise ValueError("Fixture must be an object with a nonempty version")
    mpml_sha = dataset.get("mpml_sha")
    if not isinstance(mpml_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", mpml_sha):
        raise ValueError("Fixture must pin a full MPML commit SHA")

    if dataset.get("fixture_id", DEFAULT_DATASET) != dataset_id:
        raise ValueError("Fixture ID does not match the selected dataset")
    if dataset_id != DEFAULT_DATASET:
        provenance = dataset.get("provenance")
        classification = "blinded_holdout" if dataset_id.startswith("holdout-") else "development"
        if not isinstance(provenance, dict) or provenance.get("classification") != classification:
            raise ValueError(f"Fixture provenance must declare classification {classification!r}")
        for key in ("author", "reviewer", "author_independence", "reviewer_independence"):
            if not _text(provenance.get(key)):
                raise ValueError(f"Fixture provenance requires nonempty {key}")
        if provenance["author"].strip().casefold() == provenance["reviewer"].strip().casefold():
            raise ValueError("A fixture requires a separate reviewer")
        for key in ("source_bundle_sha256", "spec_sha256"):
            digest = provenance.get(key)
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise ValueError(f"Fixture provenance requires a valid {key}")

    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Fixture must provide a nonempty case list")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not _text(case.get("id")) or case["id"] in ids:
            raise ValueError("Case IDs must be nonempty and unique")
        ids.add(case["id"])
        question = case.get("question")
        if not _text(question) or len(question) > 4000:
            raise ValueError(f"Invalid question for case {case['id']}")
        alternatives = case.get("expected")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError(f"Case {case['id']} requires gold alternatives")
        constraints = case.get("constraints", [])
        if not isinstance(constraints, list):
            raise TypeError(f"Case {case['id']} constraints must be a list")
        if "human_adjudication" in case and not _text(case["human_adjudication"]):
            raise ValueError(f"Case {case['id']} human_adjudication must be nonempty text")
        try:
            for alternative in alternatives:
                _validate_gold(alternative)
            for constraint in constraints:
                _validate_constraint(constraint, question)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Case {case['id']}: {exc}") from exc


def read_dataset(dataset_id=DEFAULT_DATASET):
    if dataset_id == DEFAULT_DATASET:
        path = _BASELINE
    elif _VERSIONED_ID.fullmatch(dataset_id):
        path = _FIXTURES / f"{dataset_id}.json"
        if _FIXTURES.is_symlink():
            raise ValueError("Fixture directory must not use symlinks")
    else:
        raise ValueError("Dataset must be baseline-v1, holdout-vN or development-vN")
    if path.is_symlink():
        raise ValueError("Fixture files must not use symlinks")
    if not path.is_file():
        raise ValueError(f"No registered fixture file for {dataset_id}")
    raw = path.read_bytes()
    dataset = json.loads(raw)
    _validate(dataset, dataset_id)
    return dataset, hashlib.sha256(raw).hexdigest()
