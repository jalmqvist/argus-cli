# ADR 0001: MPML owns its launch semantics

Status: Accepted (initial scaffold)

Argus reads `python -m mpml.spec` in MPML's own interpreter and validates candidates with
`python -m mpml.preflight` in that interpreter and working directory. Argus does not duplicate
modern MPML rule logic or import `main.py` into the Argus process. The generated docs and
spec are indexed with a source revision. Preflight is read-only and does not validate
artifact contents or guarantee the requested experiment will execute.
