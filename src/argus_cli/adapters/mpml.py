"""Restricted, read-only calls into MPML's published interfaces."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from argus_cli.config import Source


class BridgeError(RuntimeError):
    pass

@dataclass(frozen=True)
class BridgeResult:
    exit_code: int
    document: dict[str,Any]
    stderr: str

def _invoke(source: Source, module: str, argv: list[str], *, overrides: dict[str,str] | None=None, timeout: int=90) -> BridgeResult:
    if source.adapter != "mpml_v1":
        raise BridgeError(f"Unsupported adapter: {source.adapter}")
    if (source.spec_module, source.preflight_module) != ("mpml.spec", "mpml.preflight"):
        raise BridgeError("MPML v1 requires mpml.spec and mpml.preflight")
    if not all(isinstance(x,str) for x in argv):
        raise BridgeError("argv must be a list of strings")
    if overrides and not all(isinstance(k,str) and isinstance(v,str) for k,v in overrides.items()):
        raise BridgeError("Environment overrides must be strings")
    env=os.environ.copy()
    env.update(overrides or {})
    # A target venv is always used. The MPML repo root is the working directory for matching semantics.
    try:
        proc=subprocess.run([str(source.python),"-m",module,*argv],cwd=source.root,
            env=env,text=True,capture_output=True,check=False,shell=False,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise BridgeError(f"MPML interface invocation failed: {exc}") from exc
    try:
        document=json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"MPML did not produce a single JSON document (exit={proc.returncode}); stderr={proc.stderr[:300]}") from exc
    if not isinstance(document,dict) or document.get("schema_version") != 1:
        raise BridgeError("MPML returned unsupported JSON schema")
    return BridgeResult(proc.returncode,document,proc.stderr)

def spec(source: Source) -> BridgeResult:
    result=_invoke(source,source.spec_module,[])
    if result.exit_code:
        raise BridgeError(f"MPML spec failed (exit {result.exit_code}): {result.stderr[:300]}")
    return result

def preflight(source: Source,argv:list[str],*,overrides:dict[str,str]|None=None)->BridgeResult:
    return _invoke(source,source.preflight_module,argv,overrides=overrides)


def preflight_verification(result: BridgeResult) -> str:
    """Classify MPML diagnostics without changing its response."""
    issues = result.document.get("issues")
    if not isinstance(issues, list) or not all(
        isinstance(issue, dict)
        and issue.get("severity") in ("error", "warning")
        and all(isinstance(issue.get(key), str) for key in ("code", "source", "message"))
        for issue in issues
    ):
        raise BridgeError("MPML returned malformed preflight diagnostics")
    if any(issue["severity"] == "error" for issue in issues):
        return "rejected"
    if result.exit_code != 0:
        return "unverified"
    return "validated_with_warnings" if issues else "validated"
