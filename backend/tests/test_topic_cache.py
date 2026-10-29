import json
from unittest.mock import Mock

import pytest
from flask_jwt_extended import create_access_token
from redis.exceptions import ConnectionError

from extensions import db
from models.topic import Topic
from models.user import User
from services import topic_cache_service as cache


@pytest.fixture()
def fake_redis(app, monkeypatch):
    values = {}
    client = Mock()
    client.get.side_effect = lambda key: values.get(key)

    def set_value(key, value):
        values[key] = value
        return True

    def set_expiring(key, ttl, value):
        values[key] = value
        return True

    client.set.side_effect = set_value
    client.setex.side_effect = set_expiring

    monkeypatch.setattr(
        cache,
        "get_cache_client",
        lambda: client,
    )

    app.config["TOPIC_CACHE_TTL_SECONDS"] = 300

    return client


def user_headers(
    level: str | None = "ssc",
    role: str = "student",
):
    user = User(
        name="Cache Test User",
        email=f"cache-{role}-{level}@example.com",
        password_hash="unused-password-hash",
        role=role,
        academic_level=level if role == "student" else None,
    )
    user.is_email_verified = True
    db.session.add(user)
    db.session.commit()

    token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "token_version": user.token_version,
        },
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def cache_topics(app):
    db.session.add_all([
        Topic(
            title="SSC Save Practice",
            slug="cache-ssc-save",
            description="Document saving.",
            display_order=1,
            subject="ict",
            academic_level="ssc",
        ),
        Topic(
            title="HSC Binary Practice",
            slug="cache-hsc-binary",
            description="Binary numbers.",
            display_order=1,
            subject="ict",
            academic_level="hsc",
        ),
    ])
    db.session.commit()


@pytest.mark.parametrize(
    "path",
    ["/api/topics", "/api/topics/search?q=Save&page=1"],
)
def test_cache_hit_skips_topic_database_query(
    app, client, fake_redis, cache_topics, monkeypatch, path
):
    headers = user_headers()

    first = client.get(path, headers=headers)
    assert first.status_code == 200
    assert first.get_json()["topics"]
    fake_redis.setex.assert_called_once()
    assert fake_redis.setex.call_args.args[1] == 300

    topic_query = Mock(
        side_effect=AssertionError(
            "Cache hit must not query topic rows."
        )
    )
    monkeypatch.setattr(db.session, "scalars", topic_query)

    second = client.get(path, headers=headers)

    assert second.status_code == 200
    assert second.get_json() == first.get_json()
    topic_query.assert_not_called()


def test_cache_keeps_student_levels_and_teacher_separate(
    app, client, fake_redis, cache_topics
):
    ssc_headers = user_headers("ssc")
    hsc_headers = user_headers("hsc")
    teacher_headers = user_headers(role="teacher")

    for headers, expected_slugs in (
        (ssc_headers, ["cache-ssc-save"]),
        (hsc_headers, ["cache-hsc-binary"]),
        (teacher_headers, ["cache-ssc-save", "cache-hsc-binary"]),
    ):
        for _ in range(2):
            response = client.get("/api/topics", headers=headers)
            assert response.status_code == 200
            assert [
                topic["slug"]
                for topic in response.get_json()["topics"]
            ] == expected_slugs

    assert fake_redis.setex.call_count == 3


def test_cache_keys_separate_endpoint_search_and_page(
    app, fake_redis
):
    base = {
        "scope": "student:ssc",
        "endpoint": "search",
        "search_text": "Save",
        "page": 1,
    }

    keys = [
        cache.build_topic_cache_key(**base),
        cache.build_topic_cache_key(
            **{**base, "endpoint": "list"}
        ),
        cache.build_topic_cache_key(
            **{**base, "search_text": "Binary"}
        ),
        cache.build_topic_cache_key(
            **{**base, "page": 2}
        ),
    ]

    assert len(set(keys)) == 4


def test_redis_failure_falls_back_to_database(
    app, client, fake_redis, cache_topics
):
    headers = user_headers()
    fake_redis.get.side_effect = ConnectionError("Unavailable")

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 200
    assert [
        topic["slug"]
        for topic in response.get_json()["topics"]
    ] == ["cache-ssc-save"]
    fake_redis.setex.assert_not_called()


def test_cache_write_failure_does_not_break_response(
    app, client, fake_redis, cache_topics
):
    headers = user_headers()
    fake_redis.setex.side_effect = ConnectionError("Unavailable")

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["topics"]


@pytest.mark.parametrize(
    "cached_value",
    ["invalid JSON", "[]", '{"topics":"invalid"}'],
)
def test_invalid_cached_data_is_a_cache_miss(
    app, fake_redis, cached_value
):
    fake_redis.get.side_effect = None
    fake_redis.get.return_value = cached_value

    assert cache.get_cached_topics("test-key") is None


def test_invalidation_changes_keys(
    app, fake_redis
):
    old_key = cache.build_topic_cache_key(
        scope="student:ssc",
        endpoint="list",
    )
    payload = {"topics": []}
    cache.cache_topics(old_key, payload)

    assert cache.get_cached_topics(old_key) == payload
    assert cache.invalidate_topic_cache() is True

    new_key = cache.build_topic_cache_key(
        scope="student:ssc",
        endpoint="list",
    )

    assert new_key != old_key
    assert cache.get_cached_topics(new_key) is None


def test_unauthenticated_request_does_not_read_cache(
    client, fake_redis
):
    response = client.get("/api/topics")

    assert response.status_code == 401
    fake_redis.get.assert_not_called()
    fake_redis.setex.assert_not_called()


def test_invalid_search_does_not_read_cache(
    app, client, fake_redis
):
    headers = user_headers()

    response = client.get(
        "/api/topics/search",
        headers=headers,
        query_string={"q": "a" * 101},
    )

    assert response.status_code == 400
    fake_redis.get.assert_not_called()


def test_missing_student_level_does_not_read_cache(
    app, client, fake_redis
):
    headers = user_headers(level=None)

    response = client.get("/api/topics", headers=headers)

    assert response.status_code == 409
    fake_redis.get.assert_not_called()


def test_ordinary_tests_never_connect_to_real_redis(
    app, monkeypatch
):
    app.config["TOPIC_CACHE_ENABLED"] = True
    factory = Mock()
    monkeypatch.setattr(cache, "redis_client", factory)

    assert cache.get_cache_client() is None
    factory.assert_not_called()


def test_disabled_cache_never_connects_to_redis(
    app, monkeypatch
):
    app.config["TOPIC_CACHE_ENABLED"] = False
    factory = Mock()
    monkeypatch.setattr(cache, "redis_client", factory)

    assert cache.get_cache_client() is None
    factory.assert_not_called()