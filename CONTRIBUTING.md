# Contributing to AGORA

## Browser regression checks

After installing the locked development dependencies and Playwright Chromium,
run `AGORA_BROWSER_TESTS=1 uv run --no-sync pytest tests/test_global_ui.py -q`.
The tests start isolated local servers, use temporary credentials/data, and never
start a model runner. They cover the public example, English/French switching,
form preservation and delayed-response logout at 320/768/1024/1440 px. Set
`AGORA_BROWSER_ARTIFACTS` to a local folder to retain screenshots. Without the
opt-in variable, these browser cases are skipped by the normal unit suite.

Start with a small real use case. We especially welcome reports of confusing
setup steps, unavailable agents, unclear evidence and conversation UI problems.

## Report a problem

Use the bug-report template. Include your operating system, AGORA commit,
provider adapter and reproducible steps. Say whether a failure happens during
setup, source inspection or the model exchange.

Never include API keys, console keys, invitations, subscription sessions,
private repository content or personal project transcripts. Use a minimal
sanitized example. See [SECURITY.md](SECURITY.md) for security reports.

## Propose a change

Explain the user problem, expected behavior and how you will verify it. For a
large feature, open an issue before building. Small documentation corrections
can go directly to a pull request. Do not promise universal provider support,
free API usage, independent execution or tests that the software does not perform.

## Develop locally

Read [AGENTS.md](AGENTS.md), then:

```sh
uv sync --locked --no-build
uv run --no-sync pytest -q
uv run --no-sync ruff check agora tests ops
```

Use a branch, keep changes focused, and explain behavior and verification in
your PR. Use dummy credentials and isolated test data. Tests must not require
a maintainer account, paid API call or production mutation. For UI changes,
check keyboard access, narrow screens and reduced motion in a real browser.

## Product priorities

Current priorities are easier first use, an explicitly labeled no-key demo,
clear provider status, traceable questions and answers, and reproducible evidence.
Repository test execution would require a separate isolated execution boundary;
it must not be added as arbitrary shell execution on the operator's machine.

These are directions for contributions, not delivery-date promises. AGORA is
MIT licensed. Keep third-party licenses and attribution intact and document
new dependencies and their purpose.
