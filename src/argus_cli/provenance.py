"""Identify and record the inspected revision; no git mutations."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Revision:
    sha: str
    dirty: bool

def revision(repo:Path)->Revision:
    def git(*args:str)->str:
        return subprocess.run(["git","-C",str(repo),*args],check=True,
            text=True,capture_output=True,timeout=15).stdout.strip()
    return Revision(sha=git("rev-parse","HEAD"),dirty=bool(git("status","--porcelain")))
