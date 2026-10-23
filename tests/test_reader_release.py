import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

_test_root = tempfile.TemporaryDirectory()
os.environ.update(DATA_DIR=_test_root.name, LANCEDB_DIR=str(Path(_test_root.name) / 'index'), ADMIN_PASSWORD='test-admin-password', CHAT_SESSION_SECRET='test-session-secret-do-not-deploy')

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import main, reader_data, chat_access, generation, retrieval
from app.editorial_report import build_report
from app.public_content import is_public_content

PUBLIC = {'id': 'public', 'title': 'Heat pump guide', 'text': 'Public heat pump advice.', 'url': 'https://www.greenbuildermedia.com/blog/heat-pumps', 'visibility': 'public', 'surface_policy': 'public', 'score': 1.0}
PRIVATE = dict(PUBLIC, id='secret', text='CONFIDENTIAL-SENTINEL', visibility='private', surface_policy='paraphrase')
ORIGINAL_SHEET_WRITER = main.log_to_google_sheet


def test_render_fingerprint_uses_edge_address_not_forwarded_client(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setenv('RENDER', 'true')
    def request(client_ip, edge_ip):
        return Request({'type': 'http', 'client': (client_ip, 0), 'headers': [
            (b'cf-connecting-ip', edge_ip.encode()),
            (b'x-forwarded-for', client_ip.encode()),
        ]})
    first = chat_access.fingerprint(request('198.51.100.1', '203.0.113.10'))
    assert chat_access.fingerprint(request('198.51.100.2', '203.0.113.10')) == first
    assert chat_access.fingerprint(request('198.51.100.1', '203.0.113.11')) != first


@pytest.mark.parametrize('edge_ip', ['', 'not-an-ip', '203.0.113.1, 203.0.113.2'])
def test_render_missing_or_invalid_edge_identity_fails_closed(monkeypatch, edge_ip):
    from starlette.requests import Request
    monkeypatch.setenv('RENDER', 'true')
    request = Request({'type': 'http', 'client': ('198.51.100.1', 0),
                       'headers': [(b'cf-connecting-ip', edge_ip.encode())]})
    with pytest.raises(HTTPException) as error:
        chat_access.fingerprint(request)
    assert error.value.status_code == 503


def test_non_render_ignores_edge_headers(monkeypatch):
    from starlette.requests import Request
    monkeypatch.delenv('RENDER', raising=False)
    def request(edge_ip):
        return Request({'type': 'http', 'client': ('198.51.100.1', 0),
                        'headers': [(b'cf-connecting-ip', edge_ip.encode())]})
    assert chat_access.fingerprint(request('203.0.113.10')) == chat_access.fingerprint(request('203.0.113.11'))


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(main.settings, 'data_dir', tmp_path)
    monkeypatch.setattr(main.settings, 'lancedb_dir', tmp_path / 'index')
    monkeypatch.setattr(main, 'CHAT_RESPONSE_CACHE_DIR', tmp_path / 'cache')
    monkeypatch.setattr(main, 'log_to_google_sheet', Mock())


def event(question='Can I afford a heat pump?', sid='web-reader', **kwargs):
    return reader_data.append_event(dict(question=question, answer='Public advice', session_id=sid, public_sources=[{'url': PUBLIC['url']}], **kwargs))


def session(client):
    response = client.post('/api/chat-session', headers={'Origin': 'https://www.greenbuildermedia.com'})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize('chunk', [PRIVATE, dict(PUBLIC, surface_policy='weight_only'), dict(PUBLIC, surface_policy='blocked'), dict(PUBLIC, visibility=None), dict(PUBLIC, source_type='draft_html'), dict(PUBLIC, url='https://www.greenbuildermedia.com/_hcms/preview/a'), dict(PUBLIC, url='https://www.greenbuildermedia.com.evil.test/blog/a')])
def test_private_boundary(chunk):
    assert not is_public_content(chunk)
    assert generation.build_context([chunk]) == ''
    assert main._magazine_card_from_chunk(chunk) is None


def test_generation_never_receives_private_text(monkeypatch):
    completion = Mock(return_value='Public answer')
    monkeypatch.setattr(generation, 'chat_completion', completion)
    assert generation.answer_question('heat pumps', [PRIVATE]) == "I couldn't find approved public Green Builder Media content for that question."
    completion.assert_not_called()
    generation.answer_question('heat pumps', [PUBLIC, PRIVATE])
    assert 'CONFIDENTIAL-SENTINEL' not in str(completion.call_args)


def test_actual_vector_prefilter(monkeypatch, tmp_path):
    import lancedb
    db = lancedb.connect(str(tmp_path / 'vector-test'))
    table = db.create_table('greenbuilder_chunks', [dict(PUBLIC, vector=[0.1, 0.2]), dict(PRIVATE, vector=[0.1, 0.2])])
    monkeypatch.setattr(retrieval, 'get_table', lambda: table)
    monkeypatch.setattr(retrieval, 'embed_query', lambda question: [0.1, 0.2])
    assert [row['id'] for row in retrieval.search('heat pump')] == ['public']


def test_durable_concurrent_logging_and_retry():
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: event(sid=f'web-{i}'), range(40)))
    assert len(reader_data.read_events()) == 40
    failure = Mock(side_effect=RuntimeError('secret provider details'))
    reader_data.flush_outbox(failure)
    assert reader_data.logging_status()['pending'] == 40
    assert 'secret provider' not in reader_data.logging_status()['last_error']
    delivered = []
    reader_data.flush_outbox(delivered.append, limit=100, force=True)
    assert len(delivered) == 40
    assert reader_data.logging_status()['pending'] == 0
    reader_data.flush_outbox(delivered.append, force=True)
    assert len(delivered) == 40


def test_report_redacts_and_counts_sessions():
    event('Can I afford a heat pump? Email jane@example.com', sid='web-a')
    event('Can I afford a heat pump? Email jane@example.com', sid='web-a')
    event('What panel upgrade does a heat pump need?', sid='web-a')
    event('What do heat pumps cost?', sid='web-b')
    event('heat pump', sid='codex-diagnostic')
    report = build_report()
    assert report['questions'] == 3
    assert report['sessions'] == 2
    assert report['excluded'] == {'test': 1, 'repeat': 1}
    assert 'jane@example.com' not in str(report)
    assert len(report['journeys']) == 1
    assert report['themes'][0]['sessions'] == 2


def test_admin_and_proxy_authentication():
    client = TestClient(main.app)
    for path in ['/api/admin/logs', '/api/admin/editorial-report', '/api/cognition/image/example']:
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'
    assert client.post('/admin/upload-magazine', files={'files': ('test.pdf', b'%PDF-test')}).status_code == 401
    assert client.post('/admin/upload-magazine', content=b'invalid-body').status_code == 401
    response = client.get('/api/admin/editorial-report', auth=('editor', 'test-admin-password'))
    assert response.status_code == 200
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def test_session_tokens_origins_and_limits(monkeypatch):
    client = TestClient(main.app)
    assert client.post('/chat', json={'question': 'heat pumps'}).status_code == 401
    assert client.post('/api/chat-session', headers={'Origin': 'https://evil.example'}).status_code == 403
    token = session(client)['token']
    assert client.post('/chat', json={'question': 'heat pumps'}, headers={'X-Chat-Token': token + 'bad'}).status_code == 401
    assert client.get('/api/related-cards', headers={'X-Chat-Token': token, 'User-Agent': 'crawler'}).status_code == 403
    assert client.get('/api/related-cards', headers={'X-Chat-Token': token, 'User-Agent': 'Googlebot/2.1'}).status_code == 403
    monkeypatch.setenv('CHAT_REQUESTS_PER_MINUTE', '1')
    assert client.post('/chat', json={'question': 'heat pumps'}, headers={'X-Chat-Token': token}).status_code == 429


def test_public_chat_filters_private_and_logs_cache_hits(monkeypatch):
    client = TestClient(main.app, headers={'User-Agent': 'Mozilla/5.0'})
    sid = session(client)
    monkeypatch.setattr(main, 'search', lambda q: [dict(PUBLIC), dict(PRIVATE)])
    generator = Mock(return_value='Heat pumps can reduce energy use.')
    monkeypatch.setattr(main, 'answer_question', generator)
    monkeypatch.setattr(main, '_chat_payload', lambda response, *args, **kwargs: response.model_dump())
    headers = {'X-Chat-Token': sid['token']}
    for _ in range(2):
        response = client.post('/chat', headers=headers, json={'question': 'How do heat pumps work?', 'session_id': 'forged-session'})
        assert response.status_code == 200, response.text
        assert 'CONFIDENTIAL-SENTINEL' not in response.text
    assert len(generator.call_args.args[1]) == 1
    assert generator.call_count == 1
    logs = reader_data.read_events()
    assert len(logs) == 2
    assert {row['session_id'] for row in logs} == {sid['session_id']}
    assert any(row.get('cache_hit') for row in logs)


def test_year_is_not_an_event_query():
    assert not main.is_future_event_query('What articles are in Q3 2026?')
    assert main.is_future_event_query('When is the next conference?')


def test_internal_editor_note_is_not_public(monkeypatch):
    client = TestClient(main.app)
    token = session(client)['token']
    monkeypatch.setattr(main, 'find_correction', lambda q: {'answer_override': 'Approved correction.', 'editor_note': 'CONFIDENTIAL-SENTINEL'})
    monkeypatch.setattr(main, '_chat_payload', lambda response, *args, **kwargs: response.model_dump())
    response = client.post('/chat', json={'question': 'heat pumps'}, headers={'X-Chat-Token': token})
    assert response.status_code == 200
    assert 'CONFIDENTIAL-SENTINEL' not in response.text


def test_unpublished_transcript_is_not_exposed(monkeypatch):
    monkeypatch.setattr(main, '_hubspot_transcript_url_for_video', lambda video_id: '')
    client = TestClient(main.app)
    for path in ['/api/youtube-transcript/secret', '/api/youtube-transcript-html/secret']:
        assert client.get(path).status_code == 404


def test_rate_limit_error_has_cors_and_retry_header(monkeypatch):
    monkeypatch.setenv('CHAT_REQUESTS_PER_MINUTE', '0')
    client = TestClient(main.app)
    response = client.post('/chat', json={'question': 'heat pumps'}, headers={'Origin':'https://www.greenbuildermedia.com'})
    assert response.status_code == 429
    assert response.headers['access-control-allow-origin'] == 'https://www.greenbuildermedia.com'
    assert int(response.headers['retry-after']) > 0


def test_expired_token_and_forged_forwarded_header(monkeypatch):
    client = TestClient(main.app)
    token = session(client)['token']
    monkeypatch.setattr(chat_access.time, 'time', lambda: 99999999999)
    with pytest.raises(HTTPException) as exc:
        chat_access.verify_token(token)
    assert exc.value.status_code == 401
    from starlette.requests import Request
    scope = {'type':'http','method':'POST','path':'/chat','headers':[], 'client':('203.0.113.8',1234)}
    a = chat_access.fingerprint(Request(scope))
    scope['headers'] = [(b'x-forwarded-for', b'1.2.3.4')]
    assert a == chat_access.fingerprint(Request(scope))


def test_sheet_delivery_preserves_event_id_and_detects_duplicates(monkeypatch):
    sheet = Mock()
    sheet.row_values.return_value = []
    sheet.col_values.return_value = []
    monkeypatch.setattr(main, 'get_google_sheet', lambda: sheet)
    writer = ORIGINAL_SHEET_WRITER
    writer({'id': 'event-123', 'question': 'heat pumps'})
    assert sheet.append_row.call_args.args[0][-1] == 'event-123'
    sheet.col_values.return_value = ['event-123']
    writer({'id': 'event-123'})
    assert sheet.append_row.call_count == 1
