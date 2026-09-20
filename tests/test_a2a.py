import json
import uuid

import httpx
import pytest
from a2a.client import ClientConfig, ClientFactory
from a2a.types import a2a_pb2 as p
from google.protobuf.json_format import ParseDict

from agora.server import create_app


@pytest.mark.asyncio
async def test_official_sdk_two_independent_clients(tmp_path):
    app = create_app(tmp_path / "a2a.sqlite", url="http://test")
    store = app.state.store
    store.create_project("demo", "Define a tiny feature")
    ta = store.invite("demo", "codex")
    tb = store.invite("demo", "partner")

    async def exchange(token, data):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + token, "A2A-Version": "1.0"},
        ) as http:
            card = ParseDict(
                (await http.get("/.well-known/agent-card.json")).json(), p.AgentCard()
            )
            client = ClientFactory(
                ClientConfig(
                    streaming=False,
                    httpx_client=http,
                    supported_protocol_bindings=["JSONRPC"],
                )
            ).create(card)
            req = p.SendMessageRequest(
                message=p.Message(
                    message_id=str(uuid.uuid4()),
                    role=p.ROLE_USER,
                    parts=[p.Part(text=json.dumps(data))],
                )
            )
            async for event in client.send_message(req):
                if event.HasField("message"):
                    return json.loads(event.message.parts[0].text)

    question = await exchange(
        ta,
        {
            "operation": "post",
            "recipient": "partner",
            "kind": "question",
            "body": "What should the first task be?",
            "request_key": "q",
        },
    )
    assert "id" in question
    inbox = await exchange(tb, {"operation": "board", "inbox": True})
    assert inbox["messages"][0]["id"] == question["id"]
    answer = await exchange(
        tb,
        {
            "operation": "post",
            "recipient": "codex",
            "kind": "answer",
            "body": "Specify acceptance tests.",
            "request_key": "a",
            "parent": question["id"],
        },
    )
    assert answer["parent"] == question["id"]
