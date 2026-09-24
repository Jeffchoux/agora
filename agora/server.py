import hmac
import json
import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from a2a.auth.user import User
from a2a.server.agent_execution import AgentExecutor
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers.default_request_handler_v2 import (
    DefaultRequestHandlerV2,
)
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.routes.common import ServerCallContextBuilder
from a2a.server.routes.fastapi_routes import add_a2a_routes_to_fastapi
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import a2a_pb2 as proto
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.protobuf.json_format import ParseDict

from agora.store import Denied, Store


class Identity(User):
    def __init__(self, identity):
        self.identity = identity

    @property
    def is_authenticated(self):
        return True

    @property
    def user_name(self):
        return self.identity["project"] + ":" + self.identity["agent"]


class Context(ServerCallContextBuilder):
    def build(self, request):
        identity = request.scope["agora_identity"]
        return ServerCallContext(
            user=Identity(identity),
            state={
                "identity": identity,
                "headers": {"a2a-version": request.headers.get("a2a-version", "")},
            },
        )


class Coordinator(AgentExecutor):
    def __init__(self, store):
        self.store = store

    async def execute(self, context, event_queue):
        try:
            data = json.loads(context.get_user_input())
            result = self.store.dispatch(context.call_context.state["identity"], data)
        except (ValueError, Denied, TypeError) as exc:
            result = {"error": str(exc)}
        await event_queue.enqueue_event(
            proto.Message(
                message_id=str(uuid.uuid4()),
                role=proto.ROLE_AGENT,
                parts=[proto.Part(text=json.dumps(result, ensure_ascii=False))],
            )
        )

    async def cancel(self, context, event_queue):
        # Exchanges complete synchronously. No remote model job is started here.
        raise ValueError("No asynchronous tasks to cancel")


class Guard:
    def __init__(self, app, store):
        self.app, self.store = app, store
        self.rates = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        public = path in {
            "/",
            "/ui.css",
            "/capture.css",
            "/ui.js",
            "/i18n.js",
            "/messages.js",
            "/landing.js",
            "/landing.css",
            "/decisions.js",
            "/decisions.css",
            "/catalog.js",
            "/catalog.css",
            "/providers.json",
            "/health",
            "/.well-known/agent-card.json",
        }

        async def reject(code, text):
            await JSONResponse({"error": text}, status_code=code)(scope, receive, send)

        if not public:
            headers = dict(scope.get("headers", []))
            token = headers.get(b"authorization", b"").decode("latin1")
            if not token.startswith("Bearer "):
                return await reject(401, "credential required")
            if path == "/v1/console" or path.startswith("/v1/console/"):
                secret_file = os.environ.get("AGORA_ADMIN_TOKEN_FILE", "")
                try:
                    expected = (
                        Path(secret_file).read_text().strip() if secret_file else ""
                    )
                except OSError:
                    expected = ""
                if not expected or not hmac.compare_digest(token[7:], expected):
                    return await reject(401, "invalid operator credential")
                identity = {"project": "operator", "agent": "console"}
            else:
                try:
                    identity = self.store.authenticate(token[7:])
                except Denied:
                    return await reject(401, "invalid credential")
            scope["agora_identity"] = identity
            key = (identity["project"], identity["agent"])
            times = self.rates[key]
            now = time.monotonic()
            while times and times[0] < now - 60:
                times.popleft()
            if len(times) >= 60:
                return await reject(429, "request rate exceeded")
            times.append(now)
        # Enforce bytes, including chunked bodies; never trust Content-Length.
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            size += len(event.get("body", b""))
            if size > 65536:
                return await reject(413, "request too large")
            chunks.append(event.get("body", b""))
            if not event.get("more_body"):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(path=None, url=None):
    store = Store(path or os.environ.get("AGORA_DB", "state/agora.sqlite"))
    base = (url or os.environ.get("AGORA_URL", "http://127.0.0.1:8768")).rstrip("/")
    card = ParseDict(
        {
            "name": "Agora",
            "description": "Project-scoped collaboration board for invited independent agents.",
            "version": "0.1.0",
            "supportedInterfaces": [
                {
                    "url": base + "/a2a",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
            "capabilities": {},
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "securitySchemes": {
                "bearer": {"httpAuthSecurityScheme": {"scheme": "bearer"}}
            },
            "securityRequirements": [{"schemes": {"bearer": {"list": []}}}],
            "skills": [
                {
                    "id": "project-dialogue",
                    "name": "Project collaboration",
                    "description": "JSON operations in message text: board, post, claim, complete. Invited project members only.",
                    "tags": ["collaboration", "questions", "artifacts"],
                }
            ],
        },
        proto.AgentCard(),
    )
    app = FastAPI(title="Agora", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": "0.1.0",
            "source_sha": os.environ.get("AGORA_SHA", "development"),
        }

    @app.post("/v1/exchange")
    async def exchange(request: Request):
        try:
            return store.dispatch(request.scope["agora_identity"], await request.json())
        except Denied as exc:
            return JSONResponse({"error": str(exc)}, status_code=403)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    from agora.console import install

    install(app, store)
    handler = DefaultRequestHandlerV2(Coordinator(store), InMemoryTaskStore(), card)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(
            handler, rpc_url="/a2a", context_builder=Context()
        ),
    )
    app.add_middleware(Guard, store=store)
    app.state.store = store
    return app
