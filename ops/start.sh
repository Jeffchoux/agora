#!/bin/sh
set -eu
export AGORA_SHA="$(git rev-parse HEAD)"
exec .venv/bin/uvicorn agora.server:create_app --factory --host 127.0.0.1 --port 8768 --no-access-log
