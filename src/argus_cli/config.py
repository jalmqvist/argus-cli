"""Configuration is local; source repository contents never enter git artifacts."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import re
import yaml

_TOKEN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

class ConfigError(ValueError):
    pass

@dataclass(frozen=True)
class Source:
    name: str
    root: Path
    python: Path
    adapter: str
    spec_module: str
    preflight_module: str
    entrypoint: str
    documents: tuple[str, ...]

def _expand(value: str, env: dict[str,str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key=match.group(1)
        if not env.get(key):
            raise ConfigError(f"Required configuration variable {key} is unset")
        return env[key]
    return _TOKEN.sub(repl, value)

def load_sources(path: Path, *, env: dict[str,str] | None = None, verify: bool = True) -> dict[str, Source]:
    env = dict(os.environ if env is None else env)
    if not path.is_file():
        raise ConfigError(f"Missing configuration file: {path}")
    raw=yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw,dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("sources"),dict):
        raise ConfigError("sources.yaml requires schema_version: 1 and a sources mapping")
    result={}
    for name, details in raw["sources"].items():
        if not isinstance(details,dict):
            raise ConfigError(f"Invalid source: {name}")
        required=("root","python","adapter","spec_module","preflight_module","entrypoint","documents")
        missing=[key for key in required if key not in details]
        if missing:
            raise ConfigError(f"Source {name}: missing {', '.join(missing)}")
        root=Path(_expand(str(details["root"]),env)).expanduser()
        python=Path(_expand(str(details["python"]),env)).expanduser()
        if not root.is_absolute() or not python.is_absolute():
            raise ConfigError(f"Source {name}: root and python must be absolute paths")
        if verify:
            if not root.is_dir(): raise ConfigError(f"Source {name}: root not found: {root}")
            if not python.is_file(): raise ConfigError(f"Source {name}: interpreter not found: {python}")
        documents=details["documents"]
        if not isinstance(documents,list) or not all(isinstance(x,str) for x in documents):
            raise ConfigError(f"Source {name}: documents must be a list of paths")
        result[name]=Source(name=name,root=root,python=python,adapter=str(details["adapter"]),
            spec_module=str(details["spec_module"]),preflight_module=str(details["preflight_module"]),
            entrypoint=str(details["entrypoint"]),documents=tuple(documents))
    if not result: raise ConfigError("No sources configured")
    return result
