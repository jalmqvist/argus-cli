# v0.1.0rc1 acceptance checklist

Record the exact merged Argus Git SHA and results before publication. Treat the
package checks and the real integration smoke as separate gates.

| Record | Tested value or evidence |
| --- | --- |
| Argus commit and worktree status | Pending merged candidate |
| Python, OS and dependency versions | Pending |
| Wheel and sdist SHA-256 | Pending merged candidate |
| MPML revision, dirty state, interpreter version | Pending maintainer run |
| MPML spec and lexical index SHA-256 | Pending maintainer run |
| Local Ollama version, model digest and hardware | Pending maintainer run |
| Reviewer, date and evidence location | Pending |

## Public checks with synthetic MPML

Run from a fresh checkout on Python 3.12. Dependency installation and isolated
builds may use a package index or an equivalent wheelhouse. The checks themselves
need no real MPML checkout, market data, Ollama service or GPU.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,llm,agent]' build
git rev-parse HEAD
git status --short
python --version
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
python scripts/check_release.py dist
sha256sum dist/argus_cli-0.1.0rc1*
git diff --check
```

- [ ] Complete test suite and v2 response-boundary tests pass. Record test count and CI link.
- [ ] Ruff lint and format checks and `git diff --check` pass.
- [ ] Wheel and sdist build and contain only declared package files and allowed distribution metadata. Record hashes.
- [ ] Core wheel installs in a fresh venv and passes version, help, doctor, spec,
  inspect, explain, lexical indexing/retrieval and synthetic preflight.
- [ ] Sdist with `[llm]` installs in a second fresh venv. Deterministic v2 returns
  a grounded answer with zero model calls and null command/settings. LangGraph
  is absent from both installed environments.

### Preparation PR evidence

Python 3.12.14 passed 502 tests, Ruff lint and format checks, and
`git diff --check`. The isolated build produced the wheel and sdist, each
with 26 allowed files. The core wheel and the sdist with `[llm]` passed the
installed synthetic smoke in separate fresh environments. Repeat the checks
at the merged candidate SHA and record its artifact hashes above.

## Maintainer-local read-only checks

These checks are unexecuted. Run them against the merged candidate using the
release-built wheel and the pinned MPML checkout
`14ad36e3f70a10bb5781b88200e825a717ca402f`. Review the trusted MPML
checkout and interpreter before invoking the bridge. Use a separate local smoke
directory so this run does not replace your existing index.

```sh
export ARGUS_CHECKOUT="$(pwd)"
export MPML_REPO=/absolute/path/to/market-phase-ml
export MPML_PYTHON=/absolute/path/to/market-phase-ml/.venv/bin/python
git -C "$MPML_REPO" rev-parse HEAD
git -C "$MPML_REPO" status --short
"$MPML_PYTHON" --version

smoke_dir="$(mktemp -d)"
python3.12 -m venv "$smoke_dir/venv"
. "$smoke_dir/venv/bin/activate"
python -m pip install "$ARGUS_CHECKOUT/dist/argus_cli-0.1.0rc1-py3-none-any.whl[llm]"
cd "$smoke_dir"
cp "$ARGUS_CHECKOUT/sources.yaml" .
argus --version
argus doctor > doctor.json
argus spec > spec.json
argus inspect EXPERIMENT_VARIANT > inspect.json
argus explain precedence > explain.json
argus index > index.json
argus retrieve 'What takes precedence over EXPERIMENT_VARIANT?' > retrieve.json
sha256sum indexes/mpml.json
argus preflight -- --strategy MR32 --experiment-seed 57 > preflight.json
argus ask --agent-v2 'What is the default for EXPERIMENT_SEED?' > deterministic.json

# With local Ollama running on loopback and qwen2.5-coder:7b installed:
ollama --version
ollama list
proposal_status=0
argus ask --agent-v2 'Use strategy MR32 with seed 57.' > proposal.json || proposal_status=$?
test "$proposal_status" -eq 1
```

Inspect the JSON and record statuses and timings. Exit 1 is expected for the
qualified proposal with its recipe withheld. A CLI or infrastructure failure
requires investigation before publication. Keep local files out of Git.

```sh
python - <<'PY'
import hashlib
import json
from pathlib import Path

def read(file):
    return json.loads(Path(file).read_text())

doctor, index = read("doctor.json"), read("index.json")
pinned = "14ad36e3f70a10bb5781b88200e825a717ca402f"
source = index["source"]
assert doctor["sha"] == source["git_sha"] == pinned
assert not doctor["dirty"] and not source["dirty"]
canonical = json.dumps(read("spec.json"), indent=2, sort_keys=True) + "\n"
spec_hash = hashlib.sha256(canonical.encode()).hexdigest()
assert spec_hash == source["spec_sha256"] == "fbe4e83ec7540f8cca9a539b9a769cf28aa6ebb2c731faff3681c2a52a6c346a"
index_hash = hashlib.sha256(Path("indexes/mpml.json").read_bytes()).hexdigest()
deterministic, proposal = read("deterministic.json"), read("proposal.json")
assert deterministic["answer_status"] == "grounded"
assert deterministic["workflow"]["model_calls"] == 0
assert proposal["answer_status"] == "limited" and proposal["workflow"]["answer_delivered"]
assert proposal["workflow"]["generation_attempted"]
assert proposal["workflow"]["model_calls"] == 1
assert proposal["workflow"]["model_digest"]
assert proposal["recipe_status"] == "withheld"
for result in (deterministic, proposal):
    assert result["command"] is None and result["settings"] is None
    assert not result["workflow"]["recipe_released"]
    assert result["provenance"]["source_revision"] == pinned
    assert result["provenance"]["index_sha256"] == index_hash
    assert result["provenance"]["spec_sha256"] == spec_hash
print("Spec and index SHA-256", spec_hash, index_hash)
PY
```

| Gate | Result and evidence |
| --- | --- |
| Clean MPML, configured interpreter, matching revision/spec/index | Pending |
| Doctor, spec, inspect and explain | Pending |
| Index and cited lexical retrieval | Pending |
| Explicit preflight exit status and diagnostics | Pending |
| Grounded deterministic answer with zero model calls | Pending |
| Qualified local Qwen answer, one call, provenance and withheld recipe | Pending |
| Null public command/settings and no experiment, artifact loading or brokerage operation | Pending |

Record the actual commands, result JSON location, exit statuses, model digest and
timings. Confirm only the configured spec and preflight modules were used, and
that no experiment entrypoint, artifact-loading routine or broker action ran.
Preflight findings establish launch-surface checks. Record candidate correctness
and complete intent separately.

## Publication after review

1. Merge the preparation PR. Run the public and maintainer-local checks against
   the exact intended release commit and have a reviewer verify the evidence.
2. If all gates pass, create an annotated `v0.1.0rc1` tag at that tested SHA and
   push the tag. Resolve failures before tagging.
3. Create a GitHub **pre-release** from that tag. Include the tested SHA,
   artifact checksums, installation instructions and
   [draft notes](V0_1_0_RC1_NOTES.md). Attach the tested wheel and sdist if
   distributing binaries and sources through GitHub.

After approval, set `TESTED_SHA` to the recorded merged commit and run
`git tag -a v0.1.0rc1 "$TESTED_SHA" -m "Argus CLI v0.1.0rc1"` followed by
`git push origin refs/tags/v0.1.0rc1`.

Tagging and publication are outside the preparation PR. PyPI publication is
outside this preview procedure.
