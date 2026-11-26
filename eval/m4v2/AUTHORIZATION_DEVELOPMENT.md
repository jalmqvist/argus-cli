# M4v2-2B offline candidate evaluation

`argus_cli.v2_authorization.evaluate` combines an extracted interpretation, proposed settings, and trusted observations. Its output separates recognized-constraint consistency, unresolved requirements, material intent, effective configuration, structural validity, citation resolution, setting support, preflight and named blockers. `eligible_from_trusted_offline_observations` describes this assessment only. There is no renderer, execution path or authority-granting tool interface.

## Gate ownership and binding

| Gate | Trusted producer and required evidence |
| --- | --- |
| Source and index | A future adapter uses the existing repository, MPML spec bridge and verified index checks. Capture immutable spec bytes, the clean revision and digest, the verified index digest and the resolved evidence IDs. Verify the same clean snapshot again before assessing eligibility. |
| Structure and scope | The future adapter runs the existing option validator on the exact argv/env and independently confirms that the request is within manual MPML launch scope. Offline consistency also flags unsupported tokens, channels, shapes, repeated scalar flags and published CLI choices. |
| Citation resolution and support | Resolve all supplied IDs against the pinned evidence set. A trusted reviewer of the evidence must establish support for each exact candidate setting, including its value and channel. Supply the reviewed citation IDs and setting-to-citation pairs. A defaults-only candidate requires support for relying on defaults, represented by target `*`. A name match alone supplies no support or intent attestation. |
| Explicit constraints | The offline evaluator compares the bound settings against the preserved constraints and rejects a violated constraint or unresolved material requirement. |
| Material intent and effective configuration | A future independent verifier, outside the proposer, must assess the entire original request against the exact candidate, including implicit requirements, CLI/env precedence and relevant inherited values. Candidate consistency or model confidence cannot provide this assessment. Both assessments default to unresolved when trusted verification is absent. |
| Preflight | The future adapter calls the authoritative MPML preflight bridge on the bound candidate with the same inherited environment and explicit overrides. Only explicit acceptance, including acceptance with warnings, satisfies this gate. No probe, unavailable, rejected and warnings without acceptance remain distinct. The evaluator preserves valid issue codes, severity and messages as recorded. |

Bindings cover the source revision and dirty bit, spec digest, index digest,
pinned evidence-ID set, original request and extracted constraints, exact argv
order, explicit env overrides and inherited environment digest. Env key order is
immaterial. No inherited values or runnable command appear in the result.
Keep the inherited environment fingerprint within the trusted call boundary.
The evaluator verifies the spec digest against the captured bytes and checks the
final identity and provenance status independently of preflight.

Matching hashes detect mismatched inputs. The app must establish who produced
each observation by constructing it from trusted in-process adapters, never from
model payloads or user-provided records. Python types and the authority field
describe that boundary. They cannot authenticate arbitrary callers. An unknown
or model-origin observation cannot satisfy a trusted gate. Diagnostic text stays
data and cannot change the preflight outcome. This API takes no generated prose.

## Offline evaluation

Run from the repository root with the development and LLM extras installed.

```sh
python -m pytest -q tests/test_v2_authorization.py
```

- [Synthetic development fixture](authorization-development-v1.json) matched all **39/39** expected blocker sets. Two cases were eligible under supplied observations and 37 were withheld. Six cases included a material-intent blocker, including missing or untrusted verification and unresolved artifact loading. One additional case isolated uncertainty about the inherited environment.
- All **13/13** invalidating mutations were blocked, with zero survivors. Candidate-value mutations use freshly bound structural, material and preflight observations so the recognized-constraint check itself has to catch the inconsistency. Tests also exercise stale observation replay separately.
- Synthetic observations establish test outcomes only. Neither the fixtures nor their mutations estimate live intent accuracy or safe release rates.

## M4v2-2C prerequisites

Wire the existing trusted adapters to capture structural, citation and authoritative
preflight evidence with the same frozen argv, env and source snapshot. Define how
an independent verifier assesses factual support, effective configuration and full
material intent before any live release. Recheck provenance and effective environment
at the actual release boundary. The renderer must receive the exact candidate those
checks covered.
