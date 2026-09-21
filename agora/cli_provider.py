"""Subscription CLI participants, fixed argv and bounded lifetime; no shell eval."""

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path


def execute(argv, prompt, cwd, env, timeout=120):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=errors,
            cwd=cwd,
            env=env,
            start_new_session=True,
            text=True,
        )
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise ValueError("CLI response deadline exceeded") from None
        if process.returncode:
            # Never expose auth material or arbitrary provider diagnostics in board/logs.
            raise ValueError(
                f"CLI failed (exit {process.returncode}); check login/quota"
            )
        if output.tell() > 262144:
            raise ValueError("CLI output exceeds limit")
        output.seek(0)
        return output.read().decode()


def generate_cli(config, prompt, schema, images=()):
    if config.get("operator_authorized") is not True:
        raise ValueError("subscription usage must be authorized")
    # Remove provider overrides: only the already connected subscription is allowed.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ANTHROPIC_", "OPENAI_", "CLAUDE_CODE_USE_"))
    }
    with tempfile.TemporaryDirectory(prefix="agora-text-") as directory:
        if config["provider"] == "claude-cli":
            if images:
                raise ValueError("images unavailable for Claude participant")
            auth = json.loads(
                execute(
                    ["claude", "--safe-mode", "auth", "status"], "", directory, env, 20
                )
            )
            if (
                auth.get("loggedIn") is not True
                or auth.get("authMethod") != "claude.ai"
            ):
                raise ValueError("Claude subscription login required on this machine")
            argv = [
                "claude",
                "--safe-mode",
                "--tools",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--model",
                config["model"],
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(schema),
                "--max-turns",
                "1",
                "-p",
            ]
            result = json.loads(execute(argv, prompt, directory, env))
            if result.get("is_error"):
                raise ValueError("Claude rejected request (login or quota)")
            structured = result.get("structured_output")
            return json.dumps(structured) if structured else result.get("result", "")
        if config["provider"] == "grok-cli":
            if images:
                raise ValueError("images unavailable for Grok participant")
            env = {
                k: v for k, v in env.items() if k not in {"XAI_API_KEY", "GROK_API_KEY"}
            }
            argv = [
                "grok",
                "--verbatim",
                "--system-prompt-override",
                "You are a text-only project collaborator. Return only the requested JSON. No tools or external actions.",
                "--tools",
                "",
                "--no-subagents",
                "--no-memory",
                "--disable-web-search",
                "--permission-mode",
                "plan",
                "--max-turns",
                "1",
                "--cwd",
                directory,
                "--json-schema",
                json.dumps(schema),
                "--prompt-file",
                str(Path(directory) / "prompt.txt"),
            ]
            Path(directory, "prompt.txt").write_text(prompt)
            result = json.loads(execute(argv, "", directory, env))
            if "kind" in result and "body" in result:
                return json.dumps(result)
            structured = result.get("structuredOutput") or result.get(
                "structured_output"
            )
            return (
                json.dumps(structured)
                if structured
                else result.get("text", result.get("result", ""))
            )
        if config["provider"] != "codex-cli":
            raise ValueError("unsupported CLI")
        status = execute(["codex", "login", "status"], "", directory, env, 20)
        # Some CLI versions print status on stderr; forced_login_method below also
        # rejects API authentication without ever falling back to a paid API key.
        del status
        schema_path = Path(directory) / "schema.json"
        schema_path.write_text(json.dumps(schema))
        answer_path = Path(directory) / "answer.json"
        argv = [
            "codex",
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-c",
            'forced_login_method="chatgpt"',
            "-c",
            'web_search="disabled"',
            "-c",
            "project_doc_max_bytes=0",
            "-c",
            'model_reasoning_effort="low"',
            "--model",
            config["model"],
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(answer_path),
            "--json",
        ]
        for feature in [
            "shell_tool",
            "unified_exec",
            "apps",
            "hooks",
            "multi_agent",
            "skill_search",
            "shell_snapshot",
        ]:
            argv += ["--disable", feature]
        for path in images:
            image = Path(path)
            if not image.is_absolute() or image.suffix != ".png" or not image.is_file():
                raise ValueError("invalid mission capture")
            argv += ["--image", str(image)]
        argv += ["--enable", "skip_host_skill_discovery", "-"]
        events = execute(argv, prompt, directory, env)
        for line in events.splitlines():
            event = json.loads(line)
            item = event.get("item", {})
            if item.get("type") in {"command_execution", "mcp_tool_call", "web_search"}:
                raise ValueError("unexpected tool event in text participant")
        if not answer_path.exists() or answer_path.stat().st_size > 64000:
            raise ValueError("missing or oversized Codex answer")
        return answer_path.read_text()
