"""One reachability check per resource. Each returns quietly or raises."""

import boto3
import psycopg
import redis
from botocore.config import Config as BotoConfig

from app.core.config import CacheConfig, DatabaseConfig, StorageConfig

TIMEOUT_SECONDS = 3


def probe_database(config: DatabaseConfig) -> None:
    with psycopg.connect(
        config.url.get_secret_value(), connect_timeout=TIMEOUT_SECONDS
    ) as connection:
        connection.execute("SELECT 1")


def probe_cache(config: CacheConfig) -> None:
    client = redis.Redis.from_url(
        config.url.get_secret_value(),
        socket_connect_timeout=TIMEOUT_SECONDS,
        socket_timeout=TIMEOUT_SECONDS,
    )
    try:
        # A key inside the mini-app's own prefix: the cache user may touch only those.
        client.exists(f"{config.key_prefix}probe")
    finally:
        client.close()


def probe_storage(config: StorageConfig) -> None:
    client = boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key.get_secret_value(),
        config=BotoConfig(
            connect_timeout=TIMEOUT_SECONDS,
            read_timeout=TIMEOUT_SECONDS,
            retries={"max_attempts": 1},
            s3={"addressing_style": "path"},
        ),
    )
    client.head_bucket(Bucket=config.bucket)
