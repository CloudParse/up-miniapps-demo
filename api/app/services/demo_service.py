"""A tiny end-to-end example of the three DEV resources.

One row in PostgreSQL, one counter in the cache, one object in the bucket. Delete it
(and its route, schema, tests and the mini-app card) when you start your own features,
and before you ship: the route is not served when ``environment`` is ``production``.
It shows the pattern: a service that knows nothing about HTTP, built from the
configuration, with every resource optional.

The DEV database role owns its own database, so it may create the table below.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
import psycopg
import redis
from botocore.config import Config as BotoConfig
from psycopg import errors as pg_errors

from app.core.config import Config
from app.schemas.demo import DemoVisit
from app.services.resource_probes import TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

SCHEMA_ATTEMPTS = 5
SCHEMA_PAUSE_SECONDS = 1.0

# Each action takes the visitor's id and returns what it read back.
RecordDatabase = Callable[[str], int]
RecordCache = Callable[[str], int]
RecordStorage = Callable[[str], str]


@dataclass(frozen=True)
class DemoActions:
    database: RecordDatabase | None
    cache: RecordCache | None
    storage: RecordStorage | None
    # Creates the table once, at startup (None: no database).
    prepare: Callable[[], None] | None = None

    @classmethod
    def from_config(cls, config: Config) -> DemoActions:
        db_url = config.database.url.get_secret_value()
        cache_url = config.cache.url.get_secret_value()
        prefix = config.cache.key_prefix
        storage = config.storage
        return cls(
            database=(lambda user: _record_database(db_url, user)) if db_url else None,
            cache=(lambda user: _record_cache(cache_url, prefix, user))
            if cache_url
            else None,
            storage=(lambda user: _record_storage(config, user))
            if storage.endpoint and storage.bucket
            else None,
            prepare=(lambda: _ensure_schema(db_url)) if db_url else None,
        )


class DemoService:
    def __init__(self, actions: DemoActions) -> None:
        self._actions = actions

    def record_visit(self, user_id: str) -> DemoVisit:
        a = self._actions
        return DemoVisit(
            database_visits=a.database(user_id) if a.database else None,
            cache_visits=a.cache(user_id) if a.cache else None,
            storage_object=a.storage(user_id) if a.storage else None,
        )


def prepare(actions: DemoActions) -> None:
    """Startup hook: create the table once. Never stops the API from starting."""
    if actions.prepare is None:
        return
    for attempt in range(1, SCHEMA_ATTEMPTS + 1):
        try:
            actions.prepare()
        except Exception:  # noqa: BLE001 - the database may start after the API
            logger.warning(
                "demo table not created (attempt %d)", attempt, exc_info=True
            )
            time.sleep(SCHEMA_PAUSE_SECONDS)
        else:
            return


def _ensure_schema(url: str) -> None:
    try:
        with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS demo_visits ("
                "id bigserial PRIMARY KEY, user_id text NOT NULL, "
                "visited_at timestamptz NOT NULL DEFAULT now())"
            )
    except pg_errors.UniqueViolation, pg_errors.DuplicateTable:
        # Two replicas creating it at the same moment: the other one won.
        return


def _record_database(url: str, user_id: str) -> int:
    try:
        return _insert_visit(url, user_id)
    except pg_errors.UndefinedTable:
        # The table was not there at startup (database not ready yet): once, here.
        _ensure_schema(url)
        return _insert_visit(url, user_id)


def _insert_visit(url: str, user_id: str) -> int:
    with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
        connection.execute("INSERT INTO demo_visits (user_id) VALUES (%s)", (user_id,))
        row = connection.execute("SELECT count(*) FROM demo_visits").fetchone()
        return int(row[0]) if row else 0


def cache_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(
        url, socket_connect_timeout=TIMEOUT_SECONDS, socket_timeout=TIMEOUT_SECONDS
    )


def storage_client(config: Config) -> Any:  # noqa: ANN401 - boto3 clients are untyped
    storage = config.storage
    return boto3.client(
        "s3",
        endpoint_url=storage.endpoint,
        aws_access_key_id=storage.access_key,
        aws_secret_access_key=storage.secret_key.get_secret_value(),
        config=BotoConfig(
            connect_timeout=TIMEOUT_SECONDS,
            read_timeout=TIMEOUT_SECONDS,
            retries={"max_attempts": 1},
            s3={"addressing_style": "path"},
        ),
    )


def visits_cache_key(key_prefix: str) -> str:
    # Every key starts with the mini-app's prefix: the cache user may touch
    # nothing else.
    return f"{key_prefix}demo:visits"


def _record_cache(url: str, key_prefix: str, user_id: str) -> int:
    client = cache_client(url)
    try:
        return int(client.incr(visits_cache_key(key_prefix)))
    finally:
        client.close()


def _record_storage(config: Config, user_id: str) -> str:
    storage = config.storage
    client = storage_client(config)
    # One object per user (the id of the verified token): nobody reads another's.
    key = f"demo/{user_id}.json"
    body = json.dumps({"user": user_id, "at": datetime.now(UTC).isoformat()}).encode()
    client.put_object(
        Bucket=storage.bucket, Key=key, Body=body, ContentType="application/json"
    )
    stored = client.get_object(Bucket=storage.bucket, Key=key)["Body"].read()
    return str(stored.decode())
