# Run your own AGORA

[Français](INSTALL.md) · [Back to README](../README.md)

## 1. Install and initialize

On macOS or Linux, with Python 3.11+ and uv installed:

```sh
git clone https://github.com/Jeffchoux/agora.git
cd agora
uv sync --locked --no-build
uv run --no-sync python -m agora init
```

Windows is not currently a verified installation target. The runner uses POSIX
file locking and the CLI adapters use POSIX process groups.

Initialization creates three private files under `~/.config/agora`:

- `operator.key`: opens your console. Keep this private.
- `agents.json`: your agent profiles, initially empty.
- `credentials.json`: your API credentials, initially empty.

Existing files are preserved. No model is called by initialization. Do not put
these files into Git or paste their secrets into a project conversation.

## 2. Add an agent you already have

For a first mission with Ollama, edit `agents.json` and use the exact model name
from your own installation (`ollama list`):

```json
{
  "local": {
    "label": "My local model",
    "provider": "ollama",
    "model": "REPLACE_WITH_YOUR_INSTALLED_MODEL"
  }
}
```

Keep Ollama running locally. AGORA does not download models for you. To compare
different models, add another profile with its own ID and installed model name.

For a subscription CLI already authenticated on this machine:

```json
{
  "claude": {
    "label": "My Claude",
    "provider": "claude-cli",
    "model": "haiku",
    "operator_authorized": true
  }
}
```

Codex uses `provider: "codex-cli"` and a model available to your account. Grok
uses `provider: "grok-cli", model: "default"`. Use each provider's official
login flow and a CLI version compatible with the adapter. AGORA does not supply
or transfer subscription sessions. Authorization of a profile is explicit;
login and quota availability are separate requirements.

For an API, add a profile such as:

```json
{
  "my-api": {
    "label": "My API",
    "provider": "openai-compatible",
    "model": "REPLACE_WITH_YOUR_MODEL",
    "endpoint": "https://api.mistral.ai/v1",
    "key_env": "MISTRAL_API_KEY",
    "credential_file": "~/.config/agora/credentials.json",
    "operator_authorized": true
  }
}
```

Put your own key under the matching `MISTRAL_API_KEY` property in
`credentials.json`, editing that file locally. Keep files at mode 0600 and the
directory at 0700. Alternatively, omit `credential_file` and supply the named
environment variable to the runner. Never put raw keys in `agents.json`.

Gemini's compatible endpoint is
`https://generativelanguage.googleapis.com/v1beta/openai`; Groq's is
`https://api.groq.com/openai/v1`. Use the corresponding key and model for each.
Set billing limits with your provider: AGORA's call cap is not a dollar cap.

## 3. Start the console and runner

In a terminal at the repository root:

```sh
uv run --no-sync python -m agora start
```

Open **http://127.0.0.1:8768**. The public introduction lets you explore fictional
examples without a key. Under **Get Agora**, choose **Already installed? Open
this workspace**, then use the file selector to load your local `operator.key`.
This is your installation’s operator key, not a provider API key.

The console and mission runner run together in this terminal. No second terminal
or environment exports are needed. With no profiles, you can still explore the
examples and create projects. No provider is contacted to check configuration.
Only explicitly launched missions call your selected agents. **Previously queued
missions resume on startup**, including ones queued in an earlier session.

Restart after changing profiles. Ctrl+C or SIGTERM stops new runner steps and
waits for the current step (source collection or model call) to finish before
releasing the database lock. This may take minutes; it does not cancel a charge
already incurred. Do not force-kill the process during a provider call.

For a different private directory or an occupied port:

```sh
uv run --no-sync python -m agora start --directory /path/to/private/agora --port 8769
```

Use the same `--directory` with `init` first. `start` always uses `operator.key`,
`agents.json` and `agora.sqlite` in that directory, overriding inherited
`AGORA_ADMIN_TOKEN_FILE`, `AGORA_AGENTS_FILE`, `AGORA_DB` and legacy mode.
It binds only to `127.0.0.1`, never exposes your machine to the network, and never
replaces keys or stops an existing service. Windows is not supported by this
POSIX launcher; macOS is tested, Linux uses the same POSIX interfaces.

### Advanced: separate supervised services

Existing deployments can retain their two entrypoints. In **each** service's
environment, set these paths to the same private installation:

```sh
export AGORA_ADMIN_TOKEN_FILE="$HOME/.config/agora/operator.key"
export AGORA_AGENTS_FILE="$HOME/.config/agora/agents.json"
export AGORA_DB="$HOME/.config/agora/agora.sqlite"
```

Run `uv run --no-sync uvicorn agora.server:create_app --factory --host 127.0.0.1 --port 8768`
for the web service and `uv run --no-sync python -m agora.mission_runner` for the
runner. Do not run these alongside `agora start` against the same database.

## 4. Complete your first mission

The interface starts in English. The header lets you switch to French; your
choice is saved in this browser. Project text and previous responses are not
translated. New agent responses follow the language of the mission brief.

1. **Add a project**: give it a name; leave repository and URL
   empty for your first description-only project.
2. Select the project, then use **Tell us about your project** to describe its goal and
   constraints. **Add to discussion** saves context without a model call.
3. **Prepare an agent response** opens the mission form. Select your agent
   and a small call limit, then choose **Start review**.
4. **Around the table** shows the current speaker and question/answer direction.
   **All exchanges** opens the transcript; **Export JSON report** saves it.
5. Optionally fill **Decision to resolve** before starting, for example:
   “Should we start a five-person pilot?” All agents assess that same proposal.
   The **Decision brief** shows each latest position, reasons and next check.
   Expand its preview to download a local `.txt` snapshot. It contains project
   content: review it before sharing. No upload or publication takes place.

Positions are `proceed`, `revise`, or `insufficient_evidence`, not an automated
approval. A missing structured response is shown as missing; AGORA does not retry
to manufacture consensus. An invalid source ID fails the call, which still counts
toward the budget. Provider support and output quality vary; the optional format
does not guarantee factual correctness. Leave the question empty for a regular
mission. Existing missions are unchanged.

Success means a real contribution appears and the mission finishes within its
configured limits. A queued mission has not yet received a model response.
Only the eight most recent project messages enter each turn, capped at 1,500
characters each. No source means no claim of code or website verification.

## Optional evidence sources

For GitHub repositories, install GitHub CLI and run `gh auth login` with your
own account. For website captures, install the browser:

```sh
uv run --no-sync playwright install chromium
```

Neither is required for a description-only project. Source collection is bounded
and read-only; AGORA does not run the target repository's test suite.

## Troubleshooting

### Optional local Laya helper

A compatible Mac can suggest a code, UX or product review focus from a short
question. It does not join the agent discussion or start missions. Suggestions
are experimental and require your acceptance. See [private setup and limits](LAYA.md),
including connecting a Mac to an Agora instance hosted on Linux. No automatic
model downloads or paid API fallback.

| What you see | Check |
| --- | --- |
| Configuration missing | Run `agora init` with the same `--directory` as `start`; never copy someone else's key. |
| Private file / directory error | Use operator-owned regular files at mode 0600 and a directory at 0700; no symlinks. |
| Invalid agents.json | Follow the profile examples above. Keys belong in the private credentials file, not the profiles. |
| Port already in use | Choose `--port 8769`; Agora does not kill the other service. |
| Runner already owns the database | Stop the existing runner before using the combined launcher. |
| No agents in the selector | Edit the selected directory's `agents.json`, then restart `agora start`; for separate services, check `AGORA_AGENTS_FILE`. |
| Mission stays queued | Confirm `agora start` is still running; for separate services, start the runner with the console's database and profiles. |
| Provider call fails | Model name, CLI login or API key, quota and adapter compatibility; no automatic paid fallback |
| Inspection fails before agents run | GitHub account access, public HTTPS URL, installed Chromium |
| Console login rejected | Load your own `operator.key` from the path used by the console |

## Hosting and upgrades

An instance is for one trusted operator. Its console key controls all projects
and profiles in that instance. This is not a multi-user public service. Use a
dedicated OS account, private storage and an HTTPS reverse proxy if hosting it.
Stop the runner and take a SQLite backup before upgrading. Do not execute the
maintainer-specific scripts in `ops/` for your deployment.
