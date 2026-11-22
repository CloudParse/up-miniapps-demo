"""A tiny end-to-end example of the three DEV resources.

One row in PostgreSQL, one counter in the cache, one object in the bucket. Delete it
(and its route, schema, tests and the mini-app card) when you start your own features.
It shows the pattern: a service that knows nothing about HTTP, built from the
configuration, with every resource optional.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import boto3
import psycopg
import redis
from botocore.config import Config as BotoConfig

from app.core.config import Config
from app.schemas.demo import DemoVisit
from app.services.resource_probes import TIMEOUT_SECONDS

OBJECT_KEY = "demo/last-visit.json"

# Each action takes the visitor's id and returns what it read back.
RecordDatabase = Callable[[str], int]
RecordCache = Callable[[str], int]
RecordStorage = Callable[[str], str]


@dataclass(frozen=True)
class DemoActions:
    database: RecordDatabase | None
    cache: RecordCache | None
    storage: RecordStorage | None

    @classmethod
    def from_config(cls, config: Config) -> DemoActions:
        database, cache, storage = config.database, config.cache, config.storage
        return cls(
            database=(
                lambda user: _record_database(database.url.get_secret_value(), user)
            )
            if database.url.get_secret_value()
            else None,
            cache=(
                lambda user: _record_cache(
                    cache.url.get_secret_value(), cache.key_prefix, user
                )
            )
            if cache.url.get_secret_value()
            else None,
            storage=(lambda user: _record_storage(config, user))
            if storage.endpoint and storage.bucket
            else None,
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


def _record_database(url: str, user_id: str) -> int:
    with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS demo_visits ("
            "id bigserial PRIMARY KEY, user_id text NOT NULL, "
            "visited_at timestamptz NOT NULL DEFAULT now())"
        )
        connection.execute("INSERT INTO demo_visits (user_id) VALUES (%s)", (user_id,))
        row = connection.execute("SELECT count(*) FROM demo_visits").fetchone()
        return int(row[0]) if row else 0


def _record_cache(url: str, key_prefix: str, user_id: str) -> int:
    client = redis.Redis.from_url(
        url, socket_connect_timeout=TIMEOUT_SECONDS, socket_timeout=TIMEOUT_SECONDS
    )
    try:
        # Every key starts with the mini-app's prefix: the cache user may touch
        # nothing else.
        return int(client.incr(f"{key_prefix}demo:visits"))
    finally:
        client.close()


def _record_storage(config: Config, user_id: str) -> str:
    storage = config.storage
    client = boto3.client(
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
    body = json.dumps({"user": user_id, "at": datetime.now(UTC).isoformat()}).encode()
    client.put_object(
        Bucket=storage.bucket, Key=OBJECT_KEY, Body=body, ContentType="application/json"
    )
    stored = client.get_object(Bucket=storage.bucket, Key=OBJECT_KEY)["Body"].read()
    return stored.decode()
