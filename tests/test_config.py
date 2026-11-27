from pathlib import Path

import pytest

from argus_cli.config import ConfigError, load_sources


def test_unset_env_is_actionable(tmp_path: Path) -> None:
    p = tmp_path / "sources.yaml"
    p.write_text(
        "schema_version: 1\nsources:\n  mpml:\n    root: ${MPML_REPO}\n    python: /usr/bin/python3\n    adapter: mpml_v1\n    spec_module: mpml.spec\n    preflight_module: mpml.preflight\n    entrypoint: main.py\n    documents: []\n"
    )
    with pytest.raises(ConfigError, match="MPML_REPO"):
        load_sources(p, env={}, verify=False)


def test_explicit_source(tmp_path: Path) -> None:
    p = tmp_path / "sources.yaml"
    p.write_text(
        f"schema_version: 1\nsources:\n  mpml:\n    root: {tmp_path}\n    python: /usr/bin/python3\n    adapter: mpml_v1\n    spec_module: mpml.spec\n    preflight_module: mpml.preflight\n    entrypoint: main.py\n    documents: []\n"
    )
    source = load_sources(p, env={}, verify=False)["mpml"]
    assert source.root == tmp_path
