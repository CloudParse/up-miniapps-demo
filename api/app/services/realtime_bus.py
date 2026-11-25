"""The shared bus that carries a realtime message to every replica of the API.

``RealtimeHub`` only knows the sockets of its own process. With several replicas (or
several workers), a message pushed by one process would miss the sockets held by the
others. This bus uses Valkey publish and subscribe (the mini-app's cache): every
process publishes to one channel and listens to it.

The channel name starts with ``CACHE_KEY_PREFIX``, like every key of the mini-app.
Each message carries the id of the process that published it, so a process does not
deliver its own message twice (it already sent it to its own sockets).

A failing bus never breaks a request: the publisher logs and goes on, and the
listener retries with a growing pause.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Protocol

import redis.asyncio as aioredis

from app.core.config import Config

logger = logging.getLogger(__name__)

CHANNEL_SUFFIX = "realtime"
TIMEOUT_SECONDS = 5
RECONNECT_MIN_SECONDS = 1.0
RECONNECT_MAX_SECONDS = 30.0

Deliver = Callable[[dict[str, object]], Awaitable[object]]


class RealtimeBus(Protocol):
    async def publish(self, message: dict[str, object]) -> None: ...


def encode(origin: str, message: dict[str, object]) -> str:
    return json.dumps({"origin": origin, "message": message}, separators=(",", ":"))


def decode(raw: str | bytes, own_origin: str) -> dict[str, object] | None:
    """The message of another process, or ``None`` (own echo, unreadable payload)."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("origin") == own_origin:
        return None
    message = data.get("message")
    return message if isinstance(message, dict) else None


class RedisRealtimeBus:
    def __init__(self, url: str, key_prefix: str) -> None:
        self._url = url
        self.channel = f"{key_prefix}{CHANNEL_SUFFIX}"
        # One random id per process: tells a process its own message from the others.
        self.origin = secrets.token_hex(8)

    def _client(self) -> aioredis.Redis:
        # health_check_interval: a subscriber blocks on read, so a connection
        # dropped silently by a proxy is only noticed by this periodic check.
        return aioredis.Redis.from_url(
            self._url,
            socket_connect_timeout=TIMEOUT_SECONDS,
            socket_timeout=TIMEOUT_SECONDS,
            socket_keepalive=True,
            health_check_interval=30,
        )

    async def publish(self, message: dict[str, object]) -> None:
        client = self._client()
        try:
            await client.publish(self.channel, encode(self.origin, message))
        finally:
            await client.aclose()

    async def run(self, deliver: Deliver) -> None:
        """Listen until cancelled. Retries with a growing pause if the cache fails."""
        pause = RECONNECT_MIN_SECONDS
        while True:
            client = self._client()
            try:
                async with client.pubsub() as pubsub:
                    await pubsub.subscribe(self.channel)
                    logger.info("realtime bus: subscribed to %s", self.channel)
                    pause = RECONNECT_MIN_SECONDS
                    async for item in pubsub.listen():
                        if item.get("type") != "message":
                            continue
                        message = decode(item["data"], self.origin)
                        if message is not None:
                            await deliver(message)
            except Exception as error:  # noqa: BLE001 - the listener must never die
                logger.warning(
                    "realtime bus: %s, retrying in %.0f s", type(error).__name__, pause
                )
            finally:
                await client.aclose()
            await asyncio.sleep(pause)
            pause = min(pause * 2, RECONNECT_MAX_SECONDS)


def build_realtime_bus(config: Config) -> RedisRealtimeBus | None:
    """The Valkey bus, or ``None`` without a cache (one process: the hub is enough)."""
    url = config.cache.url.get_secret_value()
    return RedisRealtimeBus(url, config.cache.key_prefix) if url else None
