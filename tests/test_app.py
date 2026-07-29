import base64
import io
import threading
import time
from types import SimpleNamespace

from PIL import Image

import app as street_app
from knowledge_base.street_prompt_data_taiwan import get_taiwan_design_prompt


def setup_function():
    street_app.SESSIONS.clear()
    street_app.RATE_LIMITS.clear()


def make_png(width=1200, height=800):
    output = io.BytesIO()
    Image.new('RGB', (width, height), '#6d806a').save(output, format='PNG')
    return output.getvalue()


def test_health_is_liveness_only(monkeypatch):
    monkeypatch.setattr(street_app, 'client', object())
    monkeypatch.setattr(street_app, 'openai_client', None)

    response = street_app.app.test_client().get('/health')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'
    assert 'providers' not in response.get_json()
    assert response.headers['X-Request-ID']
    assert response.headers['X-Content-Type-Options'] == 'nosniff'


def test_index_renders_both_provider_choices(monkeypatch):
    monkeypatch.setattr(street_app, 'client', object())
    monkeypatch.setattr(street_app, 'openai_client', object())

    response = street_app.app.test_client().get('/')

    assert response.status_code == 200
    assert b'value="gemini"' in response.data
    assert b'value="openai"' in response.data
    assert b'gpt-image-2' in response.data
    assert b'data-preset-id="reduce-motor-traffic"' in response.data
    assert '減少汽機車'.encode() in response.data
    assert b'id="comparison-viewer"' in response.data
    assert b'id="before-image"' in response.data
    assert b'id="comparison-range"' in response.data
    assert b'id="video-launcher"' in response.data
    assert b'id="video-modal"' in response.data
    assert b'name="video-speed"' in response.data
    assert b'name="video-duration"' in response.data
    assert b'name="video-format"' in response.data
    assert '確認影片設定'.encode() in response.data
    assert response.headers['Cache-Control'] == 'no-store'


def test_every_homepage_preset_resolves_to_specialized_prompt():
    for preset_id, option_key in street_app.PRESET_STYLE_KEYS.items():
        prompt, negative_prompt = get_taiwan_design_prompt(
            option_key,
            f'preset {preset_id}',
        )
        assert prompt
        assert negative_prompt
        assert f'preset {preset_id}' in prompt


def test_openai_settings_preserve_orientation_and_valid_multiples():
    landscape = make_png(1600, 900)
    portrait = make_png(900, 1600)
    extra_wide = make_png(3000, 1000)

    landscape_size, landscape_quality = street_app._openai_image_settings(
        landscape, '1K')
    portrait_size, portrait_quality = street_app._openai_image_settings(
        portrait, '2K')
    extra_wide_size, _ = street_app._openai_image_settings(
        extra_wide, '1K')

    landscape_width, landscape_height = map(int, landscape_size.split('x'))
    portrait_width, portrait_height = map(int, portrait_size.split('x'))
    extra_wide_width, extra_wide_height = map(
        int,
        extra_wide_size.split('x'),
    )
    assert landscape_width > landscape_height
    assert portrait_height > portrait_width
    assert all(
        edge % 16 == 0
        for edge in (
            landscape_width,
            landscape_height,
            portrait_width,
            portrait_height,
            extra_wide_width,
            extra_wide_height,
        )
    )
    assert all(
        street_app.OPENAI_MIN_IMAGE_PIXELS <= width * height
        <= street_app.OPENAI_MAX_IMAGE_PIXELS
        for width, height in (
            (landscape_width, landscape_height),
            (portrait_width, portrait_height),
            (extra_wide_width, extra_wide_height),
        )
    )
    assert extra_wide_width / extra_wide_height <= 3
    assert landscape_quality == 'low'
    assert portrait_quality == 'medium'


def test_openai_errors_are_user_actionable():
    cases = [
        (401, None, 503, 'openai_auth_failed'),
        (403, None, 503, 'openai_access_denied'),
        (429, None, 429, 'openai_rate_limited'),
        (400, 'moderation_blocked', 400, 'openai_moderation_blocked'),
        (400, 'invalid_image', 400, 'openai_request_invalid'),
        (500, None, 502, 'openai_upstream_error'),
    ]
    with street_app.app.test_request_context('/api/transform'):
        street_app.g.request_id = 'test-request'
        for status, code, expected_status, expected_code in cases:
            error = SimpleNamespace(
                status_code=status,
                code=code,
                body={},
            )
            response = street_app._openai_generation_error(error)
            assert response.status_code == expected_status
            assert response.get_json()['code'] == expected_code


def test_openai_generation_uses_edit_api(monkeypatch):
    expected = b'generated-png'
    call = {}

    class FakeImages:
        def edit(self, **kwargs):
            call.update(kwargs)
            return SimpleNamespace(data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(expected).decode('ascii')
                )
            ])

    monkeypatch.setattr(
        street_app,
        'openai_client',
        SimpleNamespace(images=FakeImages()),
    )

    result = street_app._generate_image_from_reference(
        make_png(),
        'image/png',
        'Widen the sidewalk',
        resolution='2K',
        provider='openai',
    )

    assert result == expected
    assert call['model'] == street_app.OPENAI_IMAGE_MODEL
    assert call['prompt'] == 'Widen the sidewalk'
    assert call['output_format'] == 'png'
    assert call['image'].name == 'reference.png'


def test_transform_rejects_unconfigured_provider(monkeypatch):
    monkeypatch.setattr(street_app, 'openai_client', None)

    response = street_app.app.test_client().post(
        '/api/transform',
        data={
            'image': (io.BytesIO(make_png()), 'street.png'),
            'custom_prompt': '增加人行道',
            'provider': 'openai',
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 503
    assert 'OPENAI_API_KEY' not in response.get_data(as_text=True)
    assert '尚未設定 API Key' in response.get_json()['error']
    assert response.get_json()['code'] == 'provider_unavailable'


def test_transform_keeps_provider_for_followup_edits(monkeypatch):
    image_bytes = make_png()
    generation_call = {}
    persisted = {}
    monkeypatch.setattr(street_app, 'openai_client', object())
    monkeypatch.setattr(
        street_app,
        '_generate_image_from_reference',
        lambda *args, **kwargs: generation_call.update(kwargs) or image_bytes,
    )
    monkeypatch.setattr(
        street_app,
        '_save_generated_image',
        lambda *args: (
            '/static/generated/test/v1.png',
            {
                'url': '/static/generated/test/v1.png',
                'bytes': image_bytes,
                'mime_type': 'image/png',
            },
        ),
    )
    monkeypatch.setattr(
        street_app,
        '_generate_copilot_greeting',
        lambda *args: {
            'message': '完成第一版',
            'suggestions': ['多一點樹'],
        },
    )
    monkeypatch.setattr(
        street_app,
        '_persist_session',
        lambda session_id, session: persisted.update({
            'session_id': session_id,
            'session': session,
        }),
    )
    response = street_app.app.test_client().post(
        '/api/transform',
        data={
            'image': (io.BytesIO(image_bytes), 'street.png'),
            'custom_prompt': '增加人行道',
            'resolution': '2K',
            'provider': 'openai',
        },
        content_type='multipart/form-data',
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['provider'] == 'openai'
    assert generation_call['provider'] == 'openai'
    assert street_app.SESSIONS[payload['session_id']]['provider'] == 'openai'
    assert persisted['session_id'] == payload['session_id']
    assert persisted['session']['history'][-1]['message'] == '完成第一版'


def test_transform_rejects_fake_image_bytes(monkeypatch):
    monkeypatch.setattr(street_app, 'openai_client', object())

    response = street_app.app.test_client().post(
        '/api/transform',
        data={
            'image': (io.BytesIO(b'<script>not an image</script>'), 'street.png'),
            'custom_prompt': '增加人行道',
            'provider': 'openai',
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 400
    assert response.get_json()['code'] == 'image_invalid'


def test_prompt_and_chat_length_limits(monkeypatch):
    monkeypatch.setattr(street_app, 'openai_client', object())
    monkeypatch.setattr(street_app, 'client', object())
    client = street_app.app.test_client()

    prompt_response = client.post(
        '/api/transform',
        data={
            'image': (io.BytesIO(make_png()), 'street.png'),
            'custom_prompt': 'a' * (street_app.MAX_PROMPT_CHARS + 1),
            'provider': 'openai',
        },
        content_type='multipart/form-data',
    )
    chat_response = client.post(
        '/api/chat',
        json={
            'session_id': 'abcdef123456',
            'message': 'a' * (street_app.MAX_CHAT_CHARS + 1),
        },
    )

    assert prompt_response.status_code == 400
    assert prompt_response.get_json()['code'] == 'prompt_too_long'
    assert chat_response.status_code == 400
    assert chat_response.get_json()['code'] == 'message_too_long'


def test_api_404_and_413_are_json(monkeypatch):
    client = street_app.app.test_client()

    missing = client.get('/api/does-not-exist')
    assert missing.status_code == 404
    assert missing.is_json
    assert missing.get_json()['code'] == 'not_found'

    monkeypatch.setitem(street_app.app.config, 'MAX_CONTENT_LENGTH', 100)
    oversized = client.post(
        '/api/transform',
        data={'image': (io.BytesIO(b'x' * 1_000), 'street.jpg')},
        content_type='multipart/form-data',
    )
    assert oversized.status_code == 413
    assert oversized.is_json
    assert oversized.get_json()['code'] == 'payload_too_large'


def test_generation_rate_limit_returns_retry_after(monkeypatch):
    monkeypatch.setattr(street_app, 'MAX_GENERATIONS_PER_HOUR', 1)
    client = street_app.app.test_client()

    first = client.post('/api/transform')
    second = client.post('/api/transform')

    assert first.status_code == 400
    assert second.status_code == 429
    assert second.get_json()['code'] == 'rate_limited'
    assert int(second.headers['Retry-After']) > 0


def test_diag_requires_token_when_configured(monkeypatch):
    monkeypatch.setattr(street_app, 'DIAG_TOKEN', 'diagnostic-secret')
    client = street_app.app.test_client()

    denied = client.get('/api/diag')
    allowed = client.get(
        '/api/diag',
        headers={'X-Diag-Token': 'diagnostic-secret'},
    )

    assert denied.status_code == 403
    assert denied.get_json()['code'] == 'diag_forbidden'
    assert allowed.status_code == 200
    assert 'providers' in allowed.get_json()


def test_model_ping_is_disabled_without_diag_token(monkeypatch):
    monkeypatch.setattr(street_app, 'DIAG_TOKEN', '')

    response = street_app.app.test_client().get('/api/diag?models=1')

    assert response.status_code == 403
    assert response.get_json()['code'] == 'diag_token_required'


def test_street_view_url_allowlist_is_exact():
    assert street_app._is_allowed_street_view_url(
        'https://maps.googleapis.com/maps/api/streetview?size=640x400'
    )
    assert not street_app._is_allowed_street_view_url(
        'https://maps.googleapis.com.evil.example/maps/api/streetview'
    )
    assert not street_app._is_allowed_street_view_url(
        'https://maps.googleapis.com/maps/api/streetview/metadata'
    )


def test_expired_session_is_removed(monkeypatch):
    monkeypatch.setattr(street_app, 'client', object())
    session_id = 'abcdef123456'
    street_app.SESSIONS[session_id] = {
        'versions': [{'bytes': make_png(), 'mime_type': 'image/png'}],
        'history': [],
        'updated_at': time.time() - street_app.SESSION_TTL_SECONDS - 1,
        '_operation_lock': threading.Lock(),
    }

    response = street_app.app.test_client().post(
        '/api/chat',
        json={'session_id': session_id, 'message': '再多一些樹'},
    )

    assert response.status_code == 404
    assert response.get_json()['code'] == 'session_expired'
    assert session_id not in street_app.SESSIONS


def test_session_history_is_bounded():
    session = {'history': [], 'updated_at': time.time()}

    with street_app.SESSIONS_LOCK:
        for index in range(street_app.MAX_HISTORY_TURNS + 5):
            street_app._append_history_locked(
                session,
                'user',
                f'message-{index}',
            )

    assert len(session['history']) == street_app.MAX_HISTORY_TURNS
    assert session['history'][0]['message'] == 'message-5'


def test_busy_session_rejects_parallel_chat(monkeypatch):
    monkeypatch.setattr(street_app, 'client', object())
    session_id = 'abcdef123456'
    operation_lock = threading.Lock()
    operation_lock.acquire()
    street_app.SESSIONS[session_id] = {
        'versions': [{'bytes': make_png(), 'mime_type': 'image/png'}],
        'history': [],
        'created_at': time.time(),
        'updated_at': time.time(),
        '_operation_lock': operation_lock,
    }

    try:
        response = street_app.app.test_client().post(
            '/api/chat',
            json={'session_id': session_id, 'message': '再多一些樹'},
        )
    finally:
        operation_lock.release()

    assert response.status_code == 409
    assert response.get_json()['code'] == 'session_busy'


def test_chat_caps_versions_and_keeps_monotonic_version(monkeypatch):
    persisted = {}
    monkeypatch.setattr(street_app, 'client', object())
    monkeypatch.setattr(
        street_app,
        '_decide_copilot_response',
        lambda *args: {
            'intent': 'refine',
            'message': '我來加一些樹。',
            'refine_prompt': 'Add more trees',
            'suggestions': [],
        },
    )
    monkeypatch.setattr(
        street_app,
        '_generate_image_from_reference',
        lambda *args, **kwargs: make_png(),
    )
    monkeypatch.setattr(
        street_app,
        '_save_generated_image',
        lambda *args: (
            '/static/generated/test/v13.png',
            {
                'url': '/static/generated/test/v13.png',
                'bytes': make_png(),
                'mime_type': 'image/png',
            },
        ),
    )
    monkeypatch.setattr(
        street_app,
        '_persist_session',
        lambda session_id, session: persisted.update({
            'session_id': session_id,
            'version_count': session['version_count'],
        }),
    )
    session_id = 'abcdef123456'
    street_app.SESSIONS[session_id] = {
        'versions': [
            {'bytes': make_png(), 'mime_type': 'image/png'}
            for _ in range(street_app.MAX_SESSION_VERSIONS)
        ],
        'history': [],
        'initial_prompt': '綠化',
        'resolution': '2K',
        'provider': 'gemini',
        'version_count': 12,
        'created_at': time.time(),
        'updated_at': time.time(),
        '_operation_lock': threading.Lock(),
    }

    response = street_app.app.test_client().post(
        '/api/chat',
        json={'session_id': session_id, 'message': '再多一些樹'},
    )

    assert response.status_code == 200
    assert response.get_json()['version'] == 13
    assert street_app.SESSIONS[session_id]['version_count'] == 13
    assert len(street_app.SESSIONS[session_id]['versions']) == (
        street_app.MAX_SESSION_VERSIONS
    )
    assert persisted == {
        'session_id': session_id,
        'version_count': 13,
    }


def test_session_serialization_round_trip_uses_json_and_recreates_lock():
    image_bytes = make_png()
    session = {
        'versions': [{
            'url': '/static/generated/test/v1.png',
            'bytes': image_bytes,
            'mime_type': 'image/png',
        }],
        'history': [{'role': 'assistant', 'message': '第一版完成'}],
        'initial_prompt': '增加樹木',
        'resolution': '2K',
        'provider': 'openai',
        'version_count': 1,
        'created_at': 100.0,
        'updated_at': 200.0,
        '_operation_lock': threading.Lock(),
    }

    raw = street_app._serialize_session(session)
    restored = street_app._deserialize_session(raw)

    assert raw.startswith(b'{')
    assert b'_operation_lock' not in raw
    assert restored['versions'][0]['bytes'] == image_bytes
    assert restored['provider'] == 'openai'
    assert restored['history'] == session['history']
    assert isinstance(restored['_operation_lock'], type(threading.Lock()))


def test_get_session_loads_redis_state_into_local_cache(monkeypatch):
    session_id = 'abcdef123456'
    raw = street_app._serialize_session({
        'versions': [{
            'url': '/generated/v1.png',
            'bytes': make_png(),
            'mime_type': 'image/png',
        }],
        'history': [],
        'initial_prompt': '綠化',
        'version_count': 1,
        'created_at': time.time(),
        'updated_at': time.time(),
    })

    class FakeRedis:
        def get(self, key):
            assert key.endswith(session_id)
            return raw

        def expire(self, key, ttl):
            assert ttl == street_app.SESSION_TTL_SECONDS
            return True

        def zadd(self, key, mapping):
            assert session_id in mapping

        def zrem(self, *args):
            raise AssertionError('valid session should not be removed')

    monkeypatch.setattr(street_app, 'redis_client', FakeRedis())

    restored = street_app._get_session(session_id)

    assert restored is street_app.SESSIONS[session_id]
    assert restored['initial_prompt'] == '綠化'
    assert restored['versions'][0]['mime_type'] == 'image/png'


def test_refresh_after_distributed_lock_uses_latest_redis_state(monkeypatch):
    session_id = 'abcdef123456'
    stale = {
        'versions': [{
            'url': '/generated/v1.png',
            'bytes': make_png(),
            'mime_type': 'image/png',
        }],
        'history': [{'role': 'assistant', 'message': 'stale'}],
        '_operation_lock': threading.Lock(),
    }
    raw = street_app._serialize_session({
        **stale,
        'history': [{'role': 'assistant', 'message': 'latest'}],
        'version_count': 1,
        'created_at': time.time(),
        'updated_at': time.time(),
    })

    class FakeRedis:
        def get(self, key):
            return raw

    monkeypatch.setattr(street_app, 'redis_client', FakeRedis())

    refreshed = street_app._refresh_persisted_session(
        session_id,
        stale,
    )

    assert refreshed['history'][0]['message'] == 'latest'
    assert street_app.SESSIONS[session_id] is refreshed


def test_redis_rate_limit_uses_hashed_client_identifier(monkeypatch):
    calls = []

    class FakeRedis:
        def eval(self, script, key_count, key, window):
            calls.append((script, key_count, key, window))
            return [len(calls), window]

    monkeypatch.setattr(street_app, 'redis_client', FakeRedis())
    monkeypatch.setattr(street_app, 'MAX_GENERATIONS_PER_HOUR', 1)
    client = street_app.app.test_client()

    first = client.post('/api/transform')
    second = client.post('/api/transform')

    assert first.status_code == 400
    assert second.status_code == 429
    assert second.get_json()['code'] == 'rate_limited'
    assert '127.0.0.1' not in calls[0][2]
    assert calls[0][2].startswith(
        f'{street_app.STATE_KEY_PREFIX}:rate:transform:'
    )


def test_redis_session_lock_is_token_checked_on_release(monkeypatch):
    calls = {}

    class FakeRedis:
        def set(self, key, token, **kwargs):
            calls['set'] = (key, token, kwargs)
            return True

        def eval(self, script, key_count, key, token):
            calls['eval'] = (script, key_count, key, token)
            return 1

    monkeypatch.setattr(street_app, 'redis_client', FakeRedis())
    session = {'_operation_lock': threading.Lock()}

    handle = street_app._acquire_session_operation(
        'abcdef123456',
        session,
    )
    street_app._release_session_operation(handle)

    lock_key, token, options = calls['set']
    assert options == {
        'nx': True,
        'ex': street_app.SESSION_LOCK_SECONDS,
    }
    assert calls['eval'][2:] == (lock_key, token)
    assert "redis.call('GET'" in calls['eval'][0]


def test_diag_reports_redis_state_backend(monkeypatch):
    class FakeRedis:
        def zremrangebyscore(self, *args):
            return 0

        def zcard(self, key):
            return 3

    monkeypatch.setattr(street_app, 'redis_client', FakeRedis())
    monkeypatch.setattr(street_app, 'DIAG_TOKEN', '')

    response = street_app.app.test_client().get('/api/diag')

    assert response.status_code == 200
    assert response.get_json()['state_backend'] == 'redis'
    assert response.get_json()['sessions'] == 3
