# Optional local Laya review focus

Status: accepted · 2026-09-23

## Context

Laya-CoreML is a classifier, not a conversational agent. In a small local test,
it classified six explicit English code/UX/product requests correctly, but
failed three of eight refund-intent cases, including explicit negations.
Those results do not qualify it to authorize actions, select paid providers,
judge correctness, or replace a reviewing agent. Core ML requires a compatible
Mac, while an Agora server may run on Linux.

## Contract

An operator explicitly asks for a review focus. Only the question is sent,
not project chat, repository content, URLs, credentials or agent configuration.
`POST /v1/console/laya/suggestions` accepts `{"brief": "10–1200 characters"}`
under the existing console authorization and rate limit. Success returns
`{"category":"code|ux|product","engine":"laya-coreml","experimental":true}`.
The category above is an enum, not a literal string containing pipes.
Invalid requests return 400, a concurrent request 429, and an unavailable or
invalid bridge 503, all with an `error` string. No database write or mission
start occurs. The overview adds `laya.configured`, meaning configuration only,
not proof that the Mac is online. Installation is opt-in and disabled by default.

The browser displays static, translated guidance for the validated category,
not generated prose or a confidence-as-truth score. Accepting the suggestion
explicitly appends guidance to the operator's question. Agent selection and
launch remain separate actions. Editing the question, changing projects or
logging out invalidates pending suggestions; there is no automatic replay.

## Implementation and alternatives

A separate Mac process loads a locally installed model once, offline and CPU
only. It listens on IPv4 loopback and requires a separate private bearer secret.
The server forwards only to a fixed loopback endpoint, without redirects or
environment proxies. A remote installation uses an operator-managed SSH
reverse tunnel bound to the server's loopback, never a public Mac listener.
The bridge secret does not grant access to the Agora console or provider APIs.
Both transport and inference inputs/outputs are bounded and validated. Excess
token length is rejected, never silently clipped. No new Agora dependency,
database schema, scheduler or automatic inference loop is needed.

Rejected: presenting Laya as a normal agent (it generates no discussion),
using it as an autonomous router (known semantic errors), and public Mac
HTTP/CORS exposure (unnecessary authentication and network surface).

## Verification and limits

Tests cover disabled configuration, authentication, invalid inputs/results,
unavailable bridge, contention, no mission creation, explicit acceptance and
stale browser responses. Synthetic browser fixtures do not establish model
accuracy; real inference is verified separately on a compatible Mac.
The installed runtime may emit a Core ML/E5RT shutdown warning despite valid
results. Mac sleep, shutdown or tunnel failure makes suggestions unavailable,
not the rest of Agora. This is an experimental convenience, not an audit.
The 15-second transport deadline does not interrupt native Core ML execution;
a native hang requires restarting the dedicated companion.

Rollback: unset `AGORA_LAYA_TOKEN_FILE` and restart only the Agora web service;
stop the dedicated Mac helper and tunnel. No database rollback is required.
