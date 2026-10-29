import hashlib
import json
from functools import lru_cache
from uuid import uuid4

from flask import current_app
from redis import Redis
from redis.exceptions import RedisError


CACHE_PREFIX = "ict-coach:topics:v1"
REVISION_KEY = f"{CACHE_PREFIX}:revision"


@lru_cache(maxsize=4)
def redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )


def get_cache_client():
    if not current_app.config.get("TOPIC_CACHE_ENABLED", False):
        return None

    # Ordinary tests must not read or write the real Redis cache.
    if current_app.testing:
        return None

    redis_url = current_app.config.get("TOPIC_CACHE_REDIS_URL")

    if not isinstance(redis_url, str) or not redis_url.strip():
        return None

    return redis_client(redis_url)


def build_topic_cache_key(
    *,
    scope: str,
    endpoint: str,
    search_text: str = "",
    page: int = 1,
):
    client = get_cache_client()

    if client is None:
        return None

    try:
        revision = client.get(REVISION_KEY) or "initial"
    except RedisError:
        current_app.logger.debug(
            "Topic cache unavailable; using database."
        )
        return None

    key_data = json.dumps(
        {
            "scope": scope,
            "endpoint": endpoint,
            "search_text": search_text,
            "page": page,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(
        key_data.encode("utf-8")
    ).hexdigest()

    return f"{CACHE_PREFIX}:{revision}:{digest}"


def get_cached_topics(cache_key):
    if cache_key is None:
        return None

    client = get_cache_client()

    if client is None:
        return None

    try:
        cached = client.get(cache_key)

        if cached is None:
            return None

        payload = json.loads(cached)

        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("topics"), list)
        ):
            return None

        return payload
    except (RedisError, json.JSONDecodeError, TypeError):
        current_app.logger.debug(
            "Topic cache could not be read; using database."
        )
        return None


def cache_topics(cache_key, payload):
    if cache_key is None:
        return

    client = get_cache_client()

    if client is None:
        return

    try:
        ttl = int(
            current_app.config.get(
                "TOPIC_CACHE_TTL_SECONDS",
                300,
            )
        )

        if ttl <= 0:
            return

        client.setex(
            cache_key,
            ttl,
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
    except (RedisError, TypeError, ValueError):
        current_app.logger.debug(
            "Topic cache could not be saved."
        )


def invalidate_topic_cache() -> bool:
    client = get_cache_client()

    if client is None:
        return False

    try:
        # New requests use a new revision.
        # Old cached entries disappear through their existing TTL.
        client.set(REVISION_KEY, str(uuid4()))
        return True
    except RedisError:
        current_app.logger.debug(
            "Topic cache could not be invalidated."
        )
        return False