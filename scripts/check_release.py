"""Inspect Argus distributions and smoke-test fresh installs against synthetic MPML."""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
DIST_INFO = f"argus_cli-{VERSION}.dist-info"
METADATA = {"METADATA", "WHEEL", "entry_points.txt", "RECORD"}
SDIST_ROOT = f"argus_cli-{VERSION}"
SDIST_FILES = {".gitignore", "README.md", "pyproject.toml", "PKG-INFO"}


def command(*args, cwd, env=None):
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout


def inspect_artifacts(wheel, sdist):
    """Allow only tracked package source and the expected public distribution metadata."""
    packages = {
        path.relative_to(ROOT / "src").as_posix() for path in (ROOT / "src/argus_cli").rglob("*.py")
    }
    expected_wheel = packages | {f"{DIST_INFO}/{item}" for item in METADATA}
    expected_sdist = {
        f"{SDIST_ROOT}/{item}" for item in SDIST_FILES | {f"src/{path}" for path in packages}
    }
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        if set(members) != expected_wheel or len(members) != len(expected_wheel):
            raise RuntimeError(
                f"Unexpected wheel contents: {sorted(set(members) ^ expected_wheel)}"
            )
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        files = {item.name for item in members}
        if (
            not all(item.isfile() for item in members)
            or files != expected_sdist
            or len(members) != len(expected_sdist)
        ):
            raise RuntimeError(f"Unexpected sdist contents: {sorted(files ^ expected_sdist)}")
    return len(expected_wheel), len(expected_sdist)


def synthetic_source(workdir, python):
    source = workdir / "synthetic-mpml"
    module = source / "mpml"
    module.mkdir(parents=True)
    (module / "__init__.py").touch()
    spec = {
        "schema_version": 1,
        "arguments": [{"flags": ["--experiment-seed"], "dest": "experiment_seed"}],
        "env": [
            {
                "name": "EXPERIMENT_SEED",
                "default": 42,
                "scope": "launch_selector",
                "timing": "import",
                "semantics": "The fallback seed is 42.",
            }
        ],
        "precedence": [
            {"setting": "experiment_seed", "order": ["--experiment-seed", "EXPERIMENT_SEED", "42"]}
        ],
        "rules": [],
        "registries": {},
        "source_edit_only": [],
    }
    (module / "spec.py").write_text("print(" + repr(json.dumps(spec)) + ")\n")
    (module / "preflight.py").write_text(
        "import sys\n"
        'assert sys.argv[1:] == ["--experiment-seed", "42"]\n'
        'print(\'{"schema_version": 1, "issues": []}\')\n'
    )
    command("git", "init", "--quiet", cwd=source)
    command("git", "add", "mpml", cwd=source)
    command(
        "git",
        "-c",
        "user.name=Argus smoke",
        "-c",
        "user.email=smoke@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "Synthetic source",
        cwd=source,
    )
    configuration = {
        "schema_version": 1,
        "sources": {
            "mpml": {
                "root": str(source),
                "python": str(python),
                "adapter": "mpml_v1",
                "spec_module": "mpml.spec",
                "preflight_module": "mpml.preflight",
                "entrypoint": "main.py",
                "documents": [],
            }
        },
    }
    # JSON is a valid YAML document and keeps this script stdlib-only.
    (workdir / "sources.yaml").write_text(json.dumps(configuration))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def smoke(artifact, workdir, *, llm):
    workdir.mkdir()
    environment = workdir / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    installed = environment / "bin/argus"
    requirement = f"argus-cli[llm] @ {artifact.as_uri()}" if llm else str(artifact)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(*args):
        return command(*args, cwd=workdir, env=env)

    run(
        python,
        "-m",
        "pip",
        "--disable-pip-version-check",
        "install",
        "--quiet",
        "--no-compile",
        "--no-cache-dir",
        requirement,
    )
    run(python, "-m", "pip", "check")
    installed_version = run(
        python,
        "-c",
        "from argus_cli import __version__; from importlib.metadata import version; "
        "assert __version__ == version('argus-cli'); print(__version__)",
    ).strip()
    require(installed_version == VERSION, "Installed package version does not match project")
    require(run(installed, "--version").strip() == f"argus {VERSION}", "Console version mismatch")
    require("preflight" in run(installed, "--help"), "Console help is missing preflight")
    run(
        python,
        "-c",
        "from importlib.util import find_spec; "
        f"assert (find_spec('langchain_ollama') is not None) == {llm!r}; "
        "assert find_spec('langgraph') is None",
    )

    synthetic_source(workdir, python)

    def call(*args):
        return json.loads(run(installed, *args))

    require(call("doctor")["dirty"] is False, "Synthetic source is dirty")
    require(call("spec")["schema_version"] == 1, "Spec invocation failed")
    require(call("inspect", "EXPERIMENT_SEED")["environment"]["default"] == 42, "Inspect failed")
    require(call("explain", "precedence")["details"][0]["order"][-1] == "42", "Explain failed")
    require(call("preflight", "--", "--experiment-seed", "42")["issues"] == [], "Preflight failed")
    call("index")
    results = call("retrieve", "EXPERIMENT_SEED")["results"]["lexical"]
    require(bool(results), "Lexical retrieval returned no hits")
    if llm:
        response = call("ask", "--agent-v2", "What is the default for EXPERIMENT_SEED?")
        require(
            response["answer_status"] == "grounded"
            and response["command"] is None
            and response["settings"] is None
            and response["workflow"]["model_calls"] == 0,
            "Installed v2 crossed the deterministic response boundary",
        )
    print(f"Fresh {'sdist + llm' if llm else 'core wheel'} installation smoke passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path, help="Directory containing the wheel and sdist")
    args = parser.parse_args()
    require(sys.version_info[:2] == (3, 12), "Run release acceptance with Python 3.12")
    dist = args.dist.resolve()
    wheel = dist / f"argus_cli-{VERSION}-py3-none-any.whl"
    sdist = dist / f"{SDIST_ROOT}.tar.gz"
    wheel_count, sdist_count = inspect_artifacts(wheel, sdist)
    print(
        f"Artifact contents passed: {wheel_count} wheel files, {sdist_count} sdist files.",
        flush=True,
    )
    for artifact, llm in ((wheel, False), (sdist, True)):
        with tempfile.TemporaryDirectory(prefix="argus-release-") as temporary:
            smoke(artifact, Path(temporary) / "install", llm=llm)


if __name__ == "__main__":
    main()
