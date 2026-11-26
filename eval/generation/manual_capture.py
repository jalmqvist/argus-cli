"""Capture the manual holdout arms and prepare a blinded, ungraded review packet."""

import argparse
import fcntl
import hashlib
import hmac
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path

from . import baseline
from .datasets import read_dataset

_ARCHIVE = (
    Path(__file__).resolve().parents[2] / "docs/evaluation/M4C_2B_HOLDOUT_V1_PROVISIONAL.json"
)
_ARCHIVE_SHA256 = "c7f920cd3d01b90cdbdd9ad11b9102708d9d1575a10dbcd6b8180f48020fd247"
_HOLDOUT_SHA256 = "1e4fc365bc907e5d3aeb2af4c8e8aeeb489e1b592451e9fbbf3e9ccb4a94974e"
_DATASET_ID = "holdout-v1-manual"
_LOCAL = baseline.REPORTS / "manual"
_WORKFLOWS = ("single-pass", "agent")
_LABELS = ("Response A", "Response B")
_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}")

_WORKFLOW_TERMS = re.compile(
    r"m4-langgraph-v\d+|--agent\b|\b(?:langgraph|m[34](?:\s+(?:agent|single-pass))?"
    r"|single[- ]pass(?: workflow)?|agent(?: workflow)?)\b",
    re.IGNORECASE,
)
_NEUTRAL_UNCERTAINTY = {
    "The request is outside deterministic intent coverage.": "The response could not establish a supported interpretation of the request.",
    "An explicit requirement is outside the supported patterns.": "The response could not establish a supported interpretation of an explicit requirement.",
}
_CAPTURE_ERRORS = {"timeout", "cli_error", "invalid_report"}


def load_questions():
    raw = _ARCHIVE.read_bytes()
    fingerprint = baseline.sha(raw)
    if fingerprint != _ARCHIVE_SHA256:
        raise ValueError("Archived question source has changed")
    archive = json.loads(raw)
    holdout, holdout_hash = read_dataset("holdout-v1")
    if holdout_hash != _HOLDOUT_SHA256:
        raise ValueError("Registered holdout fixture has changed")
    if (
        archive["fixture_id"] != holdout["fixture_id"]
        or archive["mpml_sha"] != holdout["mpml_sha"]
        or archive["provenance"]["spec_sha256"] != holdout["provenance"]["spec_sha256"]
        or archive["cases"] != holdout["cases"]
    ):
        raise ValueError("Archived scored cases or source do not match the frozen holdout")

    manual = [{key: item[key] for key in ("id", "question")} for item in archive["manual_only"]]
    machine_ids = {item["id"] for item in holdout["cases"]}
    manual_ids = {item["id"] for item in manual}
    if (
        len(manual) != 14
        or len(manual_ids) != 14
        or len(machine_ids) != 12
        or machine_ids & manual_ids
        or machine_ids | manual_ids != {f"q{number:03d}" for number in range(1, 27)}
        or any(
            not isinstance(item["question"], str) or not item["question"].strip() for item in manual
        )
    ):
        raise ValueError("Manual and scored IDs must partition the original 26 questions")
    dataset = {
        "fixture_id": _DATASET_ID,
        "version": "mpml-holdout-v1-manual",
        "mpml_sha": holdout["mpml_sha"],
        "provenance": holdout["provenance"],
        "cases": manual,
    }
    return dataset, fingerprint


def capture_status(run, dataset, fingerprint):
    manifest = run["manifest"]
    cases = {item["id"]: item["question"] for item in dataset["cases"]}
    attempts = run["attempts"]
    source = manifest["source"]
    if (
        run["format"] != baseline.FORMAT
        or manifest["dataset_id"] != dataset["fixture_id"]
        or manifest["dataset_version"] != dataset["version"]
        or manifest["dataset_sha256"] != fingerprint
        or manifest["holdout_sha256"] != _HOLDOUT_SHA256
        or source["git_sha"] != dataset["mpml_sha"]
        or source["dirty"]
        or source["spec_sha256"] != dataset["provenance"]["spec_sha256"]
        or manifest["selected"] != list(cases)
        or not attempts.keys() <= cases.keys()
    ):
        raise ValueError("Saved capture does not match the frozen manual question source")
    for key, attempt in attempts.items():
        report = attempt["report"]
        if attempt["question"] != cases[key] or (
            report is not None and report.get("question") != cases[key]
        ):
            raise ValueError(f"Saved question does not match the archive for {key}")
        baseline.verify_attempt(attempt, manifest)
    remaining = [key for key in cases if key not in attempts]
    return {
        "status": "partial" if remaining else "complete",
        "captured": len(attempts),
        "total": len(cases),
        "remaining": remaining,
    }


def _capture_manifest(args, dataset, fingerprint):
    selected = [item["id"] for item in dataset["cases"]]
    manifest = baseline.live_manifest(args, dataset, fingerprint, selected)
    manifest["holdout_sha256"] = _HOLDOUT_SHA256
    manifest["argus"]["implementation_hashes"][str(Path(__file__))] = baseline.sha(
        Path(__file__).read_bytes()
    )
    return manifest


def _neutral(text):
    if not isinstance(text, str):
        return text
    return _WORKFLOW_TERMS.sub("the workflow", _NEUTRAL_UNCERTAINTY.get(text, text))


def _project(attempt):
    report = attempt["report"]
    if report is None:
        category = attempt["error_category"]
        return {
            "response_available": False,
            "capture_error": category if category in _CAPTURE_ERRORS else "unavailable",
        }
    preflight = report.get("preflight")
    evidence = None
    if isinstance(preflight, dict) and isinstance(preflight.get("issues"), list):
        evidence = {
            "issues": [
                {
                    key: _neutral(item[key])
                    for key in ("code", "severity", "source", "message")
                    if isinstance(item.get(key), str)
                }
                for item in preflight["issues"]
                if isinstance(item, dict)
            ],
        }
    return {
        "response_available": True,
        "verification": report["verification"],
        "argv": report["argv"],
        "env": report["env"],
        "explanation": _neutral(report.get("explanation")),
        "uncertainty": [_neutral(text) for text in report.get("uncertainty", [])],
        "citations": [
            {
                key: _neutral(item[key])
                for key in ("repo", "path", "heading", "git_sha")
                if isinstance(item.get(key), str)
            }
            for item in report["citations"]
        ],
        "preflight_validation": report["preflight_validation"],
        "preflight": evidence,
        "preflight_exit_code": report.get("preflight_exit_code"),
        "manual_command_available": report["command"] is not None,
    }


def _assignment(seed, cases):
    mapping = {}
    for item in cases:
        first = hmac.digest(seed, item["id"].encode("utf-8"), hashlib.sha256)[0] & 1
        mapping[item["id"]] = dict(
            zip(_LABELS, (_WORKFLOWS[first], _WORKFLOWS[1 - first]), strict=True)
        )
    return mapping


def _matched_pair(single, agent):
    first, second = single["manifest"], agent["manifest"]
    if (baseline.workflow(first), baseline.workflow(second)) != _WORKFLOWS:
        raise ValueError("Supply a single-pass capture followed by an agent capture")
    keys = (
        "dataset_id",
        "dataset_sha256",
        "selected",
        "source",
        "holdout_sha256",
        "index_sha256",
        "model",
        "settings",
        "retrieval",
        "config_sha256",
        "environment_sha256",
        "machine",
        "python",
        "dependencies",
        "ollama_version",
        "wall_timeout_seconds",
    )
    differences = [key for key in keys if first[key] != second[key]]
    for key in ("git_sha", "implementation_hashes"):
        if first["argus"][key] != second["argus"][key]:
            differences.append(f"argus.{key}")
    if differences:
        raise ValueError("Capture provenance differs: " + ", ".join(differences))


def create_packet(single_path, agent_path, packet_id, dataset, fingerprint):
    captured = {}
    report_hashes = {}
    for workflow, path in zip(_WORKFLOWS, (single_path, agent_path), strict=True):
        raw = path.read_bytes()
        run = json.loads(raw)
        if capture_status(run, dataset, fingerprint)["status"] != "complete":
            raise ValueError("Review packet requires both complete captures")
        captured[workflow] = run
        report_hashes[workflow] = baseline.sha(raw)
    _matched_pair(*captured.values())

    key_path = _LOCAL / "keys" / f"{packet_id}.json"
    packet_path = _LOCAL / "packets" / packet_id / "review.json"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    binding = {"question_source_sha256": fingerprint, "report_sha256": report_hashes}
    with key_path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another process is preparing this review packet") from exc
        if key_path.exists():
            key = json.loads(key_path.read_bytes())
            if key["binding"] != binding:
                raise ValueError(
                    "Review key belongs to different captured bytes; use a new packet ID"
                )
            seed = bytes.fromhex(key["seed"])
        else:
            seed = secrets.token_bytes(32)
            key = {
                "binding": binding,
                "seed": seed.hex(),
                "assignment": _assignment(seed, dataset["cases"]),
            }
            baseline.write_json(key_path, key)
        assignment = _assignment(seed, dataset["cases"])
        if assignment != key["assignment"]:
            raise ValueError("Review key does not match its recorded assignment")

        packet = {
            "cases": [
                {
                    "id": item["id"],
                    "question": item["question"],
                    "responses": {
                        label: _project(captured[workflow]["attempts"][item["id"]])
                        for label, workflow in assignment[item["id"]].items()
                    },
                }
                for item in dataset["cases"]
            ]
        }
        baseline.write_json(packet_path, packet)
    return packet_path, key_path


def _safe_name(value):
    if not _NAME.fullmatch(value):
        raise argparse.ArgumentTypeError("Use 1–80 letters, digits, dashes or underscores")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    run = sub.add_parser("run", help="Capture or resume one workflow for all 14 questions")
    run.add_argument("run_id", type=_safe_name)
    run.add_argument("--workflow", choices=_WORKFLOWS, required=True)
    run.add_argument("--model", default="qwen2.5-coder:7b")
    run.add_argument("--retrieval", choices=("hybrid", "lexical"), default="hybrid")
    run.add_argument("--config", type=Path, default=Path("sources.yaml"))
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--timeout", type=float, default=300.0)
    run.add_argument("--wall-timeout", type=float, default=1200.0)
    packet = sub.add_parser("packet", help="Build or regenerate a blinded packet offline")
    packet.add_argument("single_pass_run_id", type=_safe_name)
    packet.add_argument("agent_run_id", type=_safe_name)
    packet.add_argument("packet_id", type=_safe_name)
    args = parser.parse_args(argv)

    def report_path(run_id):
        return _LOCAL / "runs" / f"{run_id}.json"

    try:
        dataset, fingerprint = load_questions()
        if args.operation == "run":
            if not (
                args.model.strip()
                and 0 <= args.temperature <= 2
                and args.seed >= 0
                and 0 < args.timeout <= 600
                and 0 < args.wall_timeout <= 1200
            ):
                run.error("invalid model, generation settings, or wall timeout")
            manifest = _capture_manifest(args, dataset, fingerprint)
            summary = baseline.resume_run(
                report_path(args.run_id),
                manifest,
                dataset,
                fingerprint,
                baseline.live_attempt,
                summarize_run=capture_status,
            )
        else:
            review, key = create_packet(
                report_path(args.single_pass_run_id),
                report_path(args.agent_run_id),
                args.packet_id,
                dataset,
                fingerprint,
            )
            summary = {"review_packet": str(review), "private_key": str(key)}
        print(json.dumps(summary, indent=2))
        return 0
    except KeyboardInterrupt:
        print(
            "Interrupted. Saved attempts can be resumed with the same run command.", file=sys.stderr
        )
        return 130
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Manual capture failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
