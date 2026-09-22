# One-terminal local startup

Status: accepted · 2026-09-22

## Context

Cloning and initializing Agora previously left the user with no running console.
Two terminals with matching environment variables were necessary for a mission
to leave the queue. The beginner path should start a complete local installation.

## Contract

`python -m agora start [--directory DIR] [--port PORT]` uses an existing private
installation (default `~/.config/agora`) and listens only on IPv4 loopback.
It does not provision accounts, test providers, download models, replace secrets,
or expose the service publicly. Empty agent profiles allow local exploration.
Queued missions retain their existing explicit authorization and resume; startup
prints this fact. Configuration validation does not establish model availability.

The directory selects the key, profiles and database as a unit, overriding old
service environment settings and disabling legacy defaults. Other commands keep
their previous environment/`--db` behavior. A bad private file, profile, occupied
port or runner lock produces a concise nonzero CLI error, not raw exception data.

## Implementation and alternatives

Use the existing Uvicorn server and deterministic runner step in one foreground
process, with a runner thread. Retain a bound socket to avoid port check/bind races
and the same database flock as the standalone runner to prevent duplicate work.
SO_REUSEADDR permits immediate restart; SO_REUSEPORT is deliberately not enabled.
No process supervisor, shell script, dependency or hosted service is added.

The runner starts after web startup and stops when the server exits. If the
runner fails, the console exits too with a safe diagnostic. Shutdown waits for
the current step; it does not kill model subprocesses and leave orphaned work.
Existing provider timeouts still apply. This is graceful stop, not instantaneous
cancellation or a cost refund. Forced process/OS termination is not covered.
The existing separate production service entrypoints are unchanged.

## Verification and limits

CLI subprocess tests exercise real HTTP/auth, private files, bad configuration,
port collisions, the shared runner lock, SIGINT/SIGTERM and same-port restart.
A fake subscription executable validates an explicitly queued description-only
mission without any external provider or user credential. This is not a real
Claude validation. macOS is tested; Windows is unsupported by the POSIX runtime.
No schema change is required. Roll back by using the documented separate services.
