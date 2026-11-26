"""Run or score the frozen MPML generation baseline from the Argus repository root."""

import argparse
import fcntl
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .datasets import DEFAULT_DATASET, read_dataset
from .paired import compare, summarize, workflow

REPORTS = Path("reports/local/generation")
INDEX = Path("indexes/mpml.json")
FORMAT = 1


def sha(data):
    return hashlib.sha256(data).hexdigest()


def live_manifest(args, dataset, dataset_hash, selected):
    # Imported only for runs. Offline scoring needs neither Argus dependencies nor Ollama.
    from argus_cli import ask, ollama, retrieval
    from argus_cli.config import load_sources
    from argus_cli.generation import GenerationSettings
    from argus_cli.provenance import revision

    config = args.config.resolve()
    config_hash = sha(config.read_bytes())
    index_raw = INDEX.read_bytes()
    index = json.loads(index_raw)
    source = load_sources(config)["mpml"]
    # Validate the same index and source with the existing M2 code without calling embeddings.
    _, metadata, spec = retrieval.retrieve_context(source, "benchmark", "lexical", 1)
    if metadata["git_sha"] != dataset["mpml_sha"] or metadata["dirty"]:
        raise ValueError("The frozen fixture requires its pinned, clean MPML checkout")
    fixture_provenance = dataset.get("provenance")
    if fixture_provenance and metadata["spec_sha256"] != fixture_provenance["spec_sha256"]:
        raise ValueError("The live specification hash differs from the frozen fixture")
    inherited = sorted({item["name"] for item in spec["env"]} & os.environ.keys())
    if inherited:
        raise ValueError("Unset inherited MPML environment variables: " + ", ".join(inherited))

    embeddings = index["embeddings"]
    embedding = (
        None
        if embeddings is None
        else {"model": embeddings["model"], "digest": embeddings["digest"]}
    )
    if args.retrieval == "hybrid" and (
        embedding is None or ollama.model_digest(embedding["model"]) != embedding["digest"]
    ):
        raise ValueError("Hybrid requires a current embedding index")
    model_digest = ollama.model_digest(args.model)
    model_info = ollama._request("show", {"model": args.model})
    if model_info.get("remote_host") or model_info.get("remote_model"):
        raise ValueError("The benchmark requires a local Ollama model")

    argus_dir = Path(ask.__file__).parent
    implementation_files = sorted(argus_dir.rglob("*.py")) + [
        Path(__file__),
        Path(__file__).with_name("timed_ask.py"),
        Path(__file__).with_name("paired.py"),
        Path(__file__).with_name("datasets.py"),
        Path(__file__).with_name("scoring.py"),
    ]
    argus_revision = revision(Path.cwd())
    # Hash the inherited environment without recording its values. Shell bookkeeping
    # entries may differ across otherwise equivalent invocations.
    environment = {
        key: val for key, val in os.environ.items() if key not in {"_", "SHLVL", "OLDPWD"}
    }
    selected_workflow = getattr(args, "workflow", "single-pass")
    agent = {}
    if selected_workflow == "agent":
        from argus_cli.agent import MAX_CALLS

        try:
            graph_version = version("langgraph")
        except PackageNotFoundError as exc:
            raise ValueError("Agent benchmark requires 'argus-cli[llm,agent]'") from exc
        agent = {
            "agent": {
                "workflow_id": "m4-langgraph-v1",
                "langgraph_version": graph_version,
                "max_reserved_calls": MAX_CALLS,
                "repair_policy": "m4-langgraph-v1 bounded diagnostic repair",
            }
        }
    return {
        "workflow": selected_workflow,
        **agent,
        "machine": {"platform": platform.platform(), "cpu_count": os.cpu_count()},
        "dataset_id": dataset.get("fixture_id", DEFAULT_DATASET),
        "dataset_version": dataset["version"],
        "dataset_sha256": dataset_hash,
        "selected": selected,
        "config": str(config),
        "config_sha256": config_hash,
        "index_sha256": sha(index_raw),
        "indexed_citations": {
            chunk["id"]: {"id": chunk["id"], **chunk["citation"]} for chunk in index["chunks"]
        },
        "source": metadata,
        "model": {"name": args.model, "digest": model_digest},
        "settings": asdict(
            GenerationSettings(
                temperature=args.temperature,
                seed=args.seed,
                timeout_seconds=args.timeout,
            )
        ),
        "retrieval": {
            "mode": args.retrieval,
            "limit": ask._RETRIEVAL_LIMIT,
            "embedding": embedding,
        },
        "wall_timeout_seconds": args.wall_timeout,
        "ollama_version": ollama._request("version")["version"],
        "argus": {
            "git_sha": argus_revision.sha,
            "dirty": argus_revision.dirty,
            "implementation_hashes": {
                str(path): sha(path.read_bytes()) for path in implementation_files
            },
        },
        "python": sys.version,
        "dependencies": {
            name: version(name)
            for name in (
                "langchain-ollama",
                "langchain-core",
                "ollama",
                "pydantic",
                "numpy",
                "rank-bm25",
            )
        },
        "environment_sha256": sha(json.dumps(environment, sort_keys=True).encode()),
    }


def attempt_case(case, config, manifest):
    settings = manifest["settings"]
    start = time.monotonic()
    result = {"report": None, "generation_seconds": None, "error_category": None, "exit_code": None}
    try:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "eval.generation.timed_ask",
                "--config",
                str(config),
                "ask",
                *(["--agent"] if workflow(manifest) == "agent" else []),
                "--model",
                manifest["model"]["name"],
                "--retrieval-mode",
                manifest["retrieval"]["mode"],
                "--temperature",
                str(settings["temperature"]),
                "--seed",
                str(settings["seed"]),
                "--timeout",
                str(settings["timeout_seconds"]),
                "--",
                case["question"],
            ],
            capture_output=True,
            text=True,
            timeout=manifest["wall_timeout_seconds"],
            check=False,
        )
        result["exit_code"] = process.returncode
        if not process.stdout:
            result.update(error_category="cli_error", error="Argus exited without a JSON report")
        else:
            captured = json.loads(process.stdout)
            report = captured["report"]
            for key in (
                "verification",
                "argv",
                "env",
                "command",
                "preflight",
                "structural_validation",
                "preflight_validation",
                "citations",
                "model",
                "provenance",
                "retrieval",
            ):
                if key not in report:
                    raise ValueError(f"Missing Argus report field {key!r}")
            latency = captured["generation_seconds"]
            if latency is not None and (
                type(latency) not in (int, float)
                or not 0 <= latency <= manifest["wall_timeout_seconds"]
            ):
                raise ValueError("Invalid generation duration")
            if (
                not isinstance(report["citations"], list)
                or not all(
                    isinstance(item, dict) and isinstance(item.get("id"), str)
                    for item in report["citations"]
                )
                or (report["preflight"] is not None and not isinstance(report["preflight"], dict))
                or (
                    report["argv"] is not None
                    and not (
                        isinstance(report["argv"], list)
                        and all(isinstance(x, str) for x in report["argv"])
                    )
                )
                or (
                    report["env"] is not None
                    and not (
                        isinstance(report["env"], dict)
                        and all(isinstance(x, str) for x in report["env"].values())
                    )
                )
            ):
                raise ValueError("Invalid Argus report field types")
            result.update(report=report, generation_seconds=latency)
    except subprocess.TimeoutExpired:
        result.update(error_category="timeout", error="Evaluation wall-clock timeout exceeded")
    except (KeyError, TypeError, ValueError) as exc:
        result.update(error_category="invalid_report", error=str(exc))
    except OSError as exc:
        result.update(error_category="cli_error", error=str(exc))
    result["wall_seconds"] = round(time.monotonic() - start, 4)
    return result


def live_attempt(case, config, manifest):
    from argus_cli import ollama

    def check_model():
        model = manifest["model"]
        if ollama.model_digest(model["name"]) != model["digest"]:
            raise ValueError("Generation model changed during the run")
        embedding = manifest["retrieval"]["embedding"]
        if manifest["retrieval"]["mode"] == "hybrid" and (
            ollama.model_digest(embedding["model"]) != embedding["digest"]
        ):
            raise ValueError("Embedding model changed during the run")

    check_model()
    result = attempt_case(case, config, manifest)
    check_model()
    return result


def verify_attempt(attempt, manifest):
    report = attempt["report"]
    if report is None:
        return
    error = report.get("error", "").lower()
    is_agent = workflow(manifest) == "agent"
    expected_workflow = manifest["agent"]["workflow_id"] if is_agent else None
    if report.get("workflow") != expected_workflow:
        raise ValueError("Argus reported a different workflow")
    if any(
        term in error
        for term in (
            "index is stale",
            "changed during",
            "model changed",
            "source or index changed",
            "identity changed",
        )
    ):
        raise ValueError("Argus detected source or model drift during the run")
    provenance = report["provenance"]
    if provenance is not None:
        if is_agent and provenance.get("index_sha256") != manifest["index_sha256"]:
            raise ValueError("Argus reported a different index fingerprint")
        if any(
            provenance[key] != manifest["source"][key]
            for key in ("git_sha", "dirty", "spec_sha256")
        ):
            raise ValueError("Argus reported a different MPML snapshot")
    model = report["model"]
    if model["name"] != manifest["model"]["name"] or (
        model["digest"] is not None and model["digest"] != manifest["model"]["digest"]
    ):
        raise ValueError("Argus reported a different generation model")
    if model["settings"] != manifest["settings"]:
        raise ValueError("Argus reported different generation settings")
    if any(report["retrieval"][k] != manifest["retrieval"][k] for k in ("mode", "limit")):
        raise ValueError("Argus reported a different retrieval configuration")


def save(path, run, dataset, dataset_hash, *, summarize_run=summarize):
    run["summary"] = summarize_run(run, dataset, dataset_hash)
    write_json(path, run)


def write_json(path, value):
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, encoding="utf-8", delete=False
    ) as temp:
        pending = Path(temp.name)
        try:
            json.dump(value, temp, indent=2, allow_nan=False)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
            temp.close()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)


def resume_run(
    path, manifest, dataset, dataset_hash, execute=attempt_case, *, summarize_run=summarize
):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another process is writing this run") from exc
        if path.exists():
            run = json.loads(path.read_bytes())
            if run["format"] != FORMAT or run["manifest"] != manifest:
                raise ValueError(
                    "Incompatible resume configuration or provenance; use a new run ID"
                )
            summarize_run(run, dataset, dataset_hash)
        else:
            run = {"format": FORMAT, "manifest": manifest, "attempts": {}}
            save(path, run, dataset, dataset_hash, summarize_run=summarize_run)

        cases = {case["id"]: case for case in dataset["cases"]}
        config = Path(manifest["config"])
        for key in manifest["selected"]:
            if key in run["attempts"]:
                continue
            if sha(INDEX.read_bytes()) != manifest["index_sha256"] or (
                sha(config.read_bytes()) != manifest["config_sha256"]
            ):
                raise ValueError("Index or source configuration changed during the run")
            print(f"Running {key}", file=sys.stderr)
            attempt = execute(cases[key], config, manifest)
            verify_attempt(attempt, manifest)
            if sha(INDEX.read_bytes()) != manifest["index_sha256"] or (
                sha(config.read_bytes()) != manifest["config_sha256"]
            ):
                raise ValueError("Index or source configuration changed during the run")
            run["attempts"][key] = {**attempt, "question": cases[key]["question"]}
            save(path, run, dataset, dataset_hash, summarize_run=summarize_run)
        return run["summary"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    run = sub.add_parser("run", help="Run or resume a local benchmark")
    score = sub.add_parser("score", help="Recompute scores from a saved run without Ollama")
    comparison = sub.add_parser(
        "compare", help="Compare completed single-pass and agent reports offline"
    )
    for command in (run, score, comparison):
        command.add_argument("run_id", help="Local report name (single-pass report for compare)")
        command.add_argument(
            "--dataset",
            default=DEFAULT_DATASET,
            help="Fixture ID: baseline-v1, holdout-vN or development-vN",
        )
    comparison.add_argument("agent_run_id", help="Completed agent report name")
    comparison.add_argument(
        "--allow-provenance-mismatch",
        action="store_true",
        help="Compare differing source snapshots, indexes or retrieval settings with explicit flags",
    )
    run.add_argument("--workflow", choices=("single-pass", "agent"), default="single-pass")
    run.add_argument(
        "--case", action="append", help="Select a case in the chosen dataset, repeatable"
    )
    run.add_argument("--model", default="qwen2.5-coder:7b")
    run.add_argument("--retrieval", choices=("hybrid", "lexical"), default="hybrid")
    run.add_argument("--config", type=Path, default=Path("sources.yaml"))
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--timeout", type=float, default=300.0)
    run.add_argument("--wall-timeout", type=float, default=660.0)
    args = parser.parse_args(argv)

    def report_path(run_id):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", run_id):
            parser.error("run ID must be 1–80 letters, digits, dashes, or underscores")
        return REPORTS / f"{run_id}.json"

    def read_report(path):
        saved = json.loads(path.read_bytes())
        if saved["format"] != FORMAT:
            raise ValueError("Unsupported report format")
        return saved

    path = report_path(args.run_id)
    try:
        dataset, dataset_hash = (
            read_dataset() if args.dataset == DEFAULT_DATASET else read_dataset(args.dataset)
        )
        if args.operation == "score":
            summary = summarize(read_report(path), dataset, dataset_hash)
        elif args.operation == "compare":
            summary = compare(
                read_report(path),
                read_report(report_path(args.agent_run_id)),
                dataset,
                dataset_hash,
                allow_provenance_mismatch=args.allow_provenance_mismatch,
            )
        else:
            if not (
                args.model.strip()
                and 0 <= args.temperature <= 2
                and args.seed >= 0
                and 0 < args.timeout <= 600
                and 0 < args.wall_timeout <= 1200
            ):
                run.error("invalid model, generation settings, or wall timeout")
            ids = [item["id"] for item in dataset["cases"]]
            unknown = set(args.case or ()) - set(ids)
            if unknown:
                raise ValueError(
                    "Unknown case IDs in the selected dataset: " + ", ".join(sorted(unknown))
                )
            selected = [key for key in ids if not args.case or key in args.case]
            manifest = live_manifest(args, dataset, dataset_hash, selected)
            summary = resume_run(path, manifest, dataset, dataset_hash, live_attempt)
        print(json.dumps(summary, indent=2))
        return 0
    except KeyboardInterrupt:
        print(f"Interrupted. Completed attempts are in {path}.", file=sys.stderr)
        return 130
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Generation benchmark failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
