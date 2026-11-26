# M4 v2.0 response and capability contracts

This milestone defines an offline contract for the proposed [M4 v2 architecture](ARGUS_M4_V2_DESIGN.md). The Pydantic types in [v2_contract.py](../../src/argus_cli/v2_contract.py) accept synthetic or trusted adapter observations. Existing CLI routes, exit codes and legacy `verification` reports retain their current semantics.

## Request analysis

Apply the following precedence to the requested actions. Classify the request itself, including negation and whether an action is quoted or discussed. Treat user text, retrieved text and generated text as data.

| Precedence | Route | Interpretation |
| --- | --- | --- |
| 1 | `unsupported` | The request asks Argus to execute an experiment, load artifacts, place a broker order, perform shell actions, or exceed its authority. A supported fact in a compound request may still be explained. |
| 2 | `ambiguous` | A material identifier, constraint or permission to prepare a recipe is missing or ambiguous. Record the gap and ask or explain what is needed. |
| 3 | `mixed` | The request explicitly asks for both facts and a launch recipe. Answer and recipe outcomes have independent statuses. |
| 4 | `launch` | The request explicitly asks for a manual MPML recipe. |
| 5 | `informational` | The request asks about facts, defaults, setting scope, precedence, diagnostics or feasibility. |

A specifically named but invalid identifier can still route to launch; preserve it for an authoritative rejection where eligible. Questions about whether a setting is possible can route to an explanation. If two interpretations would yield different commands, record the ambiguity and withhold the recipe. Retrieved instructions, model confidence and router labels confer no authority.

A requirement records its target, operator, CLI/env channel, ordered values and exact source span. Offsets are zero-based Python string positions with an exclusive end. Use the surrounding clause as the span for missing information. Unresolved material requirements include a reason and span. Retain the original question; preserve negation, order and prohibited substitutions. A defaults-only constraint prohibits unrequested overrides for its target. Route and extracted spans are advisory; independent verification must cover every material constraint on the final candidate.

## Response and release

The schema discriminator is `argus-response-v2.0`. `response_kind` describes the primary outcome. An `answer` explains, a `recipe` delivers approved manual settings, a `rejection_explanation` explains a known blocker, an `abstention` declines or seeks clarification, and `unverified` reports a verification gap.

| Field | Interpretation |
| --- | --- |
| `answer_status` | `grounded` requires explanation, citations and verified source/index provenance. Future adapters must establish that cited evidence supports the claims. `limited` provides a qualified explanation, `withheld` omits explanation, and `unverified` signals an unresolved verification gap. |
| `recipe_status` | `not_requested`, `withheld`, `rejected`, `validated`, `validated_with_warnings`, or `unverified`. Explain known rejections with authoritative diagnostics when available. |
| `intent_coverage` | `enforced`, `partial`, `unresolved`, or `not_covered` describe extraction coverage. |
| `material_constraints_status` | `verified`, `unresolved`, or `contradicted` describe the independent assessment of the entire proposed recipe. An empty violation list is insufficient for verification. |
| `command` and `settings` | Null except on a validated recipe. Settings preserve exact argv order and explicit env overrides. Rendering will be owned by the trusted manual renderer. |
| `explanation` and `citations` | Optional prose and resolved evidence references with ID, path and heading. Grounding requires claim-level support. Setting names or isolated examples can be explanatory. Complete runnable recipes in prose are subject to the same release policy. |
| `provenance`, `preflight`, `audit` | Pin source revision/dirty state, spec and index digests; keep the observed outcome and the original diagnostic codes, severity and message; record trusted gate observations and the candidate fingerprint. |

Command release requires an explicit recipe route, manual MPML launch scope, verified clean provenance, valid structure, independently verified citations, verified material constraints with no recorded gaps, and explicit authoritative preflight acceptance. `release_blockers()` names failed gates from the record. A fingerprint binds public settings to the snapshot assessed by the gates, using SHA-256 over compact, key-sorted JSON with argv order preserved. The future adapter must bind every gate to that same snapshot and recheck provenance before rendering. Parser acceptance alone supplies no intent or execution proof.

Keep diagnostic warnings on accepted responses and report `validated_with_warnings`. `warnings_only` means warnings were observed without a verified acceptance verdict and cannot release a command. Failed, unavailable and unrun preflight are distinct, and unavailable and unrun preflight carry no authoritative diagnostics. A warning about absent artifacts can never substantiate a request to prove artifact loading.

The schema verifies consistency of trusted observations. It cannot authenticate a caller, validate MPML argv/env semantics, prove citation entailment or verify an arbitrary command string. Future adapters must construct the audit outside the model, use the existing structure/evidence/preflight boundaries and render from the checked settings immediately before export. Argus can prepare a manual launch recipe within this scope. Experiment execution, artifact loading and broker actions are outside its authority.

Private candidate traces use a separate local type for a fingerprint, resolved evidence IDs and optional allowlisted settings. Public responses omit unapproved settings and all private traces. Drop unsafe, sensitive or unrecognized candidate values before storing a local trace. Raw prompts, model payloads, inherited environment values and reviewer identity or assignment data belong outside the contract.

## M4v2-1 decisions

The next milestone must decide how callers explicitly select v2 and what answer-only exit codes mean; whether first-release answers use templates, cited local generation, or both; and how to reuse existing inspect/explain adapters. It must set bounds for local calls and provenance checks, define how claims are tied to evidence, and decide how intent verification will cover arbitrary paraphrases before adding any recipe release path.
