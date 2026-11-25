# ADR 0002: No experiment execution from Argus

Status: Accepted (initial scaffold)

Argus is advisory: it outputs a command and environment overrides for manual inspection.
It may execute only explicitly configured read-only introspection and validation entry
points. It never executes LLM-generated commands, and it does not call `main.py`.
