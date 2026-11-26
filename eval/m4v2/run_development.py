"""Run the pinned v2 first-attempt development cases locally, in sequence."""

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from argus_cli.config import load_sources
from argus_cli.generation import GenerationSettings
from argus_cli.ollama import EmbeddingError, model_digest
from argus_cli.provenance import revision
from argus_cli.v2_intent import Vocabulary, _candidate_values
from argus_cli.v2_live_validation import _SOURCE_ERRORS, _setting_support, _snapshot
from argus_cli.v2_workflow import FirstProposal, run

FIXTURE = Path(__file__).with_name("first-attempt-development-v1.json")
ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen2.5-coder:7b"
_ARG = re.compile(r"--(?:strategy|phaseaware-tf|phaseaware-mr|experiment-seed|experiment-variant)")
_ENV = {
    "EXPERIMENT_SEED": re.compile(r"[+-]?[0-9]{1,10}"),
    "EXPERIMENT_VARIANT": re.compile(r"[A-Z]"),
    "ACTIVE_PAIRS": re.compile(r"[A-Z]{6}(?:\s*,\s*[A-Z]{6}){0,8}"),
}
_ARG_VALUE = {
    "--strategy": re.compile(r"(?:MR|TF)[0-9]{1,3}"),
    "--phaseaware-tf": re.compile(r"(?:MR|TF)[0-9]{1,3}"),
    "--phaseaware-mr": re.compile(r"(?:MR|TF)[0-9]{1,3}"),
    "--experiment-seed": _ENV["EXPERIMENT_SEED"],
    "--experiment-variant": _ENV["EXPERIMENT_VARIANT"],
}


class DevelopmentError(RuntimeError):
    pass


def _sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


def private_directory(path: Path) -> Path:
    """Require a new directory outside Git worktrees, including this repository."""
    directory = path.parent.resolve(strict=True) / path.name
    if directory.is_relative_to(ROOT):
        raise DevelopmentError("Select a private directory outside the Argus checkout.")
    git = subprocess.run(
        ["git", "-C", str(directory.parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        env={
            **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
            "LC_ALL": "C",
        },
        check=False,
        text=True,
    )
    if git.returncode == 0:
        raise DevelopmentError("Select a private directory outside Git worktrees.")
    # Git exits 128 outside a worktree. Unexpected failures must not permit writes.
    if git.returncode != 128 or "not a git repository" not in git.stderr:
        raise DevelopmentError("Could not verify the private output location.")
    directory.mkdir(mode=0o700, exist_ok=False)
    if directory.stat().st_mode & 0o077:
        raise DevelopmentError("Private output directory permissions are not restrictive.")
    return directory


def private_write(path: Path, content: str):
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise DevelopmentError("Private output directory permissions are not restrictive.")
        descriptor = os.open(path.name, flags, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    finally:
        os.close(directory)


def _private_json(path, value):
    private_write(path, json.dumps(value, indent=2, allow_nan=False) + "\n")


def candidate_record(proposal: FirstProposal) -> dict:
    """Keep exact tokens for the fixture's limited setting vocabulary only."""
    argv = []
    pending = None
    for token in proposal.argv:
        flag, separator, inline = token.partition("=")
        if _ARG.fullmatch(flag):
            if separator:
                value = inline if _ARG_VALUE[flag].fullmatch(inline) else "[redacted]"
                argv.append(f"{flag}={value}")
            else:
                argv.append(flag)
            pending = None if separator else flag
        else:
            retain = pending is not None and _ARG_VALUE[pending].fullmatch(token)
            argv.append(token if retain else "[redacted]")
            pending = None
    return {
        "outcome": proposal.outcome,
        "argv": argv,
        "env": {
            key: value if _ENV[key].fullmatch(value) else "[redacted]"
            for key, value in proposal.env
            if key in _ENV
        },
        "omitted_env_keys": sum(key not in _ENV for key, _ in proposal.env),
        "uncertain": proposal.uncertain,
    }


def grade(case, proposal, values, issues, trace):
    expected = case["expected"]
    proposal_policy = expected.get("proposal")
    if proposal is None:
        if proposal_policy == "not_applicable" and not trace.get("generation_attempted"):
            return {"outcome": "not_applicable"}
        return {"outcome": "needs_manual_review", "reason": "no_structured_proposal"}
    if proposal_policy == "not_applicable":
        return {
            "outcome": "incorrect"
            if proposal.outcome == "recipe" or proposal.argv or proposal.env
            else "not_applicable"
        }
    if proposal.outcome != "recipe":
        outcome = (
            "incorrect"
            if proposal.argv or proposal.env or trace.get("candidate_outcome") == "invalid"
            else "needs_manual_review"
        )
        return {"outcome": outcome, "reason": "model_abstention"}
    alternatives = expected.get("alternatives")
    if not alternatives:
        return {"outcome": "needs_manual_review", "reason": "no_mechanical_expectation"}
    # Match the whole mapping, including the channel and the ordered values of repeated flags.
    exact = any(values == alternative for alternative in alternatives)
    if exact and proposal_policy == "invalid_exact":
        if issues or trace.get("preflight_outcome") == "rejected":
            return {"outcome": "exact_invalid_request", "structural_issues": len(issues)}
        return {"outcome": "needs_manual_review", "reason": "expected_invalid_value_not_rejected"}
    if exact and not issues:
        return {"outcome": "correct"}
    closest = min(
        alternatives,
        key=lambda option: sum(
            values.get(key) != option.get(key) for key in values.keys() | option.keys()
        ),
    )
    return {
        "outcome": "incorrect",
        "missing": sorted(closest.keys() - values.keys()),
        "mismatched": sorted(
            key for key in closest.keys() & values.keys() if closest[key] != values[key]
        ),
        "extra_settings": len(values.keys() - closest.keys()),
        "structural_issues": len(issues),
    }


def evidence_audit(case, proposal, index, metadata, spec, values):
    vocab = Vocabulary.from_spec(spec)
    all_ids = tuple(chunk["id"] for chunk in index["chunks"])
    support = {
        stage: dict(_setting_support(index, metadata, spec, case["question"], values, selected)[1])
        for stage, selected in (
            ("index", all_ids),
            ("retrieved", proposal.retrieved_ids),
            ("cited", proposal.cited_ids),
        )
    }
    targets = {}
    relevant = set()
    for key in values:
        if key in vocab.flags:
            heading = "arguments / " + ", ".join(vocab.flags[key]["flags"])
        else:
            heading = "env / " + key
        ids = {
            chunk["id"]
            for chunk in index["chunks"]
            if chunk["citation"]["path"] == "mpml/spec.py"
            and chunk["citation"]["heading"] == heading
        }
        relevant.update(ids)
        targets[key] = {
            "records_in_index": len(ids),
            "records_retrieved": len(ids.intersection(proposal.retrieved_ids)),
            "records_cited": len(ids.intersection(proposal.cited_ids)),
            "index_record_ids": sorted(ids),
            "retrieved_record_ids": sorted(ids.intersection(proposal.retrieved_ids)),
            "cited_record_ids": sorted(ids.intersection(proposal.cited_ids)),
            "value_supported_in_index": key in support["index"],
            "value_supported_in_retrieval": key in support["retrieved"],
            "value_supported_in_citations": key in support["cited"],
        }
    return {
        "settings": targets,
        "resolved_citations": len(set(proposal.cited_ids)),
        "unresolved_citations": proposal.unresolved_citations,
        "no_citations": not (proposal.cited_ids or proposal.unresolved_citations),
        "citations_outside_setting_records": len(set(proposal.cited_ids) - relevant),
    }


def _percentiles(values):
    values = sorted(values)
    if not values:
        return None
    return {
        "count": len(values),
        "median_seconds": statistics.median(values),
        "p95_seconds": values[(95 * len(values) + 99) // 100 - 1],
    }


def _counts(records):
    return {
        "Candidate grades": dict(Counter(row["candidate_grade"]["outcome"] for row in records)),
        "Preflight outcomes": dict(
            Counter(row["workflow"]["preflight_outcome"] for row in records)
        ),
        "Released recipes": sum(row["workflow"]["recipe_released"] for row in records),
    }


def _latency(records):
    return {
        "End-to-end": _percentiles(row["wall_seconds"] for row in records),
        "Generation": _percentiles(
            row["workflow"]["generation_seconds"]
            for row in records
            if row["workflow"]["generation_seconds"] is not None
        ),
    }


def review_sheet(records):
    lines = [
        "# M4 v2 first-attempt development findings",
        "",
        "Developer-authored development data. Human ratings remain unresolved until reviewed.",
        "",
        "| Case | Candidate score | Answer status | Preflight | Factual answer | Overall usefulness |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in records:
        lines.append(
            f"| {row['id']} | {row['candidate_grade']['outcome']} | {row['answer_status']} | "
            f"{row['workflow']['preflight_outcome']} | unresolved | unresolved |"
        )
    lines.extend(("", "## Counts", ""))
    for name, tally in _counts(records).items():
        lines.append(f"- {name} — {tally}")
    lines.extend(("", "## Latency", ""))
    for label, stats in _latency(records).items():
        if stats:
            lines.append(
                f"- {label} ({stats['count']} cases) — median {stats['median_seconds']:.3f}s, "
                f"p95 {stats['p95_seconds']:.3f}s."
            )
        else:
            lines.append(f"- {label} — no recorded samples.")
    lines.extend(("", "## Review notes", ""))
    for row in records:
        lines.extend(
            (
                f"### {row['id']}",
                "",
                f"- Question — {row['question']}",
                f"- Expected answer — {row['expected_answer']}",
                f"- Delivered answer — {row['answer'] or 'No explanation recorded.'}",
                "- Factual correctness — unresolved.",
                "- Usefulness and unnecessary withholding — unresolved.",
                "",
            )
        )
    return "\n".join(lines) + "\n"


def benchmark(config: Path, output: Path, selected: list[str] | None = None):
    fixture_raw = FIXTURE.read_bytes()
    fixture = json.loads(fixture_raw)
    ids = [case["id"] for case in fixture["cases"]]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-z0-9-]+", key) for key in ids):
        raise DevelopmentError("Fixture case IDs must be unique and safe for local filenames.")
    cases = [case for case in fixture["cases"] if not selected or case["id"] in selected]
    if selected and set(selected) != {case["id"] for case in cases}:
        raise DevelopmentError("Unknown case ID.")
    directory = private_directory(output)
    source = load_sources(config)["mpml"]
    snapshot, index, metadata = _snapshot(source)
    identity = snapshot.identity
    if identity.source_dirty or (identity.source_revision, identity.spec_sha256) != (
        fixture["mpml_sha"],
        fixture["spec_sha256"],
    ):
        raise DevelopmentError(
            "The evaluation requires the fixture's pinned clean MPML specification."
        )
    spec = snapshot.read_spec()
    settings = GenerationSettings()
    digest = model_digest(MODEL)
    inherited = dict(os.environ)
    if any(row["name"] in inherited for row in spec["env"]):
        raise DevelopmentError("Unset inherited MPML launch variables before evaluation.")
    argus = revision(ROOT)
    manifest = {
        "format": 1,
        "fixture": fixture["version"],
        "fixture_sha256": _sha(fixture_raw),
        "case_ids": [case["id"] for case in cases],
        "full_fixture": len(cases) == len(fixture["cases"]),
        "argus_revision": asdict(argus),
        "source": asdict(identity),
        "model": MODEL,
        "model_digest": digest,
        "settings": asdict(settings),
        "retrieval": "lexical",
        "config_sha256": _sha(config.read_bytes()),
        "python": platform.python_version(),
        "dependencies": {
            name: version(name) for name in ("langchain-ollama", "ollama", "pydantic")
        },
        "inherited_mpml_environment": "published_keys_unset",
        "platform": platform.platform(),
        "implementation_sha256": {
            str(path.relative_to(ROOT)): _sha(path.read_bytes())
            for path in [*sorted((ROOT / "src/argus_cli").rglob("*.py")), Path(__file__).resolve()]
        },
    }
    _private_json(directory / "manifest.json", manifest)
    records = []
    for case in cases:
        capture = []

        def inspect(proposal, target=directory / f"candidate-{case['id']}.json", captured=capture):
            _private_json(target, candidate_record(proposal))
            captured.append(proposal)

        start = time.monotonic()
        public, code = run(
            source, case["question"], model=MODEL, settings=settings, inspect_first_proposal=inspect
        )
        elapsed = time.monotonic() - start
        trace = public["workflow"]
        if (
            trace["model_calls"] > 1
            or public["command"] is not None
            or public["settings"] is not None
            or trace["recipe_released"]
        ):
            raise DevelopmentError("The first-attempt or no-release invariant failed.")
        if (
            _snapshot(source)[0].identity != identity
            or dict(os.environ) != inherited
            or trace["model_digest"] not in (None, digest)
        ):
            raise DevelopmentError("Source, index, model or inherited environment changed.")
        proposal = capture[0] if capture else None
        values, issues = (
            _candidate_values(proposal.argv, dict(proposal.env), Vocabulary.from_spec(spec))
            if proposal
            else ({}, [])
        )
        records.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "source": asdict(identity),
                "model": MODEL,
                "expected_model_digest": digest,
                "exit_code": code,
                "wall_seconds": round(elapsed, 6),
                "candidate_grade": grade(case, proposal, values, issues, trace),
                "evidence": evidence_audit(case, proposal, index, metadata, spec, values)
                if proposal
                else None,
                "workflow": trace,
                "answer_status": public["answer_status"],
                "answer": public["explanation"],
                "expected_answer": case["expected"]["answer"],
                "factual_answer_review": "unresolved",
                "usefulness_review": "unresolved",
                "unnecessary_withholding_review": "unresolved",
            }
        )
    if model_digest(MODEL) != digest:
        raise DevelopmentError("Model digest changed during evaluation.")
    _private_json(
        directory / "results.json",
        {
            "complete": True,
            "full_fixture": manifest["full_fixture"],
            "latency": _latency(records),
            "counts": _counts(records),
            "cases": records,
        },
    )
    private_write(directory / "findings.md", review_sheet(records))
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("sources.yaml"))
    parser.add_argument(
        "--output", type=Path, required=True, help="New directory outside Git worktrees"
    )
    parser.add_argument("--case", action="append", help="Repeat to select specific fixture IDs")
    args = parser.parse_args(argv)
    try:
        output = benchmark(args.config, args.output, args.case)
    except DevelopmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (*_SOURCE_ERRORS, EmbeddingError, RuntimeError):
        print(
            "Evaluation stopped. Check the local configuration, permissions, and services.",
            file=sys.stderr,
        )
        return 2
    print(f"Saved local development artifacts to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
