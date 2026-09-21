# Optional, inspectable decision briefs

Status: accepted · 2026-09-21

## Context

A transcript shows collaboration, but leaves the operator to reconstruct what
each agent recommends. We want a portable result without pretending a group of
models provides independently calibrated confidence or an automatic approval.

Inspiration: Jev separates state from typed decisions rather than generating
free-form answers. Its Choice, Score and Noul primitives are a different product
from a multi-agent workspace. We borrow the idea of an explicit decision contract,
not its model, probabilities or performance claims.
[TypeSafe introduction](https://docs.typesafe.ai/introduction)

TypeSafe's launch was dated September 15, 2026. Its speed/cost figures are
vendor-reported; we have not replicated them. Current universal availability and
the reported removal of its waitlist were not independently established. Neither
is needed for this feature. No Jev API, account or payment is introduced.
[Launch](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

## Contract

- Missions may supply `decision_question`, a trimmed string up to 500 characters;
  empty means the existing conversation-only behavior. The question participates
  in creation idempotency and is common to all selected agents.
- `Contribution.assessment` is optional for backwards-compatible readers. It
  contains `verdict` (`proceed`, `revise`, `insufficient_evidence`), `rationale`
  (1–800 characters), `next_check` (1–500), and `references` (0–8 source IDs).
  Unknown fields, wrong types and out-of-bounds values are rejected. Provider
  schemas require a nullable assessment for strict structured-output compatibility.
- The deterministic catalogue contains collected file paths, observed browser
  viewport IDs and the resolved commit, when present. Unknown references are
  rejected before persistence. Existence is not proof of relevance or correctness.
- A latest failed/running/unstructured turn supersedes an older assessment; there
  is no fallback to a stale positive opinion. Every selected agent has one row.
- `agreement=aligned` requires all selected agents to have a position with the
  same verdict. `mixed` means at least two reported verdicts differ. Otherwise
  it is `none`. None of these values is authorization to act.
- `complete=true` additionally requires a finished mission. A stopped/failed
  mission is provisional even if all positions exist. These are lifecycle labels,
  not measures of quality, truth or independence.
- The three most recent completed turns retain bounded structured positions in
  the next prompt. Sequential exposure makes agreement correlated, not a vote.
- Call caps and output-token caps are unchanged. Missing structure stays visible;
  malformed output or references fail the call, counted without automatic retry.

## Storage and presentation

SQLite adds `missions.decision_question` with an empty default and nullable
`mission_turns.assessment`, transactionally. Old missions/contributions remain
readable. The API adds `decision`; it is null when no question was requested.

The UI displays prose as text, retains original user/model language and translates
only authored labels. An explicit preview precedes the plain-text download. The
snapshot includes available mission identity/status, capture time, positions,
sources and caveats, but not raw brief/chat/transcript or provider profiles.
This is not secret redaction: any included text may contain project information.
No remote share endpoint, tracking or publication is added. Demo fixtures carry
their fictional/no-model-call label into the exported file.

## Verification and limitations

Offline tests cover strict validation, migration concurrency, idempotency,
catalogue rejection, latest-turn semantics, failure/stop/missing states, prompts
and API auth. Opt-in Chromium tests cover form submission, real SQLite snapshots,
English/French, exports, HTML-as-text and 320/768/1024/1440 px public examples.
Fixtures do not call providers. There is no new cross-provider live benchmark,
no claim of universal structured-output compliance, and no automatic execution.

Roll back application code only after stopping the runner and backing up SQLite.
The extra nullable/defaulted columns can remain; do not delete historical data.
