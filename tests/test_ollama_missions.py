"""Ensure mission output stays bounded and incomplete responses are rejected."""
import json

import httpx
import pytest

from agora.worker import generate


def mocked_client(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs
    ))


def test_local_mission_uses_small_schema_for_expected_answer(monkeypatch):
    def handler(request):
        data = json.loads(request.content)
        schema = data['format']
        assert schema['properties']['kind']['const'] == 'answer'
        assert schema['properties']['assessment'] == {'type': 'null'}
        assert '$defs' not in schema
        assert data['options']['num_predict'] == 512
        return httpx.Response(200, json={'done_reason': 'stop', 'message': {
            'content': '{"kind":"answer","body":"A concrete step","assessment":null}'}})
    mocked_client(monkeypatch, handler)
    result = generate({'provider': 'ollama', 'model': 'local', 'expected_kind': 'answer',
                       'decision_required': False}, 'Brief')
    assert result.kind == 'answer' and result.assessment is None


def test_structured_decision_retains_assessment_schema(monkeypatch):
    def handler(request):
        schema = json.loads(request.content)['format']
        assert '$defs' in schema
        assert schema['properties']['kind']['const'] == 'review'
        assert 'anyOf' in schema['properties']['assessment']
        return httpx.Response(200, json={'done_reason': 'stop', 'message': {
            'content': '{"kind":"review","body":"Review","assessment":null}'}})
    mocked_client(monkeypatch, handler)
    generate({'provider': 'ollama', 'model': 'local', 'expected_kind': 'review',
              'decision_required': True}, 'Brief')


def test_truncated_json_never_accepted_even_if_valid(monkeypatch):
    mocked_client(monkeypatch, lambda _: httpx.Response(200, json={
        'done_reason': 'length', 'message': {'content': '{"kind":"answer","body":"Incomplete"}'}}))
    with pytest.raises(ValueError, match='truncated'):
        generate({'provider': 'ollama', 'model': 'local'}, 'Brief')
