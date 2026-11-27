"""Identify and record the inspected revision; no git mutations."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Revision:
    sha: str
    dirty: bool


def revision(repo: Path) -> Revision:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, timeout=15
        ).stdout.strip()

    return Revision(sha=git("rev-parse", "HEAD"), dirty=bool(git("status", "--porcelain")))


def spec_sha256(document: dict) -> str:
    """Hash the canonical representation used by MPML's published schema v1."""
    canonical = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
