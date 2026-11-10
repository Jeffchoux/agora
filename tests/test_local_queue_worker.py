import sqlite3

import pytest

from agora import local_queue_worker as w

PREFIX = '[test team] '


@pytest.fixture
def queue(tmp_path):
    path = tmp_path / 'queue.sqlite'
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE tasks (id TEXT PRIMARY KEY, recipient TEXT, body TEXT, state TEXT,
        created INTEGER, updated INTEGER, attempts INTEGER, lease_until INTEGER, claim_token TEXT, result TEXT);
      CREATE TABLE events (seq INTEGER PRIMARY KEY, task_id TEXT, at INTEGER, event TEXT);
    ''')
    db.close()
    db = w.connect(path)
    yield db
    db.close()


def add(db, task_id, recipient='mistral', body=PREFIX+'simple'):
    db.execute("INSERT INTO tasks VALUES (?,?,?,'pending',1,1,0,NULL,NULL,NULL)", (task_id, recipient, body))


def test_only_project_mistral_claimed(queue):
    add(queue, 'other', body='unrelated')
    add(queue, 'complex', 'codex')
    add(queue, 'local')
    assert w.cycle(queue, PREFIX, (), lambda: True, lambda _: 'Réponse', 1036800) == 'done'
    assert queue.execute("SELECT state FROM tasks WHERE id='local'").fetchone() == ('done',)
    assert queue.execute("SELECT state FROM tasks WHERE id='complex'").fetchone() == ('pending',)
    assert queue.execute("SELECT state FROM tasks WHERE id='other'").fetchone() == ('pending',)


def test_pause_and_resource_fail_closed(queue, tmp_path):
    add(queue, 'a')
    pause = tmp_path / 'pause'
    pause.touch()
    assert w.cycle(queue, PREFIX, (pause,), lambda: True, lambda _: pytest.fail(), 1000) == 'paused_or_resources'
    assert w.cycle(queue, PREFIX, (), lambda: False, lambda _: pytest.fail(), 1000) == 'paused_or_resources'
    assert queue.execute('SELECT count(*) FROM events').fetchone() == (0,)


def test_manual_calls_count_and_interval_spans_midnight(queue):
    add(queue, 'manual')
    queue.execute("INSERT INTO events(task_id,at,event) VALUES ('manual',1036799,'claimed')")
    add(queue, 'new')
    assert w.reserve(queue, PREFIX, 1036801) is None
    assert w.reserve(queue, PREFIX, 1040400) is not None


def test_four_per_day_persist_and_failed_calls_count(queue):
    for i in range(5):
        add(queue, str(i))
    def fail(_):
        raise ValueError('secret')
    for hour in range(4):
        assert w.cycle(queue, PREFIX, (), lambda: True, fail, 1036800 + hour*3600) == 'failed'
    assert w.reserve(queue, PREFIX, 1036800 + 5*3600) is None
    assert queue.execute("SELECT count(*) FROM tasks WHERE state='failed'").fetchone() == (4,)
    assert 'secret' not in str(queue.execute('SELECT result FROM tasks').fetchall())


def test_recovery_only_worker_owned_claims_no_replay(queue):
    add(queue, 'a')
    task = w.reserve(queue, PREFIX, 1036800)
    add(queue, 'other', 'claude')
    queue.execute("UPDATE tasks SET state='running', claim_token='other' WHERE id='other'")
    w.recover(queue, 1036810)
    assert queue.execute("SELECT state,attempts FROM tasks WHERE id=?", (task[0],)).fetchone() == ('failed', 2)
    assert queue.execute("SELECT state FROM tasks WHERE id='other'").fetchone() == ('running',)
    assert w.reserve(queue, PREFIX, 1040400) is None


def test_claim_is_transactional_between_connections(queue, tmp_path):
    add(queue, 'a')
    first = w.reserve(queue, PREFIX, 1036800)
    other = w.connect(tmp_path / 'queue.sqlite')
    try:
        assert first and w.reserve(other, PREFIX, 1036800) is None
    finally:
        other.close()


def test_missing_queue_refused(tmp_path):
    with pytest.raises(ValueError):
        w.connect(tmp_path / 'missing.sqlite')


def test_output_limit_failure_is_distinct_and_does_not_leak(queue):
    add(queue, 'a')
    def incomplete(_):
        raise w.IncompleteResponse('private response content')
    assert w.cycle(queue, PREFIX, (), lambda: True, incomplete, 1036800) == 'failed'
    result = queue.execute("SELECT result FROM tasks WHERE id='a'").fetchone()[0]
    assert 'limite de sortie' in result
    assert 'private response content' not in result


def test_local_call_requests_bounded_output_and_rejects_truncation(monkeypatch):
    import json
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            assert limit == 65537
            return json.dumps({'message': {'content': 'Réponse'}, 'done_reason': 'length'}).encode()
    class Opener:
        def open(self, request, timeout):
            payload = json.loads(request.data)
            assert payload['options']['num_predict'] == 400
            assert payload['options']['num_thread'] == 2
            assert timeout == 150
            return Response()
    monkeypatch.setattr(w.urllib.request, 'build_opener', lambda *args: Opener())
    with pytest.raises(w.IncompleteResponse):
        w.call_local('Exemple')
