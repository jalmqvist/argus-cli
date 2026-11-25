# ADR 0003 — Structured MPML generation trust boundaries

The local source configuration supplies the checkout, interpreter, entrypoint,
and allowlisted MPML interfaces. The M2 index must match the live source.
Argus reuses its retrieval rankings and sends bounded excerpts with prompt-local
evidence IDs to a loopback Ollama endpoint. Question text and retrieved excerpts
are data in a separate message. They have no tool access or authority to change
the source configuration. The generation client disables proxies, redirects,
and LangSmith tracing. Remote model tags and aliases are refused.

The model proposes JSON only. Pydantic validates its shape before Argus resolves
citation IDs to indexed evidence and checks that the cited excerpts mention
each proposed flag and override. Argus admits exact flags and supported
argument shapes from the current spec, and only spec-listed launch-selector
environment keys. MPML preflight owns the remaining launch semantics. Argus
passes it the ordered argv and exact overrides in the inherited process
environment. Rechecking the source around preflight guards against evidence drift.

Successful preflight describes the launch surface. Intent, experiment completion,
and DL artifact activation are still unverified. Argus withholds the command
on rejection, unresolved intent, or potentially enabled DL. Commands that pass
the checks are serialized as shell-escaped text for manual execution. The only
MPML entrypoints called by Argus remain the existing spec and preflight modules.
