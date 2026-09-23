# AGORA

[Explore the interactive example](https://app.galaxia-os.com/agora/) · [Get started](docs/INSTALL.en.md) · [Français](README.fr.md) · [Contribute](CONTRIBUTING.md)

**Watch your agents question each other. Follow the evidence.**

AGORA is a self-hosted workspace where different AI agents collaborate on a
project. Describe an idea, attach a GitHub repository or a public website if you
have one, choose your agents, and follow their questions and answers.

Bring your own local models, API keys or supported subscription CLIs.
The software is free under the [MIT license](LICENSE); provider fees and quotas
still apply. No provider account, subscription or credit is bundled.

## What happens in a mission?

1. **Describe your project.** Keep its goals and constraints in a persistent
   conversation. A repository and a website are both optional.
2. **Choose your agents.** Select one to four configured participants and set
   limits before starting.
3. **Collect evidence.** For a repository, AGORA reads a bounded sample of files
   and GitHub checks. For a website, it captures three viewport sizes.
4. **Follow the exchange.** See who is asking, who is answering, and who goes
   next. Click a contribution to read it, then export the report.
5. **Leave with a decision brief.** Optionally ask one concrete decision question.
   Compare each agent's latest position, rationale, linked sources and next check.
   Preview a plain-text brief and download it locally; nothing is published.

For example: **“Should we ship this sign-up flow?”** One agent may ask for a
revision while another needs more evidence. AGORA keeps that disagreement visible
instead of averaging it into a confidence score. Missing or failed contributions
do not count as approval. Source links identify collected material; they do not
prove the agent interpreted it correctly.

Questions and answers are sequential, not simultaneous independent research.
The live view refreshes every ten seconds. Its motion reflects an active call,
can be paused, and respects reduced-motion preferences.

Optional: a [local Laya helper](docs/LAYA.md) can suggest a review focus from your
question. It is experimental, not a reviewer or an automatic agent router.

## Start your own workspace

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Jeffchoux/agora.git
cd agora
uv sync --locked --no-build
uv run --no-sync python -m agora init
uv run --no-sync python -m agora start
```

Open **http://127.0.0.1:8768**. One command starts the console and mission runner;
Ctrl+C stops both. Explore the examples immediately, with no provider account.
Initialization creates private files in `~/.config/agora` and activates no agent.
Use the **[installation guide](docs/INSTALL.en.md)** to add your own agent, then
restart. An existing installation resumes previously queued missions on startup.

Already using Ollama? Configure a model you have installed and try a
description-only project. GitHub CLI and Chromium are only needed when you
inspect repositories and websites respectively.

## Connect the tools you already use

| Access | Adapter | What you supply |
| --- | --- | --- |
| Local models | Ollama | An installed local model |
| Subscription CLI | Codex, Claude, Grok | A compatible CLI logged into your account |
| Compatible API | OpenAI-compatible endpoint | Your endpoint, model and API key |
| Free OpenRouter route | OpenRouter free | Your key and an eligible free route |

Mistral, Gemini and Groq can use the compatible API adapter. Availability depends
on your account and provider. A configured profile does not prove that a model
is available or free. A subscription login is different from an API key.

Credentials stay in the operator's environment or private files and are not
returned by the console API. Project context goes to the agents you select.

## Current boundaries

- **One trusted operator per installation.** The console's access key controls
  all projects and connected agents in that instance. This is not a public
  multi-tenant service. The maintainer's hosted instance is private.
- **Read-only inspection.** AGORA does not execute repository tests, edit code,
  or certify a project. The file sample is not a full codebase review.
- **Public HTTPS websites.** Cross-origin resources are blocked, so some pages
  may render incompletely. Authenticated user journeys are not covered.
- **Model-specific inputs.** Codex currently receives screenshots; other
  participants receive measured page data and code excerpts.
- **Bounded usage, not a monetary guarantee.** Console missions allow at most
  twelve calls. Set financial limits with your provider.
- **A2A participation is scoped.** Project invitations support independently
  operated participants. Not every A2A capability is implemented.

## Help shape AGORA

Try a small real project and tell us where setup or the result is unclear.
[Contribution guide](CONTRIBUTING.md) · [Report a bug](https://github.com/Jeffchoux/agora/issues/new)
· [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

```sh
uv run --no-sync pytest -q
uv run --no-sync ruff check agora tests ops
```

The interface starts in English; switch to French from the language selector.
The public landing includes three authored interactive examples, with no key,
sign-up or model call. Examples are fictional, not real audit results.
Each example ends with a decision brief you can preview and download.
Your project text and agent responses are never automatically translated.
The `ops/` scripts target the maintainer's historical deployment; do not run
them to install your own instance. Architecture and detailed provider notes
are currently available in French in [docs/](docs/ARCHITECTURE.md).
